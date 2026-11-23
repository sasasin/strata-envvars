# `STRATA_PF_P1A_L2`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の native MoE prefill で、`STRATA_PF_P1A=1` が選ぶ P1A カーネルの対象量子化ペアを広げるスイッチ。P1A の基本対象は gate/up `Q4_K` と down `Q5_1` で、この変数が有効なら `Q4_K` / `Q5_K` gate/up と `Q5_1` / `Q8_0` down の組み合わせを `p1a::takes()` が受け入れる。したがって、この変数だけでは P1A を有効にしない。`p1a_wanted()` が `STRATA_PF_P1A` と GPU 条件を満たし、対象 layer が実際の prefill 条件も満たす必要がある（`engine/src/prefill/moe_fused_iq.cu:3612-3628,3665-3668,3703-3715`; `engine/src/prefill/moe_p1a.cu:507-512`）。

## 値と判定

HIP ビルドの `p1a_l2()` は `std::getenv()` の結果が null でなく、かつ文字列全体がちょうど `"1"` の場合だけ true とする。整数変換はしない。明示的な空文字は設定済みでも false。大文字小文字・空白・後続文字を含めて文字列完全一致なので、`1 `、`1anything`、`true`、`0`、`false`、`-1` は false になる。非 HIP ビルドでは関数が常に false を返す（`engine/src/prefill/moe_fused_iq.cu:3623-3629`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP ビルド、P1A 判定時 | `p1a_l2()` は false。起動時の対象 GPU 既定値が適用されていれば、その前に `"1"` が設定される | `1`（文字列全体がちょうど `1`） | 空文字、`0`、`true`、`1 `、`1anything` |
| 非 HIP ビルド | `p1a_l2()` は false | なし | すべて（値を参照する HIP 専用処理がコンパイル対象外） |

既定値の注入は既存値の有無で決まり、値の真偽では決まらない。既に `STRATA_PF_P1A_L2` が存在すれば `set_default()` は上書きしないため、空文字や `0` も既定値を抑止する（`engine/src/core/arch_defaults.cpp:218-223,334-344`）。

## 有効になる条件

- **HIP 実行経路であること。** 起動時の `apply_arch_defaults()` 呼び出しは `STRATA_USE_HIP` の下にあり、P1A の読み取りも `__HIPCC__` の分岐内にある。CUDA-only ビルドではこのスイッチは P1A カーネルを選ばない（`engine/src/program/generate.cpp:4282-4286,4315`; `engine/src/prefill/moe_fused_iq.cu:3612-3629`）。
- **P1A の親スイッチと GPU 条件を満たすこと。** `STRATA_PF_P1A` も完全一致の `"1"` で、`dev_info().g11_wmma` が true の場合に限り `p1a_wanted()` が true になる。`g11_wmma` は `gfx1100` / `gfx1101` / `gfx1102` / `gfx1103` / `gfx1150` / `gfx1151` のデバイスで true になり得る。P1A_L2 単独での opt-in はできない（`engine/src/prefill/moe_fused_iq.cu:2858-2868,3612-3628`; `engine/include/strata/kernels/gfx_arch.hpp:28-32`）。
- **native MoE prefill で対象 layer があること。** `p1a::takes()` が受け入れるのは gate/up `Q4_K` または `Q5_K` と down `Q5_1` または `Q8_0` の直積。`STRATA_PF_P1A_L2` が false のときは `Q4_K` + `Q5_1` だけが対象（`engine/src/prefill/moe_p1a.cu:509-512`）。
- **その呼び出しに FP16 入力と FP16 down 出力が使えること。** prefill が native fused path で FP16 入力行を渡し、`g_dm16_want` が true、down rotation が無効、device が `g11_wmma`、layer の tile 数が 65,535 以下、FP16 の H 行が確保済みバイト数に収まる場合に P1A の gate/up と down を起動する。それらを満たさない呼び出しはこの枝を通らず既存経路へ進む（`engine/src/prefill/prefill.cpp:5774-5776,5830-5845`; `engine/src/prefill/moe_fused_iq.cu:3703-3715`）。
- **起動時の自動設定があるのは対象 GPU の限定経路。** AMD HIP の discrete `gfx1100` / `gfx1101` / `gfx1102` では `gfx11_discrete_wmma_env()` が `"1"` を既定値候補にする。Windows の integrated `gfx1151` でも integrated prompt set が有効なら同じ値が候補に入る。`STRATA_DEFAULTS=026`、`STRATA_GFX11_DEFAULTS` の先頭が `0`、または（discrete RDNA3 では）`STRATA_GFX11_WMMA_DEFAULTS` の先頭が `0` なら discrete 向け matrix-core 既定値群は作られない。Windows `gfx1151` の integrated 経路は `STRATA_IGPU_DEFAULTS` が先頭 `0` なら無効、`STRATA_IGPU_PROMPT_SET` の先頭 `1` / `0` が有効 / 無効を明示し、未指定なら有効になる。その他の対応 GPU では手動設定でのみこの変数が供給される（`engine/include/strata/core/gfx11_extra.hpp:27-36,87-109`; `engine/src/core/arch_defaults.cpp:120-138,172-180,193-213,302-344,406-420`; `engine/include/strata/core/defaults_026.hpp:21-29`）。

