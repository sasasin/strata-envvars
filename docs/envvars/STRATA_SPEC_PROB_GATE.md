# `STRATA_SPEC_PROB_GATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

確率的ドラフト受理 `STRATA_SPEC_PROB` が有効な MTP サンプリングで、`--spec-min-p` の confidence gate を「引いた draft token の確率」で判定する pick gate（既定）にするか、「q 分布の最大確率」で判定する互換 top gate にするかを選ぶ。未設定を含め、値が正確に `top` でなければ pick gate である。変数名と候補一覧の `on / off` 表記から boolean と解釈してはいけない。判定は `engine/include/strata/core/spec_prob.hpp:42-51`、ドラフト側への引き渡しは `engine/src/core/mtp.cpp:1521-1530` にある。

pick gate では gate を通らない提案も proposal として扱う gated verifier 経路を使える条件がある。top gate はその経路を使わず、従来の q による speculative acceptance を選ぶ。GPU sampler は `gate_pick` に応じて `--spec-min-p` 用の確率を `q[pi]`（引いた token）または `q[0]`（最大確率）から取り出す（`engine/src/kernels/cuda/sampler.cu:938-942, 947-982`）。

## 値と判定

`spec_gate_pick()` は `std::getenv` の結果を関数内 `static const bool` に保存し、文字列全体を大文字小文字を区別して `strcmp(e, "top")` で比較する。数値・真偽値としての parse、空白除去、範囲検査はない（`engine/include/strata/core/spec_prob.hpp:45-50`）。

| 条件 | unset | pick gate になる値の例 | top gate になる値 |
|---|---|---|---|
| 全ビルド（この関数の判定） | pick gate | 空文字、`0`、`1`、`true`、`false`、`off`、`TOP`、` top`、`top `、その他すべて | 完全一致の小文字 `top` のみ |

従って `0`、`false`、`off` は無効化値ではなく pick gate を選ぶ。境界値や負数という数値境界はなく、無効文字列として弾かれる値もない。`000_envvers.md` と `docs/SETTINGS.md` の `on / off` 分類は実装の parse 規則を表していない（Strata 側の読み取り実装: `engine/include/strata/core/spec_prob.hpp:45-50`）。

## 有効になる条件

- 確率的モードが必要。`STRATA_SPEC_PROB` により coupled draft の仕組みが用意され、要求が greedy でなく、温度が正かつ `STRATA_SPEC_MIN_TEMP` 以上のとき `mtp.prob()` が真になり得る。`STRATA_SPEC_COUPLED` だけでは q buffer を作らないため、この変数の gate 判定は確率的受理には適用されない（`engine/include/strata/core/coupled_draft.hpp:65-79`; `engine/src/core/mtp.cpp:818-821, 843-848, 855-860`; `engine/include/strata/core/mtp.hpp:192`）。
- MTP を使う経路であること。CLI と serve の gated proposal 判定はいずれも `use_mtp && mtp.prob()` を要求する（`engine/src/program/generate.cpp:21426-21430, 24842-24845`）。
- `top` の場合は gate 判定が false となるため gated proposal を使わない。従来 verifier に q を渡す経路が選ばれる（`engine/src/program/generate.cpp:21427-21430, 22983-22988, 24842-24845, 25125-25128`）。
- unset または `top` 以外の pick gate で gated proposal を有効化するには、serial decode・単一 device・非 remote であることに加え、`--lookup-chain 0`、`--adapt-swaps 0`、`--pcie-frac 0`、pipeline windows が 2 未満、`--batch 0` が必要。CLI 経路ではさらに単一 stage が必要。`STRATA_SPEC_COST`、DFlash2、または CLI の `--spec-corrupt` / `t_cycle` による独自 window rule がないこと、window が 8 行以下、`--spec-min-p` が有限かつ 0 以上であることも必要（`engine/src/program/generate.cpp:3543-3563, 21427-21430, 24842-24845`）。
- gated proposal 条件に合わない場合、pick gate の確率的受理自体を止めず、古い acceptance rule を使う。制約の理由を示す警告は初回のみ出る。Metal は gated verifier を持たないとコードに明記されている（`engine/src/program/generate.cpp:3545-3562`）。top gate は gated proposal の適用条件判定に入らない。

## 実行時の詳細

環境変数は `spec_gate_pick()` の初回呼び出し時に読み、関数内 static に保存する。CLI/serve の各リクエスト判定でも同じ値が使われ、実行中に環境を書き換えても再評価されない（`engine/include/strata/core/spec_prob.hpp:45-51`; 呼び出し: `engine/src/core/mtp.cpp:846`, `engine/src/program/generate.cpp:21427, 24842`）。値を子プロセスへ転送または上書きする処理は、この名前については見つからない。

pick gate で gated proposal 条件を満たす場合、draft 分布 q のうち `--spec-min-p` を通った mass を verifier に渡し、失敗分も proposal として扱う新しい規則になる。window 構築時に proposal packet を準備し、verifier へ `set_spec_proposal` で渡す（serve: `engine/src/program/generate.cpp:22691-22700, 22983-22990`; CLI: `25021-25030, 25125-25128`）。top gate または条件を満たさない pick gate では従来経路を用いる。MTP 候補への q の引き渡しは `mtp_q_applies(...)` が真のとき行い、CLI では `--spec-corrupt` が正の場合は除外される（serve: `engine/src/program/generate.cpp:22983-22990`; CLI: `25125-25128`）。本変数自体は CLI 引数や request の設定値により上書きされない。`--spec-min-p` は gate の閾値であり、この変数は gate 方式を選ぶ。

## ログと測定値

`STRATA_SPEC_PROB` が有効で coupled setup に成功すると、stderr に `strata mtp: probabilistic draft acceptance on (STRATA_SPEC_PROB): sampled requests draft by sampling the draft head's distribution over ... tokens; ...` が出る。末尾は pick の場合 `pick gate: masked mu offers, min(1, p/mu) acceptance and (p-mu)+ rejection/NULL residuals`、top の場合 `top gate (compatibility): q offers, min(1, p/q) acceptance and (p-q)+ rejection residuals`（`engine/src/core/mtp.cpp:843-848`）。pick gate で gated proposal の条件を満たさないときは、stderr に `strata: STRATA_SPEC_PROB=1 keeps the older acceptance rule in this run (%s). That rule's output distribution is off when the confidence gate fails; STRATA_SPEC_PROB_GATE=top is exact here.` が一度出る（`engine/src/program/generate.cpp:3556-3562`）。top gate ではこの適用条件警告は出ない。

`docs/DETAILS.md:644-654` は両 gate の意味と互換経路を記述している。そこに記載された具体的分布例は文書上の説明であり、この調査では性能測定値を確認・追加していない。

## 根拠

- 値の読み取りとキャッシュ: `engine/include/strata/core/spec_prob.hpp:42-51`
- 確率的 draft の準備と gate ログ: `engine/include/strata/core/coupled_draft.hpp:65-79`, `engine/src/core/mtp.cpp:818-848, 855-860`
- sampler の gate probability 選択: `engine/src/kernels/cuda/sampler.cu:938-982`
- gated proposal の適用条件と警告: `engine/src/program/generate.cpp:3543-3563`
- CLI/serve での方式選択と verifier への引き渡し: `engine/src/program/generate.cpp:21426-21430, 22691-22700, 22983-22990, 24842-24855, 25021-25030, 25125-25128`
- 関連設計説明: `docs/DETAILS.md:644-654`
