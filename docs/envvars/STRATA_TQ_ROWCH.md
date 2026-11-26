# `STRATA_TQ_ROWCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA trellis 型 expert（型 ID 144〜146）の staged gate/up・down カーネルで、1 CUDA block に割り当てる行チャンク数を調整する値です。行チャンク数は launch grid の x 寸法と各 block が処理する行の stride に使われ、ゲート・up または down の計算結果そのものを選ぶ設定ではありません。CUDA 以外の CPU、Metal、SYCL 実装にはこの読み取り箇所はありません。読み取りと launch は `engine/src/kernels/cuda/iq_kernels.cu` の `tq_row_chunks()`、`launch_gu()`、`native_expert_grouped()` にあります（同ファイル:3763-3771, 4541-4567, 7340-7343）。

## 値と判定

`tq_row_chunks()` の初回呼び出しで `std::getenv` を呼び、未設定なら 4、設定済みなら `std::atoi` の結果を使い、1 未満は 1、32 超は 32 に clamp します。関数内 `static const int` に保存されるため、以降の呼び出しでは環境を読み直しません（`engine/src/kernels/cuda/iq_kernels.cu:3764-3770`）。

| 条件 | unset | 有効になる値の例 | 無効・端の値の例 |
|---|---|---|---|
| `tq_row_chunks()` が呼ばれる経路 | 4 | `1`〜`32` は整数値をそのまま使用（例: `4`, `32`） | 空文字、`0`、`-2`、`n/a` は `atoi` が 0（または負値）を返し、1。`33` は32。`4tail` は先頭の数値部分を読み4。 |

変換は文字列全体の検証ではなく `atoi` です。空白や符号なども C の `atoi` の変換規則に従い、大文字小文字の判定はありません。数値として表現できない大きさの文字列に対する `atoi` の結果は、このコードでは別途検査されません（同ファイル:3765-3769）。

## 有効になる条件

- `STRATA_TQ_ROWCH` は GPU grouped expert 経路から `tq_row_chunks()` が呼ばれたときだけ影響します。別の `STRATA_TQ_ROWCH` 読み取り箇所、CLI 引数による上書き、設定ファイルからの上書きはありません（`engine/src/kernels/cuda/iq_kernels.cu:3764-3770`）。
- Gate/up では split trellis 型の `launch_gu()` が staged-grid 分岐に入り、`tq_stage_on()` と `g_stage_grid` が有効なときに値を使って x grid を縮めます。`tq_stage_on()` は `STRATA_TQ_STAGE` が未設定または空文字なら CUDA compute capability 6.1 未満で自動的に有効になり、空でない設定値は先頭文字が `0` 以外なら有効です（したがって `false` も有効扱い。`STRATA_IQ_STAGE_GRID=0` なら無効）。HIP では自動有効化されませんが、`STRATA_TQ_STAGE` を明示的に有効値にするとこの関数の明示設定分岐は有効になり得ます（同ファイル:3726-3744, 4550-4567）。
- Gate/up の `STRATA_TQ_SUB8` 経路（主に CUDA で `tq_sub8_on()` が真、かつ型144/145の行形状が160 dotsのとき）は固定 grid を使い、`STRATA_TQ_ROWCH` を参照しません。`tq_sub8_on()` は HIP では常に false です。また `STRATA_TQ_STAGE=0`、`STRATA_TQ_SUB8=0`、`STRATA_IQ_STAGE_GRID=0`、`STRATA_NO_SUB16_GU` などで sub8/staging の条件が外れるとその専用経路は使われません（同ファイル:3746-3761, 4551-4567）。
- Down では `tq_sub8` が真の場合だけ `tq_row_chunks()` を grid 算出に使います。条件は down 型が144または146、`n_ff == 640`、旧カーネルと `STRATA_NO_SUB16_GU` が無効で、`tq_stage_on()` または `tq_sub8_on()` が真であることです。それ以外は down の `tq_ch` は1です。HIP の自動 sub8 は無効であるため、この down grid 調整は通常 CUDA の該当形状で使われます（同ファイル:7340-7343）。
- CUDA/HIP の expert dispatch が trellis 用 native grouped kernel に到達する必要があります。別の実装・layout が選ばれて `launch_gu()` / down launch を通らない呼び出しでは、この設定による差はありません（同ファイル:7178-7316, 7340-7404）。

## 実行時の詳細

Gate/up の staged trellis kernel では、元の grid.x を `ceil(grid.x / tq_row_chunks())` にし、各 block が `blockIdx.x` から `gridDim.x` ずつ行チャンクを進めて処理します。Down の対象形状では同様に、32行チャンクの数を `tq_ch` でまとめる形で grid.x を算出し、カーネル内の行ループが同じ stride で複数チャンクを処理します（`engine/src/kernels/cuda/iq_kernels.cu:2252-2276, 2438-2459, 4563-4567, 7340-7343`）。この値は block の割り当て方を変えます。Strata のソースコメントは同じ行和・計算順序になると説明していますが、この環境変数ごとの性能や生成結果の測定値は確認できません。

値は最初に `tq_row_chunks()` が呼ばれた時点で static に確定します。プロセス実行中に環境を変更しても再読み込みされません。読み取り値だけを理由に出すログや警告はありません。kernel launch 後のエラーは呼び出し側の `check()` が `stderr` に `<処理名>: <CUDA error string>` を出して `exit(1)` しますが、これは `STRATA_TQ_ROWCH` 固有の検証・エラーではありません（同ファイル:47-50, 7316, 7347-7353, 7384）。

## ログと測定値

この変数の値や採用チャンク数を出力するログはありません。`docs/DETAILS.md` と trellis 関連資料には trellis kernels/staging の説明や別設定の測定値はありますが、`STRATA_TQ_ROWCH` 固有の測定値は見つかりませんでした。別設定の性能値を本変数の効果としては扱いません。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:3726-3744` — staged codebook の判定と CUDA/HIP・デバイス条件。
- `engine/src/kernels/cuda/iq_kernels.cu:3746-3771` — sub8 条件および変数の読み取り、変換、clamp、cache。
- `engine/src/kernels/cuda/iq_kernels.cu:2252-2276, 2438-2459` — block 内の行チャンク反復。
- `engine/src/kernels/cuda/iq_kernels.cu:4541-4567, 4622-4636, 7340-7343` — gate/up・down の dispatch と grid 算出。
- `engine/src/kernels/cuda/iq_kernels.cu:47-50, 7316, 7347-7353, 7384` — launch error の観測経路。
