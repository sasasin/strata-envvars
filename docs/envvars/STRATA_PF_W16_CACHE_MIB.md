# `STRATA_PF_W16_CACHE_MIB`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

CUDA の prefill で `Gemm::native()` が扱う量子化重みについて、初回 dequantization 後の FP16 重みを GPU メモリに保持する合計予算を MiB 単位で指定します。同じ重みを再度処理するときに保持済み FP16 データを使い、dequantization を省きます。エントリーは重みポインター・型・形状で識別され、`Gemm` インスタンスの破棄時に解放されます。対象コードで環境変数を読むのは `src/prefill/gemm.cu` の CUDA 側実装です。HIP ビルドではこの処理ブロック自体が除外されます。

## 値と判定

環境変数は各 `Gemm` インスタンスの `native()` 初回呼び出し時に読みます。設定値がある場合は、文字列全体の比較で小文字の `auto` と一致する場合を除き、`std::atoll()` で数値化し、結果に `2^20` を掛けてバイト予算にします。値の形式検証や明示的な範囲 clamp はありません。

| 状態・値 | 判定と予算 |
|---|---|
| 未設定 | Linux CUDA でエンジンが batch slots を使う既定が設定済みなら、16 GiB 予算・3 GiB reserve。それ以外は無効（0）。 |
| `auto` | 16 GiB 予算・3 GiB reserve。大文字小文字を区別し、`AUTO` や前後に文字が付いた値は `auto` として扱いません。 |
| 数値文字列 | `atoll` の結果を MiB として換算し、2 GiB reserve。正の結果ならキャッシュ候補、0 以下ならキャッシュしません。 |
| 空文字 | `atoll("")` 相当で 0 となり、無効。 |
| 数値として読めない文字列 | `atoll` が 0 を返すため無効。 |
| 数字の後ろに文字が続く値 | `atoll` が読む先頭の数値部分を採用します（例: `2048junk` は 2048 MiB）。 |
| 負数 | 負の予算となり `w16_budget_ > 0` の条件を満たさないためキャッシュしません。負数は未読を表す負値 sentinel とも重なるため、負の設定では `native()` 呼び出しごとに環境を読み直します。 |

数値予算の換算には乗算の範囲検査がなく、入力可能範囲はコードで制限されていません。通常の正の予算でも、後述の空き VRAM・reserve 条件を満たさなければ新規エントリーは作られません。根拠: `src/prefill/gemm.cu:1411-1433`, `include/strata/prefill/gemm.hpp:97-112`。

## 有効になる条件

- `Gemm::native()` が呼ばれる CUDA prefill 経路であること。ネイティブ GGUF ブロックのない重みは上位の `native_proj()` がエラーを返します（`src/prefill/prefill.cpp:2948-2954`）。全ての prefill 経路がこの関数を使うわけではありません。
- キャッシュ予算が正で、`side_scratch_` が未使用であること。side-stream dequant 経路では通常の dequant/GEMM に進みます。
- 対象重みの FP16 展開サイズ `N*K*2` が残り予算に収まり、`cudaMemGetInfo()` が成功し、割り当て後に設定された reserve を超える空きがあること。キャッシュ可能な重みを保持した場合は `f16()` を呼んで戻り、再利用時は同じキャッシュ済み重みを使います。条件を満たさない重みは通常の scratch dequant 経路に進みます。

明示値があると、未設定時のエンジン既定を上書きします。特に `=0` は Linux CUDA の batch slots 既定も無効化します。未設定時の既定有効化は `src/program/generate.cpp` の Linux CUDA 条件（HIP、Metal、Windows を除外）内で、`o.batch >= 2` の場合に `set_w16_auto_default(true)` を呼ぶものです。既定 atomic の初期値は false です。明示的な `auto` と数値は `gemm.cu` の CUDA 実装で直接解釈されます。

## 実行時の詳細

`Gemm` の `w16_budget_` は初期値 `-1`（未読）で、最初の `native()` 呼び出し時に環境値または上記の既定を決めます。通常の非負値では、そのインスタンス内で判定済み予算を保持し、後からプロセス環境を変えても再評価しません。キャッシュはインスタンスごとで、`Gemm` 破棄時に保持した device allocation を `cudaFree()` します。

新規キャッシュ割り当てが失敗した場合（空きメモリ取得失敗、reserve を含む空き不足、または `cudaMalloc()` 失敗）、その場で `cudaGetLastError()` を消費し、stderr に `strata prefill: FP16 weight cache ...` をインスタンスにつき一度出します。その後の予算を既に保持した量、保持量がなければ 0 に変更し、新規割り当てを止めます。処理自体は通常の scratch dequant に続き、ここでは終了しません。予算上限に達して新しい重みが入らないだけの場合、この割り当て失敗ログは出ません。

Linux CUDA のエンジンでは batch slots（`o.batch >= 2`）時に未設定既定を有効化します（`src/program/generate.cpp:8176-8181`）。サーバーは環境をコピーして engine 子プロセスを起動し、設定の `env` をその後に上書き適用します（`serve/server.py:4325-4342`）。したがって継承した環境値は engine に届き、設定 `env` の同名値があればそちらが優先されます。サーバーの `PARALLEL_STACK_ENV` にこの変数は含まれず、サーバー側の自動設定値ではありません（`serve/server.py:4250-4254,4280-4290`）。

## 根拠

- 環境値の読み取り、`auto` / 数値 / unset の分岐、予算・reserve の設定、VRAM 条件、キャッシュ利用、失敗ログと通常経路への継続: `src/prefill/gemm.cu:1403-1461`。
- キャッシュのキー、インスタンスごとの予算と使用量、未読 sentinel、reserve、auto 既定値: `include/strata/prefill/gemm.hpp:97-112`。
- `Gemm` 破棄時のキャッシュ解放: `src/prefill/gemm.cu:646-648`。
- Linux CUDA の batch slots 既定条件: `src/program/generate.cpp:8176-8181`。
- native GGUF 投影から `Gemm::native()` への呼び出しと native 重み欠落時のエラー: `src/prefill/prefill.cpp:2948-2954`。
- サーバー子プロセスへの環境継承・設定環境の上書き: `serve/server.py:4325-4342`。
