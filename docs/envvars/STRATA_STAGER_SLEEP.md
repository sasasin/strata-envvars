# `STRATA_STAGER_SLEEP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の prefill にある `Stager` が、expert の host-to-device staging 中に待つ方法を選ぶ。sleep 側では Stager の ring が再利用可能になるまでの待ちに atomic wait（利用可能な標準ライブラリの場合）を使い、DMA 完了イベントを blocking-sync 指定で作る。spin 側では atomic wait の代わりに `yield` ループを使い、イベントは timing 無効のみで作る。これは待ち方の切替で、ソースコメントはどちらでも出力は同じとしている（`engine/src/prefill/prefill.cpp:365-379, 1169-1170, 1213-1232`）。

## 値と判定

`stager_sleep()` が最初に呼ばれたとき、`std::getenv` の値を関数内 `static` に一度だけ保存する。未設定または空文字なら OS 既定値を使い、Windows は spin（`false`）、それ以外は sleep（`true`）。空でない値は先頭1文字だけを見て、`'0'` 以外なら sleep、`'0'` なら spin とする。文字列全体の parse、数値妥当性検査、大文字小文字の正規化はしない（`engine/src/prefill/prefill.cpp:369-379`）。

| OS 条件 | unset / 空文字 | sleep になる例 | spin になる例 |
|---|---|---|---|
| `_WIN32` 定義あり | spin | `1`, `true`, `false`, ` 0`, `00x` | `0`, `0anything` |
| `_WIN32` 定義なし | sleep | `1`, `true`, `false`, ` 0`, `00x` | `0`, `0anything` |

したがって `false` は文字列として「false」と解釈されず、先頭が `f` のため sleep になる。先頭の空白も取り除かれない。値が空でない `0` 始まりかどうかが判定境界となる（`engine/src/prefill/prefill.cpp:371-377`）。

## 有効になる条件

- `strata_prefill` は CUDA または HIP GPU engine の構成時に追加される。SYCL engine は別プロジェクトで、この `prefill.cpp` を構成しない（`engine/CMakeLists.txt:20-31`; `engine/cmake/strata_gpu_engine.cmake:6-9, 478-488`）。
- 実際に設定が評価されるには prefill の `Stager::init` が進み、DMA 完了イベントを作成する必要がある。Stager 初期化では ring 各 slot のイベント作成時に設定を使う（`engine/src/prefill/prefill.cpp:1156-1174, 2523-2555`）。
- `issued` watermark の待ちは ring 容量を超える job（`i >= kRing`）で発生する。各 job では別途 DMA event も同期するため、実際の待ち方の差が現れるのは Stager が処理する expert copy job がある経路である。Stager に job がない prompt では worker の待ちは発生しない（`engine/src/prefill/prefill.cpp:1212-1232`）。
- `_WIN32` は既定値だけを決める。明示値は backend 判定や別環境変数によって上書きされない。CLI 引数・設定ファイルとの優先順位を扱う読み取り経路は見つからなかった。
- `STRATA_ATOMIC_WAIT` は `__cpp_lib_atomic_wait` が定義される場合だけ有効になる。未定義の場合、設定が sleep でも `issued` の待ちは `yield` ループにコンパイルされる。一方、イベント生成に渡す blocking-sync flag の選択は残る（`engine/src/prefill/prefill.cpp:33-36, 1217-1223`）。

## 実行時の詳細

`stager_sleep()` の値は Stager 初期化時の最初の DMA event 作成で評価・cache され、その `Stager` のイベント作成と worker 待ちで共有される。実行中に環境変数を書き換えても、この cache 済みの値は変わらない（`engine/src/prefill/prefill.cpp:369-379, 1169-1170, 1173-1181`）。

sleep が選ばれ、atomic wait が利用可能な build では、worker は `issued` の watermark が ring の先行 DMA 完了を示すまで `issued.wait(x)` で待機する。spin 側または atomic wait 非対応 build では同じ watermark を `std::this_thread::yield()` のループで確認する。その後の `ready` 完了確認はどちらの設定でも yield ループであり、worker の `cudaEventSynchronize` は sleep 側で blocking-sync event を使う。呼び出し側の `Stager::wait()` も ready flag を yield しながら待つため、この環境変数はその待ちを切り替えない（`engine/src/prefill/prefill.cpp:1213-1232, 1297-1305`）。

読み取り時点での値はプロセス内 `static` に保存される。子プロセスへの転送・上書きを行うコードはこの変数について見つからなかった。

## ログと測定値

この変数を選んだこと自体を示すログや専用のエラー文言は、Strata 所有ソースでは確認できなかった。イベント作成が失敗した場合に `Stager::init` は `false` を返し、初期化側で `ok` を false にするが、この失敗が環境変数の値そのものを説明するログはない（`engine/src/prefill/prefill.cpp:1169-1170, 2553-2555`）。

`docs/DETAILS.md:1218-1219` は、Windows で sleep を強制する用途と、Windows では spin が少し速いという説明を記載する。同ファイルの測定表は Ryzen 9 7940HS / RTX 4070 / IQ3_S / 64K で、sleep 時に 5,914・22,305 token の prompt が 5–6% 遅く、システム全体 CPU 使用率が 77–90% から 21–25% になったと記載し、RTX 5070 の 8K Q2_0 prompt では spin が 1.2% 速かったとしている（`docs/DETAILS.md:1726`）。これは文書に記載された測定値であり、この調査では再測定していない。

## 根拠

- `engine/src/prefill/prefill.cpp:365-379` — OS 既定値、文字列判定、static cache。
- `engine/src/prefill/prefill.cpp:1156-1183` — Stager の event 作成と worker 起動。
- `engine/src/prefill/prefill.cpp:1213-1232, 1297-1305` — ring 待ち、event 同期、呼び出し側 wait。
- `engine/src/prefill/prefill.cpp:2523-2555` — prefill 初期化での Stager 構築。
- `engine/cmake/strata_gpu_engine.cmake:6-9, 478-488`; `engine/CMakeLists.txt:20-31` — CUDA/HIP GPU engine と SYCL の構成範囲。
