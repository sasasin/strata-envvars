# `STRATA_SPEC_PROB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

このスイッチは MTP（multi-token prediction）draft head の確率分布 `q` から draft token をサンプルし、verify 側で target 分布 `p` による確率的棄却サンプリングを使う。MTP の通常の draft は argmax だが、このモードでは確率的 draft と `q` のリストを用意する。`p` は target の sampler chain 適用後の分布で、draft は `min(1, p(d)/q(d))` の確率で受理され、棄却時は `max(0, p-q)` の残差から置換 token を選ぶ。MTP 以外の候補は点質量として既存の exact-match 判定に残る。実装は `engine/include/strata/core/coupled_draft.hpp`、MTP 側は `engine/src/core/mtp.cpp`、verify 側は `engine/src/core/verify.cpp` にある（`engine/include/strata/core/spec_prob.hpp:3-21,126-157`, `engine/src/core/mtp.cpp:1521-1531`, `engine/src/core/verify.cpp:4198-4229`）。

## 値と判定

`spec_prob_env()` は `std::getenv` の結果を関数内 `static const bool` に一度保存する。変数が未設定、空文字、または値が文字列全体でちょうど `"0"` なら false。それ以外の非空文字列は true であり、数値・真偽値としての parse はしない。したがって `1`, `true`, `false`, `00`, `0anything`, 前後に空白のある `0` は有効扱い、大文字小文字も区別しない値変換はない（文字列 `"0"` との完全一致のみ）。根拠: `engine/include/strata/core/coupled_draft.hpp:67-73`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 全経路 | 機能を要求しない | `1`, `true`, `false`, `00`, `0anything` | 空文字, `0` |

## 有効になる条件

- MTP drafter が利用される必要がある。スイッチは MTP の `coupled_draft_env()` を有効にし、bind 時に coupled sampler の setup を行うが、MTP が使われない実行には効果がない（`engine/include/strata/core/coupled_draft.hpp:75-79`, `engine/src/core/mtp.cpp:1014-1015`）。
- 実際の確率的 draft は greedy でなく、temperature が `0` より大きく、かつ `STRATA_SPEC_MIN_TEMP` の値以上の request に限る。`STRATA_SPEC_MIN_TEMP` は未設定なら `0`、設定値は `atof` で変換され、draft temperature が閾値未満なら通常 draft のままになる（`engine/src/core/mtp.cpp:855-860`, `engine/include/strata/core/spec_prob.hpp:64-73`）。
- MTP setup が sampler parameter・penalty ring・scratch と `STRATA_SPEC_PROB` 用の `q` buffer を確保できる必要がある。確保に失敗すると setup は false を返し、呼び出し元へ `mtp: the coupled draft sampler's buffers do not fit` または `mtp: the draft distributions' buffer does not fit` を渡す（`engine/src/core/mtp.cpp:802-821`, `engine/src/core/mtp.cpp:1014-1015`）。
- `--spec-min-p` が 0 より大きい場合の標準 pick gate は、serial decode・単一 device・pipeline windows 1 未満・batch 無効・stage 1・remote device なし・`--lookup-chain 0`・`--adapt-swaps 0`・PCIe sharing なし・独自 window rule なし・window 8 行以下・finite な `--spec-min-p` が揃わないと gated rule を使わない。その場合は一度だけ `strata: STRATA_SPEC_PROB=1 keeps the older acceptance rule in this run (%s). That rule's output distribution is off when the confidence gate fails; STRATA_SPEC_PROB_GATE=top is exact here.` と警告し、旧受理規則に戻る。`STRATA_SPEC_PROB_GATE=top` はこの gated rule を選ばない（`engine/src/program/generate.cpp:3543-3563`, `engine/src/program/generate.cpp:21426-21430`）。
- first window、suffix draft、lookup-chain の候補など、MTP が `q` から引いた draft でない行には MTP の `q` を適用しない（`engine/src/program/generate.cpp:22983-22988`, `engine/include/strata/spec/window_rule.hpp:35`）。

## 実行時の詳細

`coupled_draft_env()` は `STRATA_SPEC_COUPLED` またはこのスイッチのいずれかが true なら coupled sampler 用 setup を要求する。`STRATA_SPEC_PROB` の値を `spec_prob_env()` が初めて評価した時点で読み、`static` に保持するため、同一プロセス内で後から環境を書き換えても判定は更新されない（`engine/include/strata/core/coupled_draft.hpp:57-79`）。setup 成功時に `q` buffer を確保し、stderr に有効ログを出す（`engine/src/core/mtp.cpp:818-820,842-849`）。

request ごとに `set_draft_sampling()` が greedy / temperature 条件を判定する。条件を満たすと sampler parameter と penalty history を次の draft round 用に設定する。MTP draft は draft head の distribution `q` から独自 stream でサンプルし、`q` の疎な token/probability list を verify に渡す（`engine/src/core/mtp.cpp:855-865,1521-1531`, `engine/include/strata/core/mtp.hpp:192-196`）。Verify は sampled request で `q` list がある window に rejection sampling を使い、`q` がない場合は point-mass draft として処理する（`engine/src/core/verify.cpp:4192-4229`, `engine/include/strata/core/spec_prob.hpp:126-157`）。

`STRATA_SPEC_PROB_GATE` と `STRATA_SPEC_PROB_DT` は確率的処理の詳細を変える別変数である。gate の既定は drawn-token の `pick` gateで、値がちょうど `top` のときだけ top-probability gate になる。`STRATA_SPEC_PROB_DT` は drafter の temperature scale で、未設定なら `1`; `atof` の結果が正でなければ `1` に戻る（`engine/include/strata/core/spec_prob.hpp:42-61`）。

## ログと測定値

MTP setup 成功時、`STRATA_SPEC_PROB` 有効なら stderr に `strata mtp: probabilistic draft acceptance on (STRATA_SPEC_PROB): sampled requests draft by sampling the draft head's distribution over %lld tokens; ...` を出す。後半は gate により `pick gate: masked mu offers, min(1, p/mu) acceptance and (p-mu)+ rejection/NULL residuals` または `top gate (compatibility): q offers, min(1, p/q) acceptance and (p-q)+ rejection residuals` となる（`engine/src/core/mtp.cpp:842-849`）。生成終了時は q list で判定された window があった場合に stdout へ `probabilistic accept` と window 数を出す（`engine/src/program/generate.cpp:25269-25271`）。

`docs/DETAILS.md` は受理方式、confidence gate の条件、CPU native (IQ) pack の算術経路を説明している（`docs/DETAILS.md:644-660`）。ここではソースから確認できる処理のみを記し、速度・正確性の測定値は追加していない。

## 根拠

- `engine/include/strata/core/coupled_draft.hpp:67-79` — 値の判定、cache、coupled setup との接続。
- `engine/src/core/mtp.cpp:802-852,855-865,1521-1531` — buffer 確保、失敗経路、ログ、request 条件、q sampling。
- `engine/include/strata/core/spec_prob.hpp:3-21,42-73,126-157` — rejection sampling と関連環境設定。
- `engine/src/program/generate.cpp:3543-3563,21418-21430,22983-22992,25269-25271` — gated fallback、verify への q 渡し、結果表示。
- `engine/src/core/verify.cpp:4192-4229` — q list を用いた verify と fallback sampling。
