# `STRATA_PRIVATE_MTP_DEMAND`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の二段 decode pipeline で、MTP drafter の chain を全出力分まとめて投入する代わりに、まず先頭出力だけを投入し、出力が判明するたびに必要な後続 step を追加投入する private opt-in です。各 window の draft 生成を段階化し、stage 1 の verifier の投入を chain の最終出力まで待たせます。通常の生成設定やモデル選択を変える変数ではありません。読み取りと有効化は `sycl/src/program/generate.cpp:11733-11737`、chain の初回投入と continuation は `sycl/src/core/mtp.cpp:1922-1932,1984-2010`、stage 1 の gate は `sycl/src/program/generate.cpp:11976-11982` にあります。

## 値と判定

`generate.cpp` は pipeline 内で毎回 `std::getenv` し、値の先頭文字だけを `'1'` と比較します。文字列全体の parse、空白除去、大文字小文字変換、数値境界検査はありません。未設定・空文字は無効です。`1`, `10`, `1anything` は値条件を満たし、`0`, `true`, ` 1`, `01`, `1` 以外で始まる文字列は満たしません（`sycl/src/program/generate.cpp:11735-11736`）。ただし、以下の他条件も満たす必要があります。

| 条件 | unset | 値条件を満たす例 | 値条件を満たさない例 |
|---|---|---|---|
| pipeline 内の判定 | 無効 | `1`, `1junk`（先頭が `1`） | 空文字、`0`, `true`, ` 1` |
| 実際の opt-in | 無効 | 先頭が `1`、かつ `pl_agree == true`、`force_miss == 0` | 上記以外。debug の不一致モードまたは `force_miss > 0` では無効 |

`pl_agree` は既定で true ですが、`STRATA_PIPELINE_DEBUG` が設定され、その先頭が NUL/`0` 以外なら `STRATA_PIPELINE_AGREE` を参照し、その `atoi` 結果が 0 のとき false になります。これは helper の最初の呼び出し時に static cache されます（`sycl/src/program/generate.cpp:326-329,11729-11736`）。`force_miss` は pipeline ごとの `pl_force_miss` で、通常は 0、debug 時の `STRATA_PIPELINE_FORCE_MISS` の `atoi` 値（0 未満は 0 に clamp）または `STRATA_PIPELINE_SWITCH` ファイル内の `force_miss=` 指定で変更されます（`sycl/src/program/generate.cpp:10754-10777,11417-11419`）。

## 有効になる条件

- この読み取り箇所は `sycl/src/program/generate.cpp` の SYCL pipeline 実装にあります。CUDA/HIP 側でこの名前を読む箇所は、対象 commit の Strata 所有コード全体検索では見つかりません。
- `--pipeline-windows` が有効で、実際に `pl_want` となる必要があります。decode pipeline は `pipe && pl_pw >= 2 && pl_snap2[0] != nullptr` の場合だけ要求されます（`sycl/src/program/generate.cpp:11385-11396`）。
- pipeline は `--serve`、二 GPU の layer split、ちょうど二 stage、`--mtp` と `--spec >= 2` が必要です。batch slots、`--peer-device`、helper cache がある場合は無効化されます（`sycl/src/program/generate.cpp:3542-3556`）。さらに、対象リクエストに repetition penalty 履歴がある場合、または coupled draft sampling の場合は serial decode に戻ります（`sycl/src/program/generate.cpp:11387-11396`）。
- `--pipeline-windows` 自動判定では、指定が負値のとき二つの Battlemage (Xe2) GPU にまたがる split、`--serve`、MTP などの入力を使って既定値を決め、`STRATA_PIPELINE_AUTO=0` で自動有効化を止めます（`sycl/src/program/generate.cpp:3512-3540`）。この対象変数自体は pipeline を有効化しません。
- private opt-in の追加条件として `pl_agree` が true かつ `force_miss == 0` が必要です。条件を外れた場合、`begin` に false が渡り、chain は通常の全量投入経路になります（`sycl/src/program/generate.cpp:11725-11736`）。

## 実行時の詳細

