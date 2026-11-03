# `STRATA_MMVF_CHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

CUDA の BF16/F32 MMVF にある `STRATA_SMALL_UNR` bit 0 の定数回 fast path と、通常の逐次 loop の累積値を診断比較します。対象変数を有効にすると、fast path の計算に加えて volatile load を使う通常 loop も実行し、各 thread の累積値を float の bit pattern で比較します。これは検査用の追加計算で、fast path 自体を有効にするスイッチではありません。

## 値と判定

環境変数の文字列全体や数値は parse せず、`getenv()` が返す文字列の先頭 1 文字だけを見ます。

| 値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| それ以外（`0`, `true`, ` 1` など） | 無効 |

有効・無効の結果は、`STRATA_SMALL_UNR` bit 0 が有効になった後、最初に `mmvf_fast()` が呼ばれた時に `static const bool` へ保存されます。その時点以降の環境変更は再評価されません。bit 0 が無効なら対象変数は読まれません。

## 有効になる条件

対象変数だけを設定しても診断は動きません。`mmvf_fast_bit()` が 0 以外を返す必要があります。

- `STRATA_SMALL_UNR` が設定されている場合、Strata は `atoi(value) & 1` を使います。たとえば `1` や `3` は bit 0 を有効にし、`2` は無効にします。数値として読めない先頭部分は `atoi` の規則に従います。この明示値は GPU による既定値より優先します。
- `STRATA_SMALL_UNR` が未設定の CUDA では、現在の GPU の compute capability を取得し、bit 0 の既定値を選びます。既定で有効なのは compute capability 12.0 かつ `STRATA_SM120_PERF` が有効で、`STRATA_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれでもない場合です。`STRATA_SM120_PERF` は未設定または `atoi(value) != 0` なら有効です。device 情報取得に失敗した場合は 0 です。未設定時の既定値は device ごとに cache されます。
- HIP コンパイルでは `mmvf_fast_bit()` が 0 を返すため、`STRATA_MMVF_CHECK` の読み取りに到達しません。
- bit 0 が有効でも、比較処理が実行されるのは kernel 側の `BLOCK_SIZE == 256 && n_in == 2560` fast path だけです。それ以外の行列サイズや block size では `fast == 2` が渡っても比較ブロックに入りません。multi-row kernel では実際の `n_tok` 範囲の行だけを比較します。`STRATA_MMVF_ROWS=1` によって行数条件を満たす multi-row 呼び出しが rows kernel に進む場合や、`multi_aux` の rows kernel を使う場合は `mmvf_fast()` を呼ばないため、この診断は使われません。

## 実行時の詳細

単一行と通常の multi-row MMVF launch は `mmvf_fast()` の戻り値を kernel に渡します。診断が有効なら戻り値は `2` です（通常の fast path は `1`）。対象形状の kernel は通常の unroll 済み計算の後、各 thread が fast path と同じ担当 pair を通常 loop で再走査して volatile load し、同じ順序の FMA で別の累積値を作ります。`mmvf_chk_note()` は比較した accumulator 数と bitwise 不一致数を device counter に加算し、最初の不一致について block、thread、`n_in`、両方の float bit pattern を記録します。

対象変数が有効になったとき `std::atexit()` に一度だけレポート関数を登録します。終了時に counter を読み出せた場合、stderr に `strata mmvf check: ...` の形式で比較数、不一致数、最初の不一致情報を出します。`cudaMemcpyFromSymbol()` が失敗した場合はその関数が何も出力せず戻ります。この診断変数専用の警告、終了コード変更、比較不一致時の例外・処理中断はありません。

## 根拠

- `src/kernels/cuda/native_bf16.cu:49-58,84-94,142-180` — 診断カウンター、volatile による再計算、bitwise 比較と記録。
- `src/kernels/cuda/native_bf16.cu:335-338` — 終了時の counter 読み出しと stderr の文言。
- `src/kernels/cuda/native_bf16.cu:341-370` — `STRATA_SMALL_UNR` bit 0 の判定、HIP の早期無効化、対象変数の先頭文字判定と static cache。
- `src/kernels/cuda/native_bf16.cu:312-333,387-410,413-475,478-504` — rows kernel の launch、rows 分岐による fast 判定の迂回、multi-row / single-row launch から fast mode を kernel に渡す経路。
- `include/strata/core/bw_dense_defaults.hpp:18-19`, `include/strata/core/sm120_series.hpp:30-40,58-59`, `include/strata/core/defaults_026.hpp:21-29` — 未設定時の SM120 既定条件、`STRATA_SM120_PERF` と `STRATA_DEFAULTS` の扱い。
- `docs/envvars/000_envvers.md:1473` — 候補一覧への掲載。`docs/DETAILS.md` には `STRATA_MMVF_CHECK` の説明は見当たりません。
