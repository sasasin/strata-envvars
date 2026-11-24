# `STRATA_INK_HASH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。調査開始時の Strata checkout は `main` で、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）だった。

## 役割

Inkling2 の CUDA / HIP runner に、forward と tree verify の中間テンソル行ハッシュを記録して stderr に出す診断スイッチ。通常の推論設定を選ぶ変数ではなく、値が有効だと GPU 上で診断ハッシュを計算し、結果をホストへコピーして `[HASH]` 行を出す。ハッシュ処理はテンソル計算の後に呼ばれ、コード上で logits や token 選択を変更する処理には接続されていない。CUDA は標準 forward/tree の出力に加えて選択した visit の内部 tap を記録できるが、HIP には visit 選択処理がない（`engine/src/inkling2/cuda/ink_runner.cuh:1795-1814, 3228, 3419-3442, 3535-3536, 3649, 3691-3696, 3816-3820`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742, 4093, 4142-4151, 4790, 4840, 5843-5853`）。

## 値と判定

| ビルド / runner | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Inkling2 CUDA | 無効。診断バッファを確保しない | 文字列の先頭が文字 `1`。例: `1`, `10`, `1anything` | 先頭が `1` 以外。例: 空文字、`0`, `true`, ` 1` |
| Inkling2 HIP | 無効。診断バッファを確保しない | 文字列の先頭が文字 `1` | 先頭が `1` 以外 |

両 backend とも `getenv` が null でないことに加え `ev[0] == '1'` を検査する。文字列全体の parse、数値変換、大小文字変換はしない。したがって `1` の後ろの文字は無視され、空文字や空白始まりは無効になる（`engine/src/inkling2/cuda/ink_runner.cuh:2102-2108`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742`）。

## 有効になる条件

- Inkling2 の CUDA runner または HIP backend が実際に初期化されること。これらの runner 内に読み取りがあり、CPU/SYCL/Metal 経路でこの変数を読む箇所は見つからない（`engine/src/inkling2/cuda/ink_runner.cuh:2090-2108`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742`）。
- 値が有効でも GPU 診断バッファの確保が必要。CUDA は `cudaMalloc` / `cudaMemset` の失敗を `INK_CK` 経由で device error 終了経路へ送る。HIP は確保結果が `hipSuccess` の場合だけ `dbg_hash_on_` を true にし、失敗時はハッシュ出力を無効のまま続行する（`engine/src/inkling2/cuda/ink_runner.cuh:2104-2107`; `engine/src/inkling2/cuda/ink_cuda.cuh:34-42`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742`）。
- CUDA では `STRATA_INK_HASH_VISIT` が設定されていれば、その値を `atoi` で整数化して visit 内部 tap の対象を指定する。未設定なら 0。これは `STRATA_INK_HASH` が有効な場合にだけ読み取られ、未解釈の文字列や非数値は `atoi` の結果 0 となる。対象 visit と一致しない場合も visit に依存しない共通ハッシュ（各 visit の cur / MoE 入力 / router logits など）は残る（`engine/src/inkling2/cuda/ink_runner.cuh:1795-1799, 2102-2106, 3228, 3408-3420, 3513-3517`）。HIP はこの選択変数を読まず、実装上の呼び出し箇所にある visit 0 の attention tap と各 visit の共通ハッシュを処理する（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4093, 4142-4151, 4790, 5420, 5450-5459, 5523`）。
- CUDA は1〜16行、HIP は `kTreeMaxM` 以下の行数で hash/print helper が動作する。上限を超える batch は helper が return し、出力しない（`engine/src/inkling2/cuda/ink_runner.cuh:1801-1806`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:5839-5845`）。
- CLI 引数や設定ファイルによる上書き・優先順位の実装は、この環境変数の読み取り箇所では確認できない。

## 実行時の詳細

値は CUDA の `InkCudaRunner::init` と HIP backend 初期化中に読み、フラグと GPU バッファに保持する。関数内 static cache や要求ごとの再読込はなく、初期化後にプロセス環境を変えても既存 runner の状態には反映されない（`engine/src/inkling2/cuda/ink_runner.cuh:2090-2108`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:739-742`）。子プロセスへの転送・上書きはこの読み取り経路にない。

CUDA は通常の `forward_seq` と tree の出力箇所で hash buffer を同期・ホストコピーして `[HASH]` 行を出す。`forward_batched` は中間 hash の記録呼び出しを通るものの、この関数内には `dbg_hash_print` 呼び出しがない。HIP は成功した `forward_batch` と tree verify の後に出力する。両者とも helper は GPU stream を同期し、行ごとに位置や token 等のメタデータと複数の16進 hash 値を出す。CUDA は hash slot 0..211、HIP は 0..202 を出力する（`engine/src/inkling2/cuda/ink_runner.cuh:1805-1814, 3691-3696, 3816-3820, 3823-3875`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1885-1887, 2484-2486, 5843-5853`）。

## ログと測定値

有効で、対象行数内かつバッファ確保に成功した出力行は stderr の `[HASH]` で始まり、`fwd` または `tree`、行数・行番号・位置・depth・anchor・token・parent のメタデータと hash 値が続く。既定で無効、無効値、行数上限超過ではこの行は出ない。CUDA の確保エラーは `strata-inkling CUDA error ...` の device error 経路を通り、HIP の確保失敗にはこの変数専用の警告はない（`engine/src/inkling2/cuda/ink_runner.cuh:1805-1814, 2102-2108`; `engine/src/inkling2/cuda/ink_cuda.cuh:34-42`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742, 5843-5853`）。

`docs/DETAILS.md` にこの変数の測定値や性能評価は見つからなかった。診断を有効にした場合の速度・メモリ影響は本調査では測定していない。

## 根拠

- 全参照検索では、実行時読み取りは CUDA `engine/src/inkling2/cuda/ink_runner.cuh:2102-2108` と HIP `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:740-742`。その他は診断用コメント、hash helper / kernel、または `terminal/data/settings-register.json` の設定メタデータだった。
- ハッシュ kernel は各 FP32 行の bit を対象にする診断用64 bit hash と説明されている（`engine/src/inkling2/cuda/ink_kernels.cuh:2277-2280`; `engine/src/inkling2/hip/ink_hip_ops.hip.h:4072-4075`）。
