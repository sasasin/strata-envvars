# `STRATA_PF_FUSED_IQ2S`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

HIP の gfx12 (RDNA4) で、native IQ prompt fused kernel の対象に IQ2_S と IQ4_XS の gate/up 層を含める既定値を切り替えます。CUDA の native fused kernel 選択にも同じ既定判定が使われ、Linux の SM 12.0・80 SM 以上で IQ2_S / IQ4_XS gate/up を既定対象にする判定に関与します。`STRATA_PF_FUSED=0` は全 fused prompt kernel を無効にし、`STRATA_PF_FUSED` を明示的に `1` にすると、この変数による既定対象の絞り込みを迂回して、対応する native 形式を opt-in できます。

対象は prompt の MoE expert 計算です。対応層では GGUF block を読む Strata の native int8 kernel が MMQ 経路に代わって選ばれます。decode の設定ではありません。実装は `src/prefill/moe_fused_iq.cu`、呼び出し側の layer 選択は `src/prefill/prefill.cpp` にあります。

## 値と判定

数値 parse や文字列全体の比較はせず、環境文字列の先頭文字が `'0'` かだけを見ます。空文字は設定済みでも先頭文字が `\0` のため、このスイッチでは OFF になりません。

| `STRATA_PF_FUSED_IQ2S` | `gfx12_iq2s_default()` の判定 |
|---|---|
| 未設定 | Linux では ON、Windows では OFF |
| 空文字 | Linux では ON、Windows では OFF |
| 先頭が `0`（例 `0`, `0abc`） | OFF |
| その他（例 `1`, `true`, `false`, `2`, ` 0`） | Linux では ON、Windows では OFF |

この判定は `STRATA_PF_FUSED` も読み、そちらが先頭 `0` のときも OFF にします。`STRATA_PF_FUSED` の明示値は native kernel の選択時にも優先されます。

| `STRATA_PF_FUSED` | `STRATA_PF_FUSED_IQ2S` の役割 |
|---|---|
| 未設定または空文字 | gfx12 の既定判定に適用。`STRATA_PF_FUSED_IQ2S=0` で IQ2_S / IQ4_XS の既定経路を止められる |
| 先頭が `0` | 全 native fused 経路が無効。対象変数を有効にしても使われない |
| 先頭が `1` | 明示 opt-in 経路。対象変数による既定形式の絞り込みを通らず、他の条件を満たす対応形式で使える |
| その他の非空値 | `native_supported()` では無効扱い（先頭が `1` でないため）。対象変数は既定判定に適用されるが、全体 fused は有効にならない |

`STRATA_PF_FUSED` の判定は未設定または空文字を同じ既定状態として扱います。非空なら先頭文字 `1` だけが明示 opt-in、それ以外は無効です。`STRATA_PF_FUSED_IQ2S` 自体は先頭 `0` 以外の文字を有効側として扱います（大文字小文字・空白・後続文字は検査しません）。根拠: `src/prefill/moe_fused_iq.cu:1977-1985,1988-2003`。

## 有効になる条件

既定経路（`STRATA_PF_FUSED` 未設定または空文字）では、次の条件が必要です。

- `kGfx12PromptDefaultsOn` が true であること。実装では Linux が true、Windows が false です。
- 対象層の gate/up 形式が IQ2_S または IQ4_XS であること。このスイッチは IQ2_XXS / IQ2_XS を追加しません。
- device が native kernel 対応であり、down 形式も `d_covered_on()` が認めること。IQ2_S / IQ4_XS は `gu_covered()` に含まれますが、down 側の形式判定も別に行います。
- 複数 GPU の peer portable 経路、hadamard-folded 層、stream-all 以外の小さい chunk など、呼び出し側が native fused 経路を選ばない条件に当たらないこと。

`STRATA_PF_FUSED=1` の明示 opt-in はこの変数による Linux 既定 gate を迂回しますが、device / 形式対応条件は残ります。CUDA では既定経路の形式判定後、SM 12.0・80 SM 以上などの device 条件も必要です。HIP では `d.w12` が gfx12 を表し、明示 opt-in の場合も `requested() || d.w12` の判定に進みます。`STRATA_PF_FUSED_NATIVE=0` は native packs の経路を別途無効にします。小さいカード用の `pf_fused_override()` が 0 の場合も `native_supported()` は false です。根拠: `include/strata/core/gfx12_platform_defaults.hpp:10-16`, `src/prefill/moe_fused_iq.cu:1873-1890,1988-2032`, `include/strata/prefill/moe_fused.hpp:36-45`, `src/prefill/prefill.cpp:4535-4541`。

## 実行時の詳細

`gfx12_iq2s_default()` は関数内の `static const bool` を初回呼び出し時に初期化し、`STRATA_PF_FUSED_IQ2S` と `STRATA_PF_FUSED` の値を cache します。したがって、その呼び出し後にプロセス環境を変更してもこの既定判定は再評価されません。`native_supported()` も `STRATA_PF_FUSED` と `STRATA_PF_FUSED_NATIVE` を関数内 static に保存します。

`native_supported()` が true でも、prefill の layer loop は `stream_all`、peer 不使用、native expert layout、folded gate/up と down がないことを確認してから `fused_nat` を選びます。選択されると activation を int8 化し、native experts kernel を起動します。選ばれない対応層は MMQ または FP16 経路に残ります。fused 経路を使った場合、stderr に一度 `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` が出ます。このログ文字列は IQ2S 専用スイッチ名を表示しません。対象変数だけを理由にした警告やエラー出力はありません。根拠: `src/prefill/moe_fused_iq.cu:1977-1985,1988-2032`, `src/prefill/prefill.cpp:4535-4584`。

HIP gfx12 では同じ判定値が既定 CPU prefill share の chunk 上限にも使われます。`gfx12_iq2s_default()` が true なら share limit は 1,536 token、false なら一般の新上限（`kShareLimitNew`、3,072）です。CPU share の起動条件を満たすと stderr に `prefill: the CPU share is ON by default ...` が出ます。これは fused kernel の実行を保証するものではなく、CPU share の既定上限選択です。根拠: `include/strata/prefill/share_rules.hpp:24-29`, `src/prefill/prefill.cpp:2845-2867`。

`STRATA_PF_FUSED=1` があると native kernel 選択は IQ2S 変数の既定 gate を迂回しますが、CPU share limit の計算は `gfx12_iq2s_default()` の値を使い続けます。そのため、たとえば `STRATA_PF_FUSED=1 STRATA_PF_FUSED_IQ2S=0` では対象 fused kernel が選択可能でも、CPU share の既定上限は fused IQ2S 用の 1,536 ではなく 3,072 になります。

## 根拠

- 候補名の実コード読み取りは `src/prefill/moe_fused_iq.cu:1977-1985` のみ。`include/strata/prefill/moe_fused_iq.hpp:32-34` は説明コメントと宣言で、追加の読み取り箇所ではありません。
- CUDA/HIP の fused IQ 実装を build source に含む箇所: `CMakeLists.txt:2298-2302,2542-2567`。
- 関連資料 `docs/DETAILS.md:1052` は fused prompt experts の全体既定を説明しています。個別の IQ2_S / IQ4_XS 追加条件と優先関係は、上記ソース実装を根拠にしています。
