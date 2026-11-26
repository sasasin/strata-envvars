# `STRATA_MMVQ_WIDE_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL エンジンの Q6_K MMVQ で wide カーネルを選ぶ最小出力行数 `n_out` を指定する。条件を満たすと 16-byte-load の Q6_K wide カーネルを起動し、満たさない場合は rowwarp または通常の Q6_K MMVQ に進む。CUDA/HIP など他 backend の実装ではこの変数を読まない。`native_mmvq` は GGML type 14 を `native_q6_k_mmvq` に渡す（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3956,4204-4217`）。

## 値と判定

最初に通常の Q6_K MMVQ 判定まで到達したとき、関数内 `static const int` として一度だけ読み取る。設定されていれば `std::atoi` の結果を閾値にし、設定値の全体検証、範囲検査、clamp はしない。`atoi` は数値の接頭部分を変換するため、空文字や数字で始まらない値は `0`、`4096tail` は `4096` になる。符号や先行空白も `atoi` の変換規則に従う。数値変換できない文字列をエラーにはしない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3943-3945`）。

| 条件 | 未設定 | 設定時に有効になる値 | 設定時に閾値が `0` になる例 |
|---|---:|---|---|
| `STRATA_MMVQ_A2` が未設定、または `atoi` 結果が非ゼロ | `0` | `n_out >= atoi(値)`。例: `4096` は 4096 行以上 | `0`, `0tail`, 空文字, `true`, `abc` |
| `STRATA_MMVQ_A2` が設定され、`atoi` 結果が `0` | `4096` | 同上。例: `4096` は 4096 行以上 | 同上 |

`STRATA_MMVQ_A2` は unset なら有効、設定時は `atoi` の結果が非ゼロの場合だけ有効であり、同じく関数内 static に cache される。したがって `STRATA_MMVQ_WIDE_MIN` が未設定の場合の既定値は A2 の状態で変わる。WIDE_MIN を明示した場合はその変換値が優先される。`n_out` が閾値と等しい場合も条件を満たし、負の閾値も拒否・補正されない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1548,3943-3945`）。

## 有効になる条件

- `engine/sycl/CMakeLists.txt` が `native_mmvq.cu` の移行済みソースとしてビルドする SYCL エンジン実装でのみ有効（同ファイル `:273-286`）。OS ごとの条件はない。
- Q6_K の `native_q6_k_mmvq` に到達し、先行する packed Q6_K または planar Q6_K の経路が行列を処理しないこと。これらは登録済み重みを見つけると wide 閾値判定より先に return する（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2900,3007-3034,3935-3939`）。
- `STRATA_MMVQ_WIDE` が有効であること。未設定なら有効、設定時は `atoi` の結果が非ゼロで有効。さらに `ncols` が `1..wide_maxc`、`n_in` が 256 の倍数、`n_out >= wide_min` であること。`STRATA_MMVQ_WIDE_MAXC` 未設定時の上限は A2 有効時 `8`、無効時 `4`。どれかを満たさない場合 wide カーネルは選ばれない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2185,3943-3959`）。
- 閾値条件を満たさず wide を選ばない場合も、`ncols <= 4`、`STRATA_MMVQ_WIDE_RPW` の値が正、`n_in` が 256 の倍数なら rowwarp 経路が先に試される。それ以外は検証後、複数列なら multi kernel、1 列なら通常 kernel に進む（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1631-1634,3958-4023`）。
- `STRATA_MMVQ_WIDE_MIN` を指定する CLI 引数や、別設定からの上書きはこの判定にはない。

## 実行時の詳細

`native_q6_k_mmvq` はまず packed / planar 行列経路を試し、そのいずれも処理しなかった場合に `wide_min` と `wide_maxc` を初期化する。`wide_min` は最初の到達時に環境を読み、そのプロセス内では再読込しない。起動後に環境を変更しても反映されない。閾値を満たし、wide 全体の条件も通ると `ncols` に応じた `launch_q6k_wide<1..8>` を起動して戻る。wide 以外の経路では、上記 rowwarp の条件を試した後、入力形状を検証し通常 Q6_K カーネルを選ぶ（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-4023`）。

出力行数の閾値以外に、モデル種別やサーバーモードによる専用条件はない。実際に Q6_K MMVQ が呼ばれる場面に適用され、SYCL の dense native MMVQ では GGML type 14 がこの関数へ dispatch される（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4169-4223`）。

## ログと測定値

この変数の値や閾値判定を出力するログはない。Strata の `docs/DETAILS.md` にこの変数の既定値や測定値の記載はなく、数値性能は本調査では主張しない。

## 根拠

- 読み取り、A2 による既定値、wide の dispatch 条件と後続 fallback: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1548,3935-4023`
- Q6_K 型からの dispatch: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4169-4223`
- SYCL build における移行済みソースの選択と登録: `engine/sycl/CMakeLists.txt:273-286`
- packed / planar 登録行列が先に処理される条件: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2900,3007-3034`
