# `STRATA_PREFILL_ISSUER`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

GPU prefill 中に、VRAM に常駐していない expert の host-to-device コピーを発行する担当を切り替えます。既定では専用のホストスレッドがコピーを発行します。`0` と解釈される値を設定すると、層の計算を進めるスレッドがコピーを逐次発行します。

この切り替えは CUDA/HIP 共通の `src/prefill/prefill.cpp` と SYCL 用 `sycl/src/prefill/prefill.cpp` にあります。CUDA/HIP 側では CMake が同じ `src/prefill/prefill.cpp` を `strata_prefill` に含めます（`CMakeLists.txt:589-595`）。SYCL 側も同じ prefill 実装を解決してライブラリに含めます（`sycl/CMakeLists.txt:232-236`）。

## 値と判定

両実装とも `std::getenv()` と `std::atoi()` を使い、結果を関数内 `static const bool` に保存します。

| 環境変数の値 | 判定 |
|---|---|
| 未設定 | 有効（専用スレッド） |
| 設定され、`atoi` の結果が `0` | 無効（計算側スレッドが逐次発行） |
| 設定され、`atoi` の結果が非 `0` | 有効（専用スレッド） |

これは文字列全体の真偽値 parse ではありません。`atoi` は先頭の空白と符号の後から十進数字を読み、数字の後ろの文字列は判定に使いません。そのため `1`, `1tail`, `-1`, ` 2` は有効、`0`, `0tail`, 空文字, `false`, `tail` は無効です。数値として表現できない範囲の入力は使用しないでください。

## 有効になる条件

変数が有効でも、当該 chunk で expert の全体ストリーミングが行われない場合は専用スレッドを起動しません。実装上の条件は、staging ring が `STAGE`（8 slot）より大きいこと、chunk 長 `T` が `stream_all_min()` 以上であること、expert source `m.src` が存在することです。CUDA/HIP では `stream_all_min()` の既定値は1,024 token で、`STRATA_PREFILL_STREAM_MIN` や CPU share の設定により条件が変わる場合があります。SYCL の既定値も1,024 token で、`STRATA_PREFILL_STREAM_MIN` がしきい値を上書きします。これらの条件を満たすかどうかは本変数とは別に決まります。

ソース内で環境変数を読む箇所は CUDA/HIP と SYCL の prefill 実装です。HIP でも CUDA/HIP 共通ソースがビルドされます。GPU backend を通らない処理には適用されません。

## 実行時の詳細

判定値は prefill の `run_impl()` 内の関数ローカル static として初回に評価され、以後プロセス内で再読込されません。したがって、プロセス起動後に環境を書き換えても反映されません。

有効時は専用スレッドが expert を layer/expert 順にステージング ring へコピー発行します。コピー先 slot の再利用は、計算側が該当 slot の使用完了を記録して ring を開放するまで待ちます。計算側は次の expert を使う前に発行済み状態とコピー完了 event を確認します。CUDA 実装では補助 CPU pool にスレッドを pin し、対象 device を選びます。SYCL 実装でも専用スレッドから同じ順序でコピーを発行します。

無効時はスレッドを作らず、最初の ring 分を計算側から発行し、その後は計算側が消費済み slot を開放するたびに次のコピーを発行します。どちらの経路も同じ順序・slot で同じ expert blob を転送する実装です。専用スレッドを有効にすることで prompt 中の pageable blob の host 側待ちが計算用スレッドを止めないようにする意図が、ソースコメントに記されています。変数専用のログ出力はありません。

`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。性能差や出力同一性について、この調査で独立した測定はしていません。

## 根拠

- CUDA/HIP 側の値判定、スレッド起動、ring 進行: `src/prefill/prefill.cpp:2416-2475`。
- CUDA/HIP 側の stream 条件と threshold: `src/prefill/prefill.cpp:149-153,2301-2303`。
- CUDA/HIP 側のスレッド join と統計更新: `src/prefill/prefill.cpp:4040-4047`。
- SYCL 側の stream 条件と threshold: `sycl/src/prefill/prefill.cpp:119-121,2460-2465`。
- SYCL 側の値判定、スレッド起動、ring 進行: `sycl/src/prefill/prefill.cpp:2618-2690`。
- SYCL 側のスレッド join と統計更新: `sycl/src/prefill/prefill.cpp:4415-4422`。
- CUDA/HIP と SYCL の prefill ソースを含むビルド定義: `CMakeLists.txt:589-595`, `sycl/CMakeLists.txt:232-236`。
