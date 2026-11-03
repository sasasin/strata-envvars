# `STRATA_PA_RPF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

HIP の matrix-core prompt-attention kernel で、次 chunk の ID と page-table の読み出しを現在の chunk の計算に先行させる RPF（read prefetch）経路を選びます。既定では有効です。これは実験用の kernel variant で、Strata のコメントは読み出し位置を変え、算術と出力 bits は同じとしています（`src/kernels/cuda/qsa_prompt_attn.cu:1961-1965`）。

## 値と判定

`pa_launch()` 内の `static const bool` 初期化で `std::getenv()` を一度呼び、値全体の parse はせず先頭文字だけを判定します（`src/kernels/cuda/qsa_prompt_attn.cu:2301-2309`）。

| 環境値 | RPF 選択 |
| --- | --- |
| 未設定 | 有効 |
| 空文字 | 有効（設定値の先頭が `\0` で、`'0'` ではない） |
| 先頭文字が `0` | 無効。`0`、`0anything` など |
| それ以外 | 有効。`1`、`true`、`false`、` 0` など |

数値変換、空白除去、大文字小文字変換、文字列全体との比較はありません。負値を含む `-1` も先頭が `0` ではないため有効です。コマンドライン引数による上書きはこの読み取り箇所にはありません。

## 有効になる条件

値が有効でも、`pa_launch()` が呼ばれる HIP WMMA prompt-attention 経路に入らなければ効果はありません。

- この WMMA 実装は `__HIPCC__` のみでコンパイルされます。対象アーキテクチャ macro は gfx1200/1201 と gfx1100/1101/1102/1103/1150/1151 です。それ以外は `STRATA_PA_WMMA=0` となり、この body は利用できません（`src/kernels/cuda/qsa_prompt_attn.cu:1885-1905`）。
- HIP WMMA が `STRATA_HIP_WMMA` と device 条件で選択される必要があります。gfx11 は `STRATA_HIP_WMMA=1` が必要です。gfx12 は Linux 既定または明示設定で選択され、`auto` では query 数などの閾値によって選択されます。mode が off、対象外 device、または過去の WMMA launch failure 後は利用されません（`src/kernels/cuda/qsa_prompt_attn.cu:2235-2249,2285-2294`）。
- prompt-attention 呼び出し側の pool が Q8 K/V と scale を持ち、Q4 pool がなく、head dimension・head 数が kernel geometry に一致し、`cap > 0`、ID・steps・page table が有効である必要があります。gated 経路も同じ WMMA launcher に到達します（`src/kernels/cuda/qsa_prompt_attn.cu:2445-2457,2494-2502`）。
- 呼び出し元は prefill の QSA attention で gated 経路または通常の `qsa_prompt_attn_batch()` を試します。`STRATA_PROMPT_ATTN_OLD` が設定されると gated 融合は使わず、通常経路も古い attention を指定します（`src/prefill/prefill.cpp:4383-4404,7514-7521`）。

通常の CUDA prompt-attention kernel にはこの RPF 選択がありません。`STRATA_PA_RPF` を設定しても、それだけで HIP WMMA 経路を有効にはしません。

## 実行時の詳細

読み取り結果は `pa_launch<SPLIT, GATE>` の各関数テンプレート specialization にある関数ローカル `static const bool` に保存されます。各 specialization の初回呼び出し時に環境を読み、その後は同じ specialization について再読込しません。初回評価後の環境変更はその specialization の選択に反映されません（`src/kernels/cuda/qsa_prompt_attn.cu:2301-2309`）。

RPF 有効時は `prompt_attn_wmma_kernel<SPLIT, GATE, true, TR>` を起動し、chunk ごとに現在 chunk の row を fetch した後、次 chunk の row を `row_of(ci + 1)` で先に求めてから現在 chunk を計算します。無効時は `row_of(ci)` を fetch してからその chunk を計算する kernel variant を使います。`TR` は別の `STRATA_PA_TRIM` 設定から選ばれます（`src/kernels/cuda/qsa_prompt_attn.cu:2025-2036,2181-2197,2297-2309`）。

この変数に固有のログ、警告、終了処理はありません。WMMA kernel launch の `cudaGetLastError()` が失敗すると、stderr に `qsa_prompt_attn_batch (wmma): <error>; the FP32 prompt attention runs from here on` を出し、WMMA を以後無効にして呼び出し元へ失敗を返します。prefill 側は通常の decode attention 経路へ fallback します（`src/kernels/cuda/qsa_prompt_attn.cu:2365-2371,2285-2287`; `src/prefill/prefill.cpp:4403-4416,7519-7525`）。この失敗処理は RPF 固有ではありません。

## 根拠

- 全候補参照と RPF kernel 本体: `src/kernels/cuda/qsa_prompt_attn.cu:1961-1965,2181-2197,2297-2309`。
- HIP build macro、device・pool 条件、WMMA の選択と fallback: `src/kernels/cuda/qsa_prompt_attn.cu:1885-1905,2235-2249,2285-2294,2445-2457,2494-2502,2365-2371`。
- prefill からの呼び出しと上位 fallback: `src/prefill/prefill.cpp:4383-4416,7514-7525`。
- `docs/DETAILS.md` に `STRATA_PA_RPF` 固有の説明・測定値は見つかりませんでした。コードコメントの「同じ出力 bits」は実装コメントの記載として扱い、独立した測定・検証結果としては記載していません。
