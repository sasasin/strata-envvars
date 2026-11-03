# `FNX_PF_F16ACC`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` のプロンプト用 dense GEMM と hyper-connection の up projection で、積和の出力を f16 で扱う経路を選びます。既定値は OFF です。設定しても通常の Strata エンジンや decode 全般を切り替える変数ではありません。`strata-split` は別 executable としてビルドされる任意の all-cards split エンジンです（`src/split/CMakeLists.txt:1-5,64-68,92-120`）。

## 値と判定

環境変数は `env_flag()` から `env_int(name, 0)` に渡され、10 進の整数として全体を parse した後、0 以外を true とします。文字列の真偽値判定ではありません（`src/split/src/env.hpp:15-21,33-39,51-52`）。

| 値 | 結果 |
| --- | --- |
| 未設定 | OFF（既定値 0） |
| `0`, `+0`, `-0`, `000` | OFF |
| `1`, `2`, `-1` など、範囲内の 0 以外の整数 | ON |
| 空文字、前後の空白、`true`、`1x`、整数範囲外 | `std::runtime_error` |

整数は省略可能な符号と数字だけを許し、文字列末尾まで消費される必要があります。空白の読み飛ばしや小数・接尾辞の許容はありません。範囲外は `strtoll` の `ERANGE` で無効になります。無効値の fallback はなく、例外メッセージは `FNX_PF_F16ACC: '<値>' is not a whole number` です（`src/split/src/env.hpp:15-21,33-39`）。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` で対応する `strata-split-N` executable がビルドされ、その executable が選択・起動される必要があります。split engine のビルドは既定 OFF で、CMake は Linux CUDA または Linux HIP の構成以外をスキップします（`src/split/CMakeLists.txt:1-5,20-30,64-80,92-120`）。
- 起動した split engine のプロンプト経路で、dense GEMM または hyper-connection の up projection が実行されると値が使われます。通常の Strata engine を起動しただけでは、この `src/split` の読み取りは通りません（`src/split/src/engine.cu:275`, `src/split/src/prefill.cu:625-646,410-427,451-468`）。
- CLI 引数や別環境変数による上書き分岐はありません。`Engine::prefill_alloc()` が各カードの `Pf` を作る際に値を読み、`p->f16acc` に保持します。static cache はなく、各カードの初期化時に読み取ります。初期化後に環境値を変えても、作成済みの `Pf` の設定は変わりません（`src/split/src/prefill.cu:625-646`）。

## 実行時の詳細

OFF の `pf_gemm()` は f16 の重み・入力を使い、出力を f32 として GEMM に渡します。ON では一時出力を f16 とし、`CUBLAS_COMPUTE_16F` を指定してから `k_f16_f32` で f32 の出力バッファへ変換します（`src/split/src/prefill.cu:410-427`）。この共通経路は `pf_dense_xh()` から dense projection に使われます（`src/split/src/prefill.cu:429-443,1201,1210-1211,1293-1296`）。

hyper-connection の down projection に続く up projection も同じフラグで分岐し、ON の場合は f16 出力と `CUBLAS_COMPUTE_16F` を使ってから f32 に変換します。OFF は f32 出力と `CUBLAS_COMPUTE_32F` を使います（`src/split/src/prefill.cu:451-468`）。

この変数専用の有効化ログはありません。整数 parse に失敗すると例外で初期化が中断します。GEMM の cuBLAS 呼び出しが失敗した場合も、`ckb` が `prefill: cublas <処理名>: <status>` の例外にします（`src/split/src/pf_common.cuh:30-32`）。Strata ソースから確認できるのはこの呼び出し設定・変換・エラー経路までです。cuBLAS / GPU が実際に選ぶ内部実装や、精度・性能への定量的影響はここでは断定しません。

## 根拠

- 候補名のソース全体検索では、実際の読み取りは `src/split/src/prefill.cu:645` の一箇所でした。もう一つの参照は同ファイル冒頭の説明コメント（`src/split/src/prefill.cu:1-3`）です。helper `env_flag()` と `env_int()` の定義、および全 helper 呼び出しも確認しました。
- `src/split/src/env.hpp:15-21,33-39,51-52` — 整数 parse、既定値、0 判定。
- `src/split/src/prefill.cu:410-427,451-468,625-646` — 値の保存先と f16/f32 の処理分岐。
- `src/split/src/engine.cu:275`、`src/split/CMakeLists.txt:1-5,20-30,92-120` — 初期化呼び出しと実行ファイルの build 条件。
- `src/split/src/pf_common.cuh:30-32` — cuBLAS エラーの例外化。
