# `SPIN_MAX`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`SPIN_MAX` は `sycl/tools/build.sh` が読むビルド用環境変数です。設定すると、SYCL エンジンがホスト側のフラグを待つ device spin の上限を、デバイスごとの実行時選択に代えてビルド時に固定する CMake 変数 `STRATA_SYCL_SPIN_MAX` へ渡します。Strata の実行ファイルが `SPIN_MAX` という名前を直接読む箇所はありません。実行時に読むのは別名の `STRATA_SPIN_MAX` です。

## 値と判定

`build.sh` は `${SPIN_MAX:-}` を CMake の `-DSTRATA_SYCL_SPIN_MAX=...` に渡します。シェルの `:-` 展開により、未設定と空文字はいずれも空文字として渡されます。スクリプトや CMake に値の数値検証はありません。

| `SPIN_MAX` | CMake での扱い | 結果 |
|---|---|---|
| 未設定または空文字 | `STRATA_SYCL_SPIN_MAX` は空 | コンパイル定義を追加せず、実行時にデバイスごとの上限を選ぶ |
| `0` | CMake の `if(STRATA_SYCL_SPIN_MAX)` は偽 | コンパイル定義を追加せず、実行時選択になる。上限 0 を固定する設定ではない |
| `20000` など非ゼロの文字列 | CMake 条件が真となり、`STRATA_SYCL_SPIN_MAX=<値>u` を定義 | すべてのデバイスにその値を固定する |

CMake は値の形式や範囲を検査せず、真と判定した値をそのまま C++ のマクロ定義に連結します。したがって数値以外の値が正しく受理される保証はなく、ビルド時に問題になる可能性があります。

根拠: `sycl/tools/build.sh:5-9`, `sycl/CMakeLists.txt:31-38`。

## 有効になる条件

この変数を読み取るのは `sycl/tools/build.sh` だけです。スクリプトは `$BUILD_DIR/build.ninja` が存在しない場合に限って CMake を実行し、そのとき `SPIN_MAX` を渡します。既存の `build.ninja` があるビルドディレクトリでは CMake を再実行しないため、環境変数を変更しても設定は更新されません。値を変更して反映するには、該当ビルドディレクトリを再構成する必要があります。

CMake が非空のコンパイル定義を作ると、実行時の `STRATA_SPIN_MAX` が未設定・空・正数に変換できない値・0以下の場合に、そのビルド値が使われます。正の `STRATA_SPIN_MAX` が設定されている場合は、ビルド値より優先されます。`spin_max()` はデバイスごとの結果をプロセス内キャッシュするため、そのデバイスで初めて評価した後に `STRATA_SPIN_MAX` を変えても再評価されません。

根拠: `sycl/tools/build.sh:5-8`, `sycl/include/strata/sycl_doorbell.hpp:134-152`。

## 実行時の詳細

SYCL の doorbell wait と verifier の wait kernel は、ホスト側フラグを読むループの反復上限として `spin_max(queue)` の値を受け取ります。上限までにフラグ条件を満たさない場合、device 側の待機ループを抜けます。この helper は、実行時環境変数 `STRATA_SPIN_MAX` が設定されていて `std::atol()` の結果が正なら、その結果を `uint32_t` に変換します。変換は文字列全体の厳密な検査ではないため、たとえば先頭が正の数値で後ろに文字が続く値も `atol()` の数値部分で判定されます。

実行時変数が有効でない場合、ビルド時定義があればそれを使います。定義がない場合は、`xe` ドライバーなら 20,000 回、ドライバー名を取得できない Battlemage なら通常 20,000 回（MTP 層なしで spec drafting を行う要求が先に設定された場合は 2,000,000 回）、その他は 2,000,000 回です。これらは `SPIN_MAX` の値ではなく、値を渡さなかったビルドで使われる実行時 fallback です。

根拠: `sycl/include/strata/sycl_doorbell.hpp:114-152`, `sycl/src/kernels/cuda/elementwise.dp.cpp:385-411`, `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2398-2410,2457-2468`, `sycl/src/program/generate.cpp:2309`。

## 文書との照合

`docs/INTEL.md:708-717` はこの上限が device spin を制限し、SYCL のビルドオプション `STRATA_SYCL_SPIN_MAX` を `SPIN_MAX` で `sycl/tools/build.sh` に渡せると説明しています。測定値は同資料にある特定の起動条件での記録であり、この調査では再測定していません。現在のソースでは空のビルド設定時に `spin_max()` がデバイス・driver・drafting 条件を見て上限を選ぶため、文書の「通常 2,000,000、B-series AOT は 20,000」という要約だけでは全 fallback 条件を表しません。
