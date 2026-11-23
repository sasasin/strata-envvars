# `HY4_DRY_LAUNCH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Hy4-Flash の CUDA/HIP 共通 GPU 起動 wrapper `hy4::gpu_launch` で、GPU kernel の起動を省くための実験用スイッチです。`HY4_DRY_LAUNCH` が環境に存在すると、wrapper は kernel 起動式に進まず return します。値の内容は使いません。宣言コメントは「host-overhead experiment」としています（`engine/src/hy4flash/run/hy4_gpu.h:103-111`）。

この wrapper は `hipLaunchKernelGGL` に割り当てられており、Hy4-Flash の CUDA/HIP ソースにある同マクロ経由の起動が対象です。CMake の `strata-hy4` は `STRATA_BUILD_HY4` が有効で CUDA または HIP が有効な場合に構成され、Metal/SYCL は専用スクリプト経由です（`engine/src/hy4flash/run/hy4_gpu.h:104-111`、`engine/CMakeLists.txt:846-852,884-891`）。

## 値と判定

`getenv("HY4_DRY_LAUNCH") != nullptr` だけで判定します。文字列比較や数値変換はなく、環境変数の設定有無が条件です（`engine/src/hy4flash/run/hy4_gpu.h:105-108`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Hy4-Flash CUDA/HIP wrapper | `dry == false`。kernel 起動式を実行 | 空文字、`0`、`1`、`false`、その他どの文字列でも `dry == true` | なし。環境変数が存在する限り値による無効化はない |

大文字小文字、空白、文字列全体の形式は判定されません。CLI 引数や別の環境変数との優先順位・上書き処理もこの読み取り箇所にはありません（`engine/src/hy4flash/run/hy4_gpu.h:105-108`）。

## 有効になる条件

- `engine/src/hy4flash/run/hy4_gpu.h` の `gpu_launch` と `hipLaunchKernelGGL` wrapper を使う Hy4-Flash CUDA/HIP コードであること。CMake では `STRATA_BUILD_HY4=ON` に加え、`STRATA_ENABLE_CUDA=ON` または `STRATA_ENABLE_HIP=ON` が必要です。`STRATA_BUILD_HY4` は既定で OFF です（`engine/CMakeLists.txt:846-852`）。
- Metal/SYCL 実装では、この名前を読む参照は見つかりません。したがって同名変数を設定しても、それらの専用実装に対する Strata 側の作用は確認できません。
- wrapper 以外の GPU runtime 呼び出しを止める処理はここにはありません。設定時に GPU kernel が起動されないことは確認できますが、その状態でのモデル計算・CLI の終了・エラーの結果を、この分岐だけから一般化できません（`engine/src/hy4flash/run/hy4_gpu.h:105-111`）。

## 実行時の詳細

`gpu_launch` の最初の呼び出しで関数内 `static const bool dry` が初期化され、その値を以降の呼び出しで再利用します。従って実行中に環境を変更しても、このプロセスで既に初期化された値には反映されません。読み取りより前に環境が設定されているかが判定に使われます（`engine/src/hy4flash/run/hy4_gpu.h:104-108`）。

`dry` が true の場合は `return` し、kernel launch 式 `k<<<g, b, shmem, s>>>(a...)` を実行しません。false の場合はその式を実行します。wrapper 自体はログ、警告、環境値の書き換えを行いません（`engine/src/hy4flash/run/hy4_gpu.h:105-111`）。

## ログと測定値

この分岐に対応するログ出力、明示的な終了・失敗処理、測定値の記載は確認できません。ヘッダーのコメントは host overhead の実験用途を示しますが、測定条件や数値は示していません（`engine/src/hy4flash/run/hy4_gpu.h:105-108`）。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu.h:103-111` — 設定有無の読み取り、static 保存、kernel launch のスキップ、HIP 起動マクロへの割り当て。
- `engine/CMakeLists.txt:846-852,884-891` — Hy4-Flash ターゲットの既定状態、CUDA/HIP 必須条件、コンパイル対象。
