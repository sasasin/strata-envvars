# `STRATA_ATTN_DAILY`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の QSA decode attention で、chunk 計算に `attn_chunk_kernel_pre75`（Daily 由来の実装）を選ぶかを指定します。有効時は merge にも `attn_merge_v2_kernel` が既定で選ばれます。CUDA の全カードで明示的に有効化できますが、unset の場合は compute capability 12.0（sm_120）だけで既定有効です。HIP では `daily_attn()` が常に false を返すため、この変数による切り替えはありません。

対象の decode attention は、逐次 1 query の `qsa_decode_attn_step` のほか、複数 query の batch、slot、row 経路から呼ばれます。slot 経路は PR #540 の kernel を使う場合、slot 一括 kernel を使わず batch 呼び出しへ fallback します。

## 値と判定

CUDA 実装は、最初に `daily_attn()` が呼ばれた時に環境変数を一度読み、プロセス内の static 値に保存します。値が設定されている場合は文字列全体が厳密に `1` と一致する時だけ有効です。

| 値 | `daily_attn()` の結果 |
|---|---|
| unset | 現在の CUDA device が sm_120 で、`STRATA_SM120_PERF` が無効化していない場合に有効。それ以外は無効 |
| `1` | 有効（全 CUDA card） |
| `0`、空文字、`01`、`1x`、`true` など | 無効。unset 時の sm_120 既定判定も行わない |

未設定時の sm_120 判定では `STRATA_SM120_PERF` も static cache されます。同変数が未設定なら有効、設定時は `atoi(value) != 0` なら有効です。そのため `STRATA_SM120_PERF=0` なら sm_120 での既定有効化は止まります。`STRATA_ATTN_DAILY` に何らかの値（空文字を含む）を明示すると、sm_120 既定値より優先されます。

## 有効になる条件

- この切替の実装は CUDA の `src/kernels/cuda/qsa_decode_attn.cu` にあります。HIP ビルドでは `daily_attn()` は常に false です。
- CUDA では PR #540 の kernel がビルドされます。CUDA の通常ビルドでは `pre75_attn()` は `daily_attn()` の結果を使います。`STRATA_EXPERIMENTAL_SM60` ビルドでは、Daily kernel が無効でも compute capability が sm_75 未満なら PR #540 kernel が選ばれます。
- `STRATA_ATTN_PRE75=0` は PR #540 kernel の選択を止めます。したがって `STRATA_ATTN_DAILY=1` でも chunk kernel の切替が抑止されます。`STRATA_ATTN_PRE75` の他の値判定は同ファイルの `pre75_attn()` に従います。
- `STRATA_ATTN_MERGE_V2` が空でない値として設定されていれば、その `atoi(value) != 0` の結果が merge 選択に優先します。未設定または空文字なら `STRATA_ATTN_DAILY` の判定に追従します。
- sm_120 以外のカードでは、変数 unset 時の `STRATA_SM120_PERF` による既定判定は適用されません。ただし `STRATA_ATTN_DAILY=1` の明示指定はカードを問わず有効です。

## 実行時の詳細

`daily_attn()` は変数が設定済みなら厳密な `1` 判定を返し、unset なら CUDA の現在 device の compute capability を取得して `strata::sm120_default()` を判定します。device 情報の取得に失敗した場合、または device ordinal が 0–63 の範囲外なら false です。unset 時の device ごとの結果も static 配列に cache されます。CUDA 環境変数をプロセス起動後に変更しても、最初の評価後は反映されません。

`pre75_attn()` が true になると batch chunk pass は `attn_chunk_kernel_pre75` を選択します。通常の CUDA ビルドでは `STRATA_ATTN_DAILY=1` が全カードでこの選択を有効にします。merge 関数は `STRATA_ATTN_MERGE_V2` に明示的な非空値がなければ `daily_attn()` の結果を使います。`qsa_decode_attn_batch()` と `qsa_decode_attn_step()` はこの merge 選択を使います。slot batching は `pre75_attn()` が有効な場合に一括 slot kernel を使わず、query ごとの batch 経路へ戻ります。

別に、CUDA の起動処理は全ての可視 GPU が同じ compute capability である場合に限り、sm_86 / sm_60 用の既定 switch 群を適用します。その群には `STRATA_ATTN_DAILY=1` が含まれ、`STRATA_SM86_PERF=0` または `STRATA_SM60_PERF=0` で該当群を止められます。ユーザーが `STRATA_ATTN_DAILY` を設定済みなら値を上書きせず、未設定時だけ `1` を設定します。設定時には stderr に有効化した switch 名を含む `strata: sm_86 (Ampere)...` または `strata: sm_60 (Pascal)...` のログを出します。これは起動時に環境値を設定する実装であり、kernel 内の環境変数読み取りより先に実行されます。

## 資料との照合

`docs/DETAILS.md` は 0.1.45 の CUDA opt-in 測定として、RTX 3060 / RTX A4000 での結果をそれぞれ +3.2%（5/5） / +0.7% と記載しています。同資料の見出しは「all off unless you set them」としていますが、現 HEAD には sm_86 / sm_60 用起動時既定値があり、sm_120 でも unset 時の既定有効化があります。したがって、その表は当該測定時の opt-in 設定を説明する資料として扱い、現 HEAD の全カード既定動作の根拠にはしていません。`sm120_series.hpp` のコメントは RTX PRO 5000 Blackwell 72 GB、IQ3_S、全 expert VRAM resident の測定で、この switch を含む組み合わせの verify round が 13.70 ms から 12.23 ms になったと記載しています。個別 switch の寄与を示す値ではありません。

## 根拠

- `src/kernels/cuda/qsa_decode_attn.cu:832-860`: CUDA/HIP 分岐、値の完全一致判定、sm_120 既定値、device ごとの cache。
- `src/kernels/cuda/qsa_decode_attn.cu:862-900`: `STRATA_ATTN_PRE75` とビルド条件による chunk kernel 選択。
- `src/kernels/cuda/qsa_decode_attn.cu:925-933, 1023-1038, 1054-1065, 1209-1227`: merge の優先順位と batch/step の kernel 呼び出し。
- `src/kernels/cuda/qsa_decode_attn.cu:1072-1127`: slot 経路が PR #540 kernel の場合に一括処理を断念する条件。
- `include/strata/core/sm120_series.hpp:28-41`: `STRATA_SM120_PERF` と sm_120 既定判定。
- `src/core/nv_defaults.cpp:18-35,52-70`, `src/program/generate.cpp:2800-2816`: sm_86 / sm_60 switch の既定値、上書き回避、診断ログと適用時期。
- `docs/DETAILS.md:2502-2511`, `include/strata/core/sm120_series.hpp:1-18`: 資料にある測定条件と主張。