対象変数は pipeline decode の setup ごとに読み取られ、値を static cache しません。従って、その後の pipeline setup で環境が変更されていれば次の判定に反映されます。状態自体は `private_demand` の `thread_local` にあり、`begin` が MTP owner と有効状態を設定し直します（`sycl/src/program/generate.cpp:11735-11736`; `sycl/include/private_mtp_demand.hpp:8-29`）。

有効時、`MtpDrafter::chain_launch` は chain 出力上限を `limit` に保存し、最初の一出力だけを submit します（`sycl/src/core/mtp.cpp:1922-1932`）。pipeline loop は ready な出力数 `k` と chain kind、window の確定状態、確率条件を調べ、続行が必要なら `target` を最大 `k + 1` まで進めます。chain が最終状態、確率ゲートによる終了、または window サイズ確定に至ると、既に submit 済みの数で target を固定します（`sycl/src/program/generate.cpp:11821-11858`）。`chain_outputs_ready` は増えた target まで step graph を投入し、event を待ちます（`sycl/src/core/mtp.cpp:1984-2010`）。chain が final でない間は `chain_poll` は完了扱いを返さず（`sycl/src/core/mtp.cpp:2055-2058`）、stage 1 の verifier 起動も `can_enqueue_s1` が許可するまで待機します（`sycl/include/private_mtp_demand.hpp:32-34`; `sycl/src/program/generate.cpp:11976-11982`）。

context/cancel など loop が通常の frontier より前に終わる場合は、drain が残りの上限まで submit する状態にしてから既存の drain/reuse boundary に進みます（`sycl/src/program/generate.cpp:12121-12125`; `sycl/include/private_mtp_demand.hpp:35-37`）。request の verifier が最終的に出力を選び、出力 token は `outp` から stdout の `T <id>` 行として出されます（`sycl/src/program/generate.cpp:11992-12010`）。この環境変数は verifier の判定規則や CLI の生成上限を変更する処理を持ちません。

## ログと測定値

対象変数が有効な state を作った場合、pipeline drain 後に stderr へ `STRATA_MTP_DEMAND chains=... requested=... actual=... continuations=... dead_B=... reaction_ns=... submit_ns=... max_reaction_ns=...` の集計行を出します（`sycl/src/program/generate.cpp:12220-12224`）。`STRATA_PRIVATE_MTP_DEMAND_LOG` が設定されている場合（空文字を含む）には、chain 完了時に stderr へ `STRATA_DEMAND_DETAIL {...}` の機能的記録も出ます（`sycl/src/program/generate.cpp:11866-11875`）。これらの行は本変数の有効時に state が存在することが前提です。

Continuation の目標が staged chain の上限を超えた場合は `private demand: target exceeds staged chain`、step submit/barrier に失敗した場合は `private demand: continuation failed`、retirement event に失敗した場合は `private demand: retirement event failed` が error になります（`sycl/src/core/mtp.cpp:1995-2007`）。呼び出し側は chain poll の負値などを `die(err)` に渡します（`sycl/src/program/generate.cpp:11860-11861`）。この文書では性能値を記載しません。`docs/DETAILS.md:334-341` は MTP と関連 CLI を説明していますが、この private demand mode の測定値や効果は記載していません。

## 根拠

- `sycl/src/program/generate.cpp:326-329` — `STRATA_PIPELINE_DEBUG` による debug helper の判定と cache。
- `sycl/src/program/generate.cpp:3512-3556` — pipeline 自動判定、必要条件、無効化理由。
- `sycl/src/program/generate.cpp:10754-10777` — debug switch の値と per-request override。
- `sycl/src/program/generate.cpp:11377-11400` — decode pipeline の要求条件と serial fallback。
- `sycl/src/program/generate.cpp:11725-11736,11821-11875,11976-11982,12121-12125,12220-12224` — 対象変数の読み取り、demand state の判断、gate、drain、ログ。
- `sycl/src/core/mtp.cpp:1922-1932,1984-2010,2055-2091` — initial submission、continuation、poll/retire。
- `sycl/include/private_mtp_demand.hpp:8-37` — state/cache scope と gate/drain helper。
- `docs/DETAILS.md:334-341` — MTP 関連の文書記載との照合。
