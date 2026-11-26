# `STRATA_SPEC_COST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP drafter が提案する draft の個数、つまり target model が検証する window 幅を、draft の確率から推定した受理率と実測 window コストに基づいて決めます。既定の `--spec-min-p` 方式ではなく MTP の chain を一段ずつ伸ばし、期待 token 数/ms が最良になる幅を選びます。検証器に渡す候補幅を選ぶ制御であり、通常 generate の出力 token は target 側で検証・commit されます（`engine/src/program/generate.cpp:24825-24827,25032-25040`; `engine/include/strata/spec/window_rule.hpp:30-33,57-70`; `engine/src/spec/draft_policy.cpp:975-1000`）。

実装は通常 generate と `--serve` の両ループにあります。`use_mtp` が偽なら chain callback は登録されず、MTP の window 選択には作用しません。DFlash2 がその round の候補を作る場合も cost rule は適用されず、MTP fallback が候補を作った round に限って適用されます（`engine/src/program/generate.cpp:12309-12314,16419-16428`; `engine/include/strata/spec/window_rule.hpp:16-33`; `engine/src/program/generate.cpp:22702-22709,25032-25039`）。

## 値と判定

両経路とも `std::getenv` の結果が null でなく、かつ `v[0] == '1'` の場合だけ有効とします。文字列全体の parse・数値変換・大文字小文字変換はありません。空文字は無効、`1`, `1abc`, `10` は有効、`0`, `true`, ` 1`, `01` は無効です（`engine/src/program/generate.cpp:16419,24827`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 一般の読み取り | `getenv` が null なら無効 | 先頭文字が `1` | 空文字、`0`, `true`, ` 1` |
| CUDA の均一 sm_121 (GB10) 起動時既定 | `STRATA_SM121_PERF=0` または `STRATA_DEFAULTS=026` でなければ、未設定時に `1` を注入 | 上記既定、または利用者が設定した値の先頭が `1` | 利用者が設定した空文字や `0...` は既定注入を抑止し、無効 |

明示的に設定された値は「何であっても」既定値より優先されます。既定注入は CUDA build で、可視 CUDA GPU がすべて同一 compute capability のときに行われます。表に `STRATA_SPEC_COST=1` があるのは sm_121 のみです。sm_121 の表自体は `STRATA_SM121_PERF=0` または `STRATA_DEFAULTS=026` で省かれます。HIP/Metal/SYCL や混在 compute capability の CUDA ではこの表から値は注入されません（`engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:176-180,202-205,222-234`）。

## 有効になる条件

- MTP drafter がロードされ、その MTP chain が当該 round の候補を生成すること。`--draft auto` では request ごとに選ばれた drafterが MTP である場合に限ります（`engine/src/program/generate.cpp:16402-16413,16423-16428`）。
- 初回 window では cost rule を使いません。serve では初回 window に prompt merge がある場合も caller が幅を設定します（`engine/include/strata/spec/window_rule.hpp:30-33`; `engine/src/program/generate.cpp:22702-22711,25038-25040`）。
- DFlash2 候補の round では使われません。`--draft-fallback` 等で MTP がロード済みでも、DFlash2 が実際の候補源なら cost window は適用されません（`engine/include/strata/spec/window_rule.hpp:16-33`; `engine/src/program/generate.cpp:22703-22709,25032-25039`）。
- `--spec-min-p` と同時に有効なとき、MTP 候補の幅は cost rule が選びます（`choose_window` の分岐順）。ただし後段の suffix lookup が policy により幅を差し替えることがあります。CLI の `STRATA_SPEC_T_CYCLE` はさらに後で幅を上書きします（`engine/include/strata/spec/window_rule.hpp:57-70`; `engine/src/program/generate.cpp:25032-25053,25042`）。
- `STRATA_SPEC_PROB=1` の gated proposal は、`own_window_rule` にこの変数が含まれるため利用不可となり、一度 stderr に理由を出して古い acceptance rule を維持します（`engine/src/program/generate.cpp:3543-3562,24842-24845`）。

## 実行時の詳細

値は serve loop への入り口と通常 generate の speculative loop 初期化時にそれぞれ一度読みます。読み取り値はその serve プロセスまたは generate 実行の間保持され、後から環境を書き換えても反映しません。policy の cost・受理率・文脈 bucket は各 round の観測に応じて更新されますが、これは環境変数の再読ではありません（`engine/src/program/generate.cpp:16419-16428,24825-24830`; `engine/src/spec/draft_policy.cpp:966-1000`）。

有効時、MTP drafter は各 draft step の後で callback を呼び、現在の幅を伸ばすか決めます。policy は draft 確率から受理率を推定し、現在の文脈位置 (<6K, <24K, それ以上) の測定コストに対する期待 token 数/ms を比較します。未測定幅は一定条件で探索されます。round 終了後に実測値と受理結果を policy に反映し、次の選択に使います（`engine/src/core/mtp.cpp:2001-2024`; `engine/src/spec/draft_policy.cpp:530-550,966-1000`; `engine/src/program/generate.cpp:22667-22668,23208-23214,25018-25019,25243-25245`）。

`STRATA_SPEC_COST_TABLE` が設定され、空でなく、この変数が有効な場合は起動時に初期コスト表として読みます。値は最大 3 bucket の `;` 区切り、それぞれ数値を `,` 区切りする形式で `atof` に渡されます。cost policy は実測 round cost も更新に使います（`engine/src/program/generate.cpp:24874-24890`; `engine/src/spec/draft_policy.cpp:521-528,668-679`）。

## ログと測定値

通常の generate は終了時に `window sizes` と `spec cost table` の行を stdout に出します。前者には幅ごとの回数と `cost rule 1`、後者には bucket ごとの `Tn:cost(n=...)` が表示されます（`engine/src/program/generate.cpp:25257-25278`; 表示は通常 generate loop）。serve では `STRATA_DRAFT_LOG` が設定されていれば request ごとの診断行が出ますが、cost rule 固有の必須ログではありません（`engine/src/program/generate.cpp:16416-16419`）。値が無効な場合にこの変数固有の警告やエラーはありません。

`docs/DGX_SPARK_LINUX.md:117,128-134` は GB10 上の `STRATA_SPEC_COST=1` で decode +4.7% と記録し、コスト対応窓は試行する draft を変えるだけと説明しています。これは同資料の測定記録であり、他機種や設定での性能保証ではありません。`engine/src/core/nv_defaults.cpp:202-205` にも IQ3_S の測定値 1.047x と 24/24 greedy answers 同一との記録があります。文書記録と一般的な出力同一性を混同せず、ソースで確認できるのは window 幅の選択・候補の検証経路までです。

## 根拠

- `engine/src/program/generate.cpp:16419-16428` — serve 経路での読み取り、robust policy 設定、MTP callback。
- `engine/src/program/generate.cpp:24825-24830,24842-24845,24874-24890` — 通常 generate での読み取り、gated proposal 条件、コスト表。
- `engine/include/strata/spec/window_rule.hpp:30-33,57-70` — 初回/DFlash2 条件と `--spec-min-p` との選択順。
- `engine/src/spec/draft_policy.cpp:530-550,966-1000` — context bucket、確率受理率、幅の選択。
- `engine/src/core/mtp.cpp:2001-2024` — draft ごとの callback 実行。
- `engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:176-180,202-205,222-234` — CUDA の既定注入と利用者設定の優先。
- `engine/src/program/generate.cpp:3543-3562` — `STRATA_SPEC_PROB` との競合時の警告・fallback。
