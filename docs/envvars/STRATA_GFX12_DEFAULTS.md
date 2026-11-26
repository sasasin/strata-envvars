# `STRATA_GFX12_DEFAULTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

RDNA4 / gfx12 向けの Strata デフォルト群を止める共通スイッチ。各読取箇所は真偽値や数値として全体を parse せず、設定値の先頭文字が `0` かだけを見る。先頭が `0` なら、gfx12 の既定値注入、GDN chunk の自動選択、gfx12 での既定 Q8 hyper-connection 読み取り、既定 CPU prefill share、Linux HIP の裸の `~`--prefill auto`~` の chunk 上限引上げを、それぞれの条件下で抑える。これらは別々のコード経路で判定されるため、抑止範囲も経路ごとに異なる。たとえば `STRATA_HC_Q8=1` の明示指定はこの変数より優先する。

HIP の generate 起動時に `apply_arch_defaults()` が gfx12 用の環境変数群をプロセス環境へ補う。ユーザーが各個別変数を設定済みなら値を保持し、この変数が先頭 `0` の場合は gfx12 候補群を注入しない（`engine/src/core/arch_defaults.cpp:28-63,302-310,360-379`、呼出元 `engine/src/program/generate.cpp:4287-4320`）。

## 値と判定

すべての実読取箇所で、環境変数が未設定でなく先頭文字が `'0'` なら無効化する。文字列全体の比較や数値変換はない。unset、空文字、`1`、`true`、`false`、`00`、`0anything`、`0.5` は無効化しない値だが、`0`、`00abc`、`0 ` は先頭が `0` のため無効化する。大文字小文字、空白、数値としての妥当性は検査しない。根拠: `engine/include/strata/core/gfx12_extra.hpp:41-64`、`engine/src/core/arch_defaults.cpp:41-42,109-113,392-395`、`engine/src/core/native_dense.cpp:85-94`、`engine/src/prefill/kernels.cu:1906-1909`、`engine/src/program/generate.cpp:4547-4559`。

| 適用経路 | unset / 空文字 / 先頭が `0` 以外 | 先頭が `0` |
|---|---|---|
| HIP gfx12 arch defaults | 候補の既定値を注入 | gfx12 候補テーブルを空にする |
| gfx12 CPU prefill share | 他条件を満たせば既定で有効 | 既定有効を止める |
| gfx12 GDN 自動 chunk gate（`STRATA_GDN_CHUNKED` unset 時） | 30,000 token 以上で gate を通す | 自動 gate を止める |
| gfx12 の `STRATA_HC_Q8` 自動判定 | HIP gfx12 なら自動有効 | gfx12 の自動有効を止める |
| Linux HIP gfx12 の裸の `~`--prefill auto`~` | chunk 上限を 32,768 へ引上げ可能 | 引上げない（通常の 8,192） |

`STRATA_DEFAULTS=026` は別の条件で、gfx12 table の prompt 側 5 件は残し、decode 側追加を抑える（`engine/src/core/arch_defaults.cpp:43-62`）。個別環境変数が設定済みなら `apply_arch_defaults()` は上書きせず、空文字や `0` も設定済みとして保持する（同 `:360-379`）。裸の `~`--prefill auto`~` では `STRATA_GFX12_CHUNK` も別に判定され、完全一致 `"16"` は 16,384、先頭 `0` は引上げなし、それ以外は 32,768 候補となる（`engine/include/strata/core/gfx12_chunk.hpp:13-19`）。

## 有効になる条件

