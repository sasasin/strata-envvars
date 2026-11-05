# `STRATA_GFX12_RING`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

HIP の prompt prefill で、gfx12 向けに matrix-core attention が要求されているときに使う streamed expert ring の深さを既定ルールから切り替えます。条件を満たすと、chunk 長が 6,144 token 以下なら最大 256 slots、6,144 超から 12,288 未満なら最大 192 slots、12,288 以上なら 96 slots です。環境変数が設定されていると、この gfx12 向け分岐自体を使わず、通常の ring 計算へ進みます。

## 値と判定

変数の値は parse されず、`getenv()` が `nullptr` かどうかだけで分岐します。`STRATA_GFX12_RING` が未設定なら gfx12 向け分岐に進む可能性があります。値が空文字でも `nullptr` ではないため、設定済みとして同分岐を止めます。`0`、`1`、`false`、数値以外を含め、設定された値の内容に違いはありません。

| 状態 | ring の決定 |
|---|---|
| 未設定 | 下記の適用条件を満たせば gfx12 用の深さを使う。条件を満たさなければ通常の ring 計算へ進む |
| 設定あり（空文字を含む） | gfx12 用の深さを使わず、通常の ring 計算へ進む |

## 有効になる条件

gfx12 用の深さが選ばれるには、すべて次の条件が必要です。

- HIP build である。判定コードは `STRATA_USE_HIP` の下にあります。
- `STRATA_GFX12_RING` が未設定である。
- layer split 等が設定する `g_ring_override` が 0 以下である。
- prompt attention の matrix-core path が requested と判定される。
- 現在の HIP device が `gfx12` 系である。
- chunk 長 `T` が `stream_all_min()` 以上である。

matrix-core path の request は `STRATA_HIP_WMMA` と device 世代などで決まります。`STRATA_HIP_WMMA=0` または matrix-core launch failure 後は requested になりません。未設定時の gfx12 既定は非 Windows で ON、Windows では OFF です。Windows でも `STRATA_HIP_WMMA=1` なら request され得ます。この環境変数が設定されている場合は、matrix-core path の状態にかかわらず gfx12 ring 分岐へ入りません。

chunk が `stream_all_min()` より短い場合、gfx12 ring ではなく `STAGE` を返します。既定の `stream_all_min()` は 1,024 token ですが、`STRATA_PREFILL_STREAM_MIN` や CPU-share の設定によって変わる経路があります。

## 実行時の詳細

`ring_slots(T)` が ring を解決するたびに `STRATA_PREFILL_RING` の設定有無を確認します。この変数が設定されていると、gfx12 分岐を含む通常ルールを通らず、`atoi` で得た明示値を優先します。未設定で layer split の ring override が正数なら override を使います。gfx12 分岐は `STRATA_PREFILL_RING` 未設定かつ override なしのときだけ候補になります。通常ルールへ進んだ場合は `STRATA_RING_BYTES`、自動 chunk の ring budget、pinned share 等も ring 値に影響します。

gfx12 分岐が候補になった後、matrix-core requested 判定と gfx12 判定は helper を経由します。`deeper` は関数内 `static const bool` で初回評価結果をプロセス内に cache します。matrix-core requested 判定も、その内部で `STRATA_HIP_WMMA` を `static const int` として初回に読みます。したがって、最初の評価後に環境を変更してもこれらの cache 済み判定は変わりません。ring 関数の `STRATA_PREFILL_RING` 読み取り自体は各呼び出し時に行われます。

gfx12 用深さの計算は次の通りです。

- `T < stream_all_min()`: `STAGE`。
- matrix-core request がない、device が gfx12 でない、または `T >= 12,288`: 96 slots。
- `T <= 6,144`: 256 slots、ただし `MAXBLOB()` が正なら 800 MiB / blob サイズで算出する上限を適用する。上限は最低 96 slots。
- それ以外の `T < 12,288`: 同じ上限を適用した 192 slots。

この特別ルールは通常ルールの `ring_cap()` による clamp を通しません。選ばれた ring は `Prefill::init` の ring layout に使われます。`STRATA_GFX12_RING` 固有の警告やログはありません。自動 chunk を選ぶ一部の serve 経路は、解決済み ring を `strata serve: prompt chunk auto: ... a ...-slot ring` として stderr に出します。

## 文書との照合

`docs/DETAILS.md` は `STRATA_GFX12_RING=0` を `STRATA_PREFILL_RING=96` と並べて旧 ring に戻す指定として記載しています。しかし現行コードでは `STRATA_GFX12_RING=0` は単に gfx12 特別分岐を止め、通常の ring 計算へ進ませます。通常計算は `STRATA_PREFILL_RING`、layer split override、ring budget、pinned share 等の状態に依存するため、常に 96 slots を強制する指定ではありません。また、コード上は HIP build であれば Windows でも matrix-core request が成立した場合に特別分岐の対象となり得ます（既定 request は Windows で OFF）。資料の性能値は Linux の R9700 測定として掲載されていますが、本調査では再測定していません。

## 根拠

- `src/prefill/prefill.cpp:402-437`: `STRATA_PREFILL_RING` 優先、HIP 専用条件、`STRATA_GFX12_RING` の設定有無による分岐、token 長別 ring 値、通常ルールへの fallback。
- `src/prefill/prefill.cpp:257-260`: 既定 `stream_all_min()` と `STRATA_PREFILL_STREAM_MIN`。
- `src/prefill/prefill.cpp:2034-2038,2860`: 解決 ring の layout 適用と公開 helper。
- `src/prefill/prefill.cpp:2655-2659`; `src/program/generate.cpp:5922-5930,10184-10199`: layer split の ring override 設定。
- `src/kernels/cuda/qsa_prompt_attn.cu:2241-2275,2285-2295,2432-2448`: `STRATA_HIP_WMMA` の読み取り、gfx12 判定、requested 判定、gfx12 判定 helper。
- `include/strata/core/gfx12_platform_defaults.hpp:4-15`: gfx12 matrix-core prompt default の Windows / 非 Windows 差。
- `src/program/generate.cpp:10785-10797`: serve の auto chunk で解決 ring を表示する箇所。
- `docs/DETAILS.md:1055`: Linux gfx12 prompt staging ring の説明と測定記載。
