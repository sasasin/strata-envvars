# `STRATA_BENCH_PLANAR`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL ビルドの `mmvq_bench` が、通常の Q6_K 行列と planar 配置の行列で出力がビット単位に一致するか、さらに planar 配置から選択行を gather した結果が元行列の同じ行と一致するかを追加検証します。通常の `strata` エンジンの推論経路からこの変数を読むコードはありません。用途はベンチマーク／検証用の実行ファイルに限られます。

## 値と判定

`mmvq_bench` はベースライン測定・checksum 出力の後に `std::getenv` で読み取り、設定値に `std::atoi` を適用した結果が 0 以外かを判定します。

| 値 | planar 追加検証 |
|---|---|
| 未設定 | 行わない |
| 空文字 | 行わない（`atoi("")` は 0） |
| 先頭の空白や符号の後に 0 以外の数字がある文字列（例: `1`, ` 1`, `+2`, `-1`, `1tail`） | 行う（`atoi` が 0 以外を返す） |
| `0`、`0tail`、数値に変換できない文字列 | 行わない（`atoi` が 0 を返す） |

文字列全体の数値としての妥当性は検査されません。したがって `1tail` は有効、`true` は無効です。範囲チェック、clamp、無効値時の警告や fallback はありません。`atoi` が表現範囲外の値を受けた場合の結果は、このコードでは規定・処理していません。

## 有効になる条件

- SYCL プロジェクトで `mmvq_bench` がビルドされていること。`sycl/CMakeLists.txt` ではこのターゲットは `STRATA_SYCL_PARITY` の有効ブロック内にあり、同オプションの既定値は ON です。トップレベルから SYCL を選ぶ場合は `STRATA_ENABLE_SYCL=ON` が必要で、CUDA/HIP と同時には有効にできません。
- `mmvq_bench` を実行すること。この環境変数はエンジン本体や他のツールで参照されません。
- `STRATA_BENCH_PLANAR` が 0 以外に変換されること。
- planar adoption が成功すること。これは別環境変数 `STRATA_Q6_PLANAR` の判定や行列形状・デバイスメモリなどに依存します。`STRATA_Q6_PLANAR=0` では adoption が無効になり、このベンチは `planar: adopt declined` を出して終了コード 1 になります。ベンチ用行列の `n_in` は 256 の倍数、`n_in` と `n_out` は正数である必要があります。

## 実行時の詳細

プログラムはまず既定または CLI 引数から行列サイズ（`n_in`, `n_out`, `ncols`）を取り、ランダムな Q6_K 重みと入力を用意します。通常配置の MMVQ を実行して checksum を出力した後に、この変数を一度読みます。値が有効なら重みのコピーを用意して planar adoption を試し、planar MMVQ の全出力を通常配置の結果と `memcmp` で比較します。その後 20 回ウォームアップし、400 回測定して時間を出力します。さらに `max(1, n_out / 3)` 行を選んで planar gather し、全列について gather 結果を元行列の対応行とビット比較します。

全出力が一致すれば `bitwise EQUAL`、異なれば `bitwise DIFFERENT` と表示します。gather の不一致数も表示し、どちらかの比較に差があれば終了コード 1、差がなければ 0 です。adoption または gather を行えない場合も診断を出して終了コード 1 になります。変数は `main` 内で一度だけ評価されるので、起動後の環境変更は反映されません。子プロセスへの転送処理はありません。

## 根拠

- `sycl/src/kernels/mmvq_bench.cpp:13-28` — 引数と合成データを用意し、ベースラインを実行。
- `sycl/src/kernels/mmvq_bench.cpp:51-59` — baseline checksum の後で環境変数を読み、`atoi(...) != 0` で分岐。
- `sycl/src/kernels/mmvq_bench.cpp:60-97` — planar adoption、全出力と gather 結果の比較、測定、終了コード。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3062-3067,3075-3115,3118-3152` — SYCL カーネル側の planar 機能条件、adoption/gather の失敗時処理とログ。
- `sycl/CMakeLists.txt:254-255,362-365,396` — `STRATA_SYCL_PARITY` のブロック内で `mmvq_bench` を作成。
- `CMakeLists.txt:12-21` — トップレベルの SYCL 選択条件。
- `docs/INTEL.md:491-500` — 関連する `STRATA_Q6_PLANAR` の設計説明と測定値。これは `STRATA_BENCH_PLANAR` の有効化による速度効果を示す記述ではありません。
