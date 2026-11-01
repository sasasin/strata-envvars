# `STRATA_SPEC_PROB_GATE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。Strata checkout は `## main...origin/main` で、未コミット変更はありません。

## 役割

`STRATA_SPEC_PROB=1` の確率的 MTP draft acceptance で使う confidence gate の方式を選びます。未設定時と `top` 以外の値は pick gate になり、draft head が q から引いた token の確率を gate に使います。値が厳密に `top` のときは互換方式となり、q の最大確率を draw 前に調べる top gate を使って、正規化した q に基づく従来の rejection sampling を行います。

この変数だけでは確率的 draft acceptance を有効にしません。上位スイッチ `STRATA_SPEC_PROB` が必要です。

## 値と判定

`include/strata/core/spec_prob.hpp:45-50` で `std::getenv` の結果を文字列全体で `strcmp(e, "top")` と比較します。空文字を含む「未設定以外で `top` と完全一致しない値」は pick gate です。大文字小文字、空白、数値としての解釈はありません。

| 値 | gate 選択 |
|---|---|
| 未設定 | pick gate |
| 空文字 | pick gate |
| `top` | top gate（互換方式） |
| `TOP`, `pick`, `0`, `1`, その他 | pick gate |

結果は関数内の `static const bool` に保存され、最初の呼び出し時に一度だけ読み取られます。その後プロセス内で環境を書き換えても再評価されません（`include/strata/core/spec_prob.hpp:45-50`）。

## 有効になる条件

- `STRATA_SPEC_PROB` が設定され、値が空でなく、文字列 `0` と異なること。判定は `include/strata/core/coupled_draft.hpp:67-72` にあります。この変数が unset、空、または `0` のとき、本変数は確率的 draft acceptance の gate に使われません。
- MTP drafter が使われ、greedy でなく、request temperature が正で、`STRATA_SPEC_MIN_TEMP` の閾値以上であること。MTP の sampled draft 有効判定は `src/core/mtp.cpp:647-652`、probability buffer の存在判定は `include/strata/core/mtp.hpp:133-137` にあります。
- pick gate の新しい gated-proposal 経路は、さらに serial decode・単一 device、`--lookup-chain 0`、`--adapt-swaps 0`、`--pcie-frac 0`、独自の window 規則なし、window 8 行以下、有限かつ 0 以上の `--spec-min-p` を要求します。Metal engine も gated verifier を持ちません。条件を満たさない場合は警告を一度出し、従来の acceptance rule に戻ります（`src/program/generate.cpp:2813-2836,15797-15800,18397-18400`）。
- `top` を選んだ場合は pick-gate 用の `gated_proposal_usable` 判定・fallback 警告の対象外で、旧来の正規化 q による rejection sampling 経路を選びます（同 `src/program/generate.cpp:15797-15800,18397-18400`）。ただし上記の `STRATA_SPEC_PROB` と MTP の条件は引き続き必要です。

## 実行時の詳細

MTP の coupled setup は `STRATA_SPEC_PROB` 有効時に q 分布用 buffer を確保し、開始時に stderr へ `probabilistic draft acceptance on (STRATA_SPEC_PROB)` と gate 名を含む行を出します。pick gate なら「pick gate: masked mu offers...」、`top` なら「top gate (compatibility): q offers...」です。確保に失敗すると `mtp: the draft distributions' buffer does not fit` を返します（`src/core/mtp.cpp:594-614,634-644`）。

pick gate では、draft ごとの q を confidence threshold で mask した測度 mu を verifier に渡します。window の候補生成にはこの gate が関わり、verifier は mu の offer を `min(1, p/mu)` で受け入れ、拒否や gate 失敗時は `(p-mu)+` の residual から置換を選びます。top gate は q の最大確率を draw 前に gate し、通常の正規化 q に対する `min(1, p/q)` と `(p-q)+` residual を使います（`src/core/mtp.cpp:1245-1254`; `src/program/generate.cpp:16977-16983`; `src/kernels/cuda/sampler.cu:1006-1010,1037-1076`; `docs/DETAILS.md:562-572`）。

pick gate が使えない条件では stderr に `STRATA_SPEC_PROB=1 keeps the older acceptance rule in this run (...)` を一度出します。警告文は旧 rule が confidence gate 失敗時に出力分布をずらすこと、および `STRATA_SPEC_PROB_GATE=top` がこの条件で exact であることを述べています（`src/program/generate.cpp:2813-2836`）。verifier の proposal sampler が利用不可、または allocation/copy/launch に失敗した場合は `verify: proposal sampler unavailable or allocation/copy/launch failed` でその run を失敗させます（`src/core/verify.cpp:3365-3391`）。top の経路を選んだこと自体による警告や終了処理はありません。

## 根拠

- 全参照を `rg -n --hidden --glob '!.git/**' 'STRATA_SPEC_PROB_GATE'` で調査。実際の環境読み取りは `include/strata/core/spec_prob.hpp:47` のみ。`src/program/generate.cpp:2834` は警告文字列、`docs/DETAILS.md:567` は説明、CMake の参照は `spec_admission_test` 用の値設定です。
- gate の選択と cache: `include/strata/core/spec_prob.hpp:42-50`。
- 上位モードの判定と MTP 連携: `include/strata/core/coupled_draft.hpp:65-79`, `src/core/mtp.cpp:594-614,634-652`, `include/strata/core/mtp.hpp:133-137`。
- pick gate の使用条件・fallback: `src/program/generate.cpp:2813-2836,15797-15800,18397-18400`。
- verifier への q/proposal の設定と失敗経路: `src/program/generate.cpp:16977-16983`, `src/core/verify.cpp:3359-3395`, `include/strata/core/verify.hpp:149-168`。
- gate ごとの動作説明との照合: `docs/DETAILS.md:562-572`。これは設計説明として参照し、挙動の根拠は実装箇所を優先しました。