- arch defaults の注入と gfx12 CPU share は HIP 経路で使われる。generate の呼出しは `STRATA_USE_HIP` の guard 内である。gfx12 判定は `gfx_arch_is_gfx12()` による（`engine/src/program/generate.cpp:4287-4320`、`engine/src/core/arch_defaults.cpp:28-30`）。
- gfx12 arch table の prompt 既定候補は `STRATA_GDN_HEAD=1`, `STRATA_GDN_PP=2`, `STRATA_GDN_CONVL2=1`, `STRATA_GDN_NOY=1`, `STRATA_CVEC_FUSE=1`。`STRATA_DEFAULTS=026` でなければ、さらに `STRATA_ATTN_LANECELL=1`, `STRATA_ATTN_MERGE_V2=1`, `STRATA_TSUM=1`, `STRATA_EXPDEC=1`, `STRATA_SMALL_UNR=3`, `STRATA_GR_Q32_G=2`, `STRATA_GR_Q8_PFS=1` が候補（`engine/src/core/arch_defaults.cpp:43-62`）。別枠で `STRATA_HEAD_MIX_MULTI=1`, `STRATA_SELECT_WMMA=1` と `STRATA_SELECT_ALT_MIN_TOKENS=28672` を候補にする。Linux build では `STRATA_MMQ_KQ=1` も候補となる（`engine/include/strata/core/gfx12_extra.hpp:41-64`、platform macro は `engine/include/strata/core/gfx12_platform_defaults.hpp:8-15`）。MMQ 非搭載 build では別の案内となり、K-quant experts のないモデルには MMQ 既定の対象がない（`engine/src/core/arch_defaults.cpp:373-386`）。
- gfx12 CPU prefill share は、prefill が `applies` / `by_default` と判断し、`STRATA_PREFILL_CPU_SHARE` が未指定、かつ別の既定 share がまだ arm されていない場合に判定される。`STRATA_PREFILL_CPU_SHARE=0` など明示指定はこの既定経路に優先（`engine/src/prefill/prefill.cpp:3842-3854`）。
- GDN 自動 gate は `STRATA_GDN_CHUNKED` が unset または空文字（helper はどちらも `-1`）の場合に限り本変数を見る。非空値は `atoi` で変換され、`0` や `0abc` は 0 となって chunked dispatch を止め、非数値文字列も 0 になる（`engine/src/prefill/kernels.cu:1902-1909,2203-2223,2243-2265,3087-3099`）。自動 gate の閾値は `STRATA_GDN_CHUNKED_MIN`（未設定・空なら 30,000、設定時は `atoll`）で変更できる。Linux HIP 起動では可視 GPU がすべて gfx12 のとき、先に unset の `STRATA_GDN_CHUNKED` を `1` にするため、この場合は本変数だけでは chunked GDN を止めない。ユーザーの `STRATA_GDN_CHUNKED=0` は保持される（`engine/src/program/generate.cpp:4304-4320`、`engine/src/core/arch_defaults.cpp:278-290`）。
- `STRATA_HC_Q8` が unset または完全一致 `"auto"` のときだけ自動判定に進む。先頭が `1` なら明示有効、その他の非空値（`0`, `true`, `AUTO` など）は自動判定より先に無効化する。gfx1151 の HIP 既定判定が先にあるため、本変数は gfx1151 既定に作用しない（`engine/src/core/native_dense.cpp:48-98`）。
- 裸の `~`--prefill auto`~` の上限引上げは `STRATA_USE_HIP && !_WIN32` 経路で、`prefill_auto_bare`、`prefill_auto_cap == 0`、device 0 が gfx12、`STRATA_GFX12_CHUNK` が引上げを許す場合のみ。`--prefill auto:N`、明示 chunk、`STRATA_PREFILL_AUTO_MAX` 指定時はこの分岐に入らない。RAM guard により 32,768 候補は 16,384、さらに 8,192 へ下がり得る（`engine/src/program/generate.cpp:4000-4021,4537-4571,11280-11303`、`engine/include/strata/core/gfx12_chunk.hpp:13-22`）。

## 実行時の詳細

arch defaults は generate の GPU 情報取得後、他の engine switch が初回参照される前に呼ばれる。`set_default()` は Windows で `_putenv_s`、それ以外で `setenv(..., 0)` を使い、既存値を置き換えない。arch defaults は呼出し時に本変数を直接読む。根拠: `engine/src/core/arch_defaults.cpp:218-224,302-310,360-379`、呼出元 `engine/src/program/generate.cpp:4287-4320`。