## 実行時の詳細

`generate.cpp` は HIP ビルドで device 0 のプロパティ取得に成功すると、起動時に `apply_arch_defaults()` を呼ぶ。対象の既定値テーブルを走査し、環境に既に同名があればその値を保持し、なければ Windows では `_putenv_s`、それ以外では `setenv(..., 0)` で `"1"` を設定する。discrete gfx11 の既定値は integrated GPU と判定された場合には適用しない。Windows integrated gfx1151 の既定値は別の integrated prompt set 経路で入る（`engine/src/program/generate.cpp:4282-4315`; `engine/src/core/arch_defaults.cpp:218-223,302-344,406-420`）。

P1A_L2 の値を読む実装は `p1a_l2()` の関数内 `static const bool` で、最初に呼ばれた時点のプロセス環境から一度だけ決まる。それ以降の環境変更はそのキャッシュに反映されない。呼び出し側は `p1a_wanted()` が true のときに layer の対象ペアを確認し、実行時には入力・down 出力・容量などの条件を満たした呼び出しだけ `moe_p1a.cu` の P1A gate/up と down を実行する（`engine/src/prefill/moe_fused_iq.cu:3623-3629,3665-3668,3703-3715`; `engine/src/prefill/moe_p1a.cu:509-512`）。

## ログと測定値

discrete gfx11 の起動時に Strata がこの値を新規設定し、同時に他の matrix-core 既定値も一つ以上設定した場合、stderr の既定値一覧に `P1A_L2` が含まれる。ユーザーがこの変数を事前に設定していた場合、その名前は一覧に追加されない。P1A の使用状況は最初の fused prefill chunk の最終 layer で一度報告される。少なくとも一つの layer で使われた場合の stderr 書式は `strata: prompt experts P1A (STRATA_PF_P1A=1): gate/up + down on the P1A kernels in %d of %zu layers (%s); today's kernels in %d (%s); %d not on the fused path in this chunk`。この時点で P1A を使った layer がない場合は報告行を出さない（`engine/src/core/arch_defaults.cpp:334-344`; `engine/src/prefill/prefill.cpp:2273-2308,5857-5861`）。

ソースコメントには Windows gfx1151 でのモデル別測定記述があるが、P1A_L2 単体の効果を切り分けた測定ではないため、ここではこの変数単独の速度・品質測定値としては扱わない（`engine/src/core/arch_defaults.cpp:202-210`）。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:3623-3629` — 値の取得、完全一致判定、HIP 以外での false。
- `engine/src/prefill/moe_fused_iq.cu:3665-3668,3703-3715` — P1A 親スイッチとの関係、ペア判定と実カーネル分岐。
- `engine/src/prefill/moe_p1a.cu:509-512` — P1A_L2 有効時に受け入れる量子化ペア。
- `engine/include/strata/core/gfx11_extra.hpp:27-36,87-109` — discrete RDNA3 の既定値とその無効化条件。
- `engine/src/core/arch_defaults.cpp:218-223,302-344,406-420` — 既存環境値の保持、既定値注入、stderr 通知、integrated GPU の適用経路。
- `engine/src/program/generate.cpp:4282-4315` — HIP ビルドの起動時における arch defaults 適用。
- `engine/src/prefill/prefill.cpp:2280-2308,5774-5776,5830-5861` — P1A 使用ログと prefill 側の入力・呼び出し条件。
- `engine/include/strata/kernels/gfx_arch.hpp:28-32`; `engine/src/prefill/moe_fused_iq.cu:2858-2868` — gfx11 WMMA 世代判定。
