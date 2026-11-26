# `STRATA_SM61_TABLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

sm_61（例: Tesla P40 / P4、GTX 10 系）で、二つの CUDA 経路にある専用テーブルを既定で使うかを切り替える。`0` を指定すると、grouped expert は通常の CUDA layout（expert mode 0）を選び、dense matvec は `native_mmvq` の通常 kernel に戻る。未設定または `atoi` の結果が非 0 なら、expert は条件を満たすと mode 8 を選び、dense matvec は sm_61 用 interleaved table (`kIlRows_61` / `kIl1Rows_61`) を利用可能にする。読み取り箇所は `engine/src/kernels/cuda/iq_kernels.cu` の `exp_mode()` と `engine/src/kernels/cuda/native_mmvq.cu` の `sm61_table_on()`。前者は expert gate/up の layout 選択、後者は interleaved MMVQ kernel の対応判定に使われる（同ファイル:4201-4214, 4218-4252）。

## 値と判定

両箇所とも `std::getenv` で取得し、設定されていれば `std::atoi` の戻り値が 0 かどうかで判定する。文字列全体の妥当性確認や `true` / `false` の解釈はない。空文字、数字で始まらない文字列、`0`、`0anything` は `atoi` が 0 を返すため無効。`1`、`-1`、`2`、`1suffix` のように先頭の数値部分が非 0 になる値は有効。先頭空白の後の数値も `atoi` の規則で変換され、大文字小文字は関係しない。変換可能な数値範囲外の文字列に対する `atoi` の結果は C/C++ の仕様上保証できないため、値として依存できない。読み取りと判定は `iq_kernels.cu:6790-6791`、`native_mmvq.cu:4201`。

| 実行経路 | 未設定 | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| grouped expert の `exp_mode()`、GPU 属性が sm_61 | mode 8 の候補 | `atoi(value) != 0`（例: `1`, `-1`, `1suffix`） | `atoi(value) == 0`（例: 空文字, `0`, `0anything`, `true`） |
| CUDA interleaved MMVQ、GPU 属性が sm_61 | 専用 table を許可 | `atoi(value) != 0` | `atoi(value) == 0` |

## 有効になる条件

- grouped expert 側では `STRATA_EXP_LAYOUTS` が有効で、現在デバイスの compute capability が major 6 / minor 1 であること。`STRATA_HIP_GFX906` ビルドでは `exp_mode()` が早期に既定 mode を返すため、この sm_61 判定には進まない（`engine/src/kernels/cuda/iq_kernels.cu:6764-6803`, `7196-7204`）。
- expert mode 8 を選んでも、fused gate/up kernel は `!nib_layout(L)`、`L.had_block == 0`、`L.n_embd <= 4096`、対象 gate/up 型、`L.n_ff % 32 == 0` などの条件が必要。verify 用の一部 CUDA 呼び出しでは `grid_groups > 0 && grid_groups < cap_groups` のとき mode 0 に固定される（同ファイル:7200-7214）。他の型や条件では別の expert kernel 経路になる。
- interleaved MMVQ 側は CUDA 実装でのみ機能し、`1 <= ncols <= 8`、multi-column exact が有効、型が IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K のいずれかで、該当する sm_61 table の行数が 0 でないことが必要（`engine/src/kernels/cuda/native_mmvq.cu:3901-3907`, `4025-4029`, `4218-4227`）。
- `g_tune_rows == 0` の通常実行で、dense INT8 Tensor Core GEMM が対象 shape を処理できる場合は interleaved MMVQ が辞退し、呼び出し元は通常 `native_mmvq` に進む（同ファイル:4218-4227）。
- 呼び出し元が interleaved 経路を要求し scratch 等を用意する必要もある。例として shared expert は interleaved scratch と 2 token 以上を確認し（`engine/src/kernels/cuda/shared_expert.cu:229-256`）、split head と DFlash2 head にも対応可否による分岐がある（`engine/src/core/native_head.cpp:449-477`, `engine/src/core/dflash2.cpp:596-604`）。

## 実行時の詳細

expert 側では `exp_mode()` がデバイス属性を調べ、`per_dev[dev]` に mode を保存する。sm_61 なら unset または `atoi != 0` で mode 8、`atoi == 0` なら通常の CUDA layout である。`STRATA_EXP_MODE` の `atoi` 結果が 0 以上なら明示 mode として優先し、`STRATA_SM61_TABLE` の sm_61 既定選択は使われない。負の値（未設定時の -1 を含む）はデバイス別既定の選択へ進む。mode 8 は条件を満たす gate/up に fused kernel を選び、それ以外の処理条件では LDS または通常 layout 等の分岐に従う（`engine/src/kernels/cuda/iq_kernels.cu:6763-6803`, `7205-7214`, `7215-7238`, `7270-7284`）。

interleaved MMVQ 側では `il_arch_ok()` がデバイス ordinal ごとの `ok[16]` を一度決めると、その結果を保持する。sm_61 の `STRATA_SM61_TABLE` 判定もその初回判定時だけ行われる。table が許可され、型・shape の行数が非 0 なら `native_mmvq_il()` が interleaved kernel を launch し、対応しない場合は同関数内で `native_mmvq()` に fallback する（`engine/src/kernels/cuda/native_mmvq.cu:4201-4214`, `4218-4252`）。環境値をプロセス実行中に変更した場合に反映する再評価経路はない。設定値は CLI 引数や設定ファイルで上書きするコードを確認できず、expert 側では `STRATA_EXP_MODE` が明示 mode として優先する。

この変数の無効化自体による警告・エラー出力はない。interleaved 対応外の形状も通常 `native_mmvq` に fallback する。expert 側で mode 8 が無効になる場合も通常 layout 側の選択に進む（`engine/src/kernels/cuda/native_mmvq.cu:4230-4234`, `engine/src/kernels/cuda/iq_kernels.cu:7196-7204`, `7241-7284`）。

## ログと測定値

この変数の値や無効化理由を表示する専用の stderr / stdout ログは読み取り経路にない。ソースコメントには測定記録があるが、実行時の保証ではない。`iq_kernels.cu:6787-6791` は Tesla P40 の expert mode 8 について `native_expert_bench` の IQ3_S / IQ3_XXS / IQ2_S / IQ4_XS の時間例と bitwise equal と記し、`native_mmvq.cu:3897-3906` は Tesla P40 の interleaved table について `mmvq_il_parity --bench --emit-table` の 3 run と比較例を記している。これらはソースコメント上の過去の測定であり、ここで再測定した値ではない。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:6763-6803` — expert mode の `STRATA_EXP_MODE` 優先、sm_61 判定とデバイス別 cache。
- `engine/src/kernels/cuda/iq_kernels.cu:7196-7214`, `7215-7238`, `7270-7284` — expert mode 選択、mode 8 kernel の条件と dispatch。
- `engine/src/kernels/cuda/native_mmvq.cu:3897-3907`, `4025-4053`, `4065-4077` — sm_61 専用 table と arch table。
- `engine/src/kernels/cuda/native_mmvq.cu:4201-4214`, `4218-4252` — 値判定、cache、対応判定と通常 kernel への fallback。
- `engine/src/kernels/cuda/shared_expert.cu:229-256`, `engine/src/core/native_head.cpp:449-477`, `engine/src/core/dflash2.cpp:596-604` — 呼び出し元の適用条件。