GDN 自動 gate と `hc_q8_env()` は関数内 `static` に結果を保存するため、初回評価時の値を以後も使う（`engine/src/prefill/kernels.cu:1906-1909`、`engine/src/core/native_dense.cpp:52-99`）。GDN の chunked 有効判定も `gdn_recurrence_impl()` 内で static cache される（`engine/src/prefill/kernels.cu:3087-3096`）。CPU share と裸の auto chunk 上限は処理時に直接読む。実行中の環境変更を再評価する仕組みはない。arch defaults は現在のプロセス環境に機能別の既定値を設定し、この設定処理から子プロセスへの転送は行わない。

本変数が先頭 `0` でも、個別スイッチの明示値は保持される。特に `STRATA_HC_Q8=1` は独立した明示要求として自動判定を迂回する。arch default table が抑止されても、別の CLI / model / GPU 条件が成立しない機能が有効化されるわけではない。

## ログと測定値

本変数を無効値として警告する処理はない。gfx12 defaults が実際に注入された場合、対象候補が一つ以上あると次の stderr 行が出る。

- `strata: gfx12 (RDNA4): exact extra switches on by default (STRATA_GFX12_DEFAULTS=0 turns them off; a switch you set is kept): ...`（`engine/src/core/arch_defaults.cpp:360-370`）。
- MMQ: `strata: gfx12 (RDNA4): a model with K-quant experts (Unsloth UD-Q4/Q5/Q6_K_XL) reads its prompt on llama.cpp's MMQ kernels (+10..17% prompt speed on an R9700, first-token KL against the FP16 path about 0.03; STRATA_MMQ_KQ=0 or STRATA_GFX12_DEFAULTS=0 turns it off)`。MMQ 非搭載 build では `Strata's own kernels` を示す別行（`engine/src/core/arch_defaults.cpp:381-386`）。
- QSA scorer: `strata: gfx12 (RDNA4): the matrix-core QSA block scorer is on once a prompt is past 28,672 tokens (+5.7% prompt speed at 98K on an R9700, shorter prompts unchanged; the first-token KL against the warp kernel is 0.002 on average above 30K; STRATA_SELECT_WMMA=0 or STRATA_GFX12_DEFAULTS=0 turns it off)`。個別 `STRATA_SELECT_WMMA` が先頭 `0` の場合、この案内は出ない（`engine/src/core/arch_defaults.cpp:387-390`）。
- gfx12 CPU share が既定で arm された場合、`prefill: the CPU share is ON by default for prompt chunks up to ...` の行に本変数を含む停止条件が付く（`engine/src/prefill/prefill.cpp:3842-3854`）。
- gfx12 かつ `STRATA_GDN_CHUNKED` unset で本変数が先頭 `0` 以外なら、`strata: RDNA4 (gfx12): prompt chunks of 30,000+ tokens use the chunked GDN scan (STRATA_GDN_CHUNKED=0 turns it off)`。同変数が設定済みなら案内行は出ない（`engine/src/core/arch_defaults.cpp:392-395`）。
- bare-auto 上限引上げ時は `strata generate: gfx12: --prefill auto may take chunks up to ... (STRATA_GFX12_CHUNK=16 keeps 16384, =0 keeps 8192)`。本変数で抑止したこと自体を示す警告はない（`engine/src/program/generate.cpp:4552-4559`）。

ログ文字列に含まれる速度・KL 数値は、この調査で再測定した値ではない。

## 根拠

- 読み取り・値判定・候補: `engine/include/strata/core/gfx12_extra.hpp:41-68`、`engine/src/core/arch_defaults.cpp:28-63,109-116,360-405`。
- 起動、既定値設定と個別値の優先: `engine/src/program/generate.cpp:4287-4320`、`engine/src/core/arch_defaults.cpp:218-224,302-310,360-379`。
- CPU share: `engine/src/prefill/prefill.cpp:3842-3854`。
- GDN 自動 gate と Linux での明示デフォルト: `engine/src/prefill/kernels.cu:1902-1909,2203-2223,2243-2265`、`engine/src/core/arch_defaults.cpp:278-290`、`engine/src/program/generate.cpp:4304-4320`。
- Q8 hyper-connection: `engine/src/core/native_dense.cpp:47-99,247-260,289-295`。
- bare-auto chunk ceiling / CLI 条件: `engine/include/strata/core/gfx12_chunk.hpp:13-22`、`engine/src/program/generate.cpp:4000-4021,4537-4571,11280-11303`。
