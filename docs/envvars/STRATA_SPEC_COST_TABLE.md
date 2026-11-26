# `STRATA_SPEC_COST_TABLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` の speculative decoding で、コストを考慮した MTP 検証幅選択に初期コスト表を与える値です。`STRATA_SPEC_COST=1` のときに限り、表の値を `DraftPolicy` に投入します。幅選択のコスト推定を始める材料であり、候補 token の生成や検証そのものを置き換える値ではありません（`engine/src/program/generate.cpp:24871-24897`、`engine/include/strata/spec/draft_policy.hpp:196-201,287-301`）。

読み取り箇所は `engine/src/program/generate.cpp:24875` の 1 箇所です。永続 serve ループにも `STRATA_SPEC_COST` の判定はありますが、そこではこの表を読みません（同ファイル `16411-16429`）。したがって、この変数はその serve ループに初期表を渡しません。

## 値と判定

値全体を検証する parser はなく、カンマ区切りを `std::atof` で数値化します。セミコロンで最大 3 個の context bucket のリストに分けます。各リストの先頭から最大 16 個が読み取られ、位置 1 の値は T1、位置 2 は T2 の窓コストとして扱われます（`engine/src/program/generate.cpp:24875-24888`、`engine/include/strata/spec/draft_policy.hpp:152-155`）。

| 条件 | unset / 空文字 | 有効になる値（例） | 無効・無視される値（例） |
|---|---|---|---|
| `STRATA_SPEC_COST` が有効 | unset または空文字は表を parse / 投入しない | `1.2,2.4,3.1`、`1,2;1.1,2.2;1.3,2.5` | `0,0,-2,abc` は各要素が正数でないためコストとして登録されない |
| `STRATA_SPEC_COST` が無効 | unset / 空文字を含め、表は利用されない | なし | `STRATA_SPEC_COST_TABLE` が非空でも、環境値は取得するが内容は parse / 登録しない |

`STRATA_SPEC_COST` 自体は文字列の先頭 1 文字が `'1'` かで判定されます。`1`, `10`, `1anything` は有効、`0`, `true`, ` 1`, 空文字、未設定は無効です（`engine/src/program/generate.cpp:16419,24827`）。ただし CUDA の全可視 GPU が同一の compute capability 12.1 で、`STRATA_SM121_PERF` が先頭 `'0'` でなく、`STRATA_DEFAULTS=026` による既定無効化もない場合は、起動時に Strata が未設定の `STRATA_SPEC_COST=1` を設定します。ユーザーが空文字を含む何らかの値を設定済みならその値が優先されます（`engine/src/program/generate.cpp:4425-4449`、`engine/src/core/nv_defaults.cpp:15-18,176-205,222-233`）。

表の値は `atof` の変換結果が `> 0.0` の場合だけ採用されます。従って `2.5junk` や前後に空白のある数値は数値 prefix が変換され、`abc`・`0`・負数・NaN は採用されません。正の値に上限・有限値チェックはありません。欠けた項目は登録されず、空の要素は `atof` が 0 とするためその幅のコストとして登録されませんが、要素位置は消費します（例: `1,,3` の `3` は T3）。カンマ後に終端した末尾の未完了リストは `seed_costs` に渡されません。4 個目以降の bucket と各 bucket の 17 個目以降は処理されません（`engine/src/program/generate.cpp:24879-24888`、`engine/src/spec/draft_policy.cpp:521-528`）。

各非空リストは `seed_costs(..., 6.0, bucket)` に渡されます。各正数はその窓幅のコストとして 6 サンプル分の重みで初期化され、実測コストが既にある幅は上書きしない実装です（この CLI 経路では新しい `DraftPolicy` を作ってから投入します）（`engine/src/program/generate.cpp:24871-24888`、`engine/src/spec/draft_policy.cpp:521-528`）。

## 有効になる条件

- speculative decoding のループに入る必要があります。`--spec` が 0 などで `spec_loop_runs(...)` が偽なら、この表を読む位置まで進みません（`engine/src/program/generate.cpp:24459-24489`）。
- 同じ実行経路で `STRATA_SPEC_COST` 判定が有効で、かつ `STRATA_SPEC_COST_TABLE` が未設定でなく空文字でもない必要があります（`engine/src/program/generate.cpp:24875-24890`）。
- `--spec` と `--mtp-max-t` が実際の上限を定めます。MTP の上限 `S_mtp` は `--mtp-max-t` が正なら `min(--mtp-max-t, --spec)`、それ以外は `--spec` です。コスト表によりこの上限を越える窓が選ばれることはありません（`engine/src/program/generate.cpp:24836-24845,24868-24897`）。
- MTP が読み込まれていない場合、MTP の逐次 draft chain に対する `keep_draft` callback は登録されず、この変数の「MTP draft を追加するか」という作用はありません（`engine/src/program/generate.cpp:24507-24511,24890-24896`）。
- serve ループでは `STRATA_SPEC_COST` によるコスト幅ルール自体は設定されますが、`STRATA_SPEC_COST_TABLE` の読み取り・seed はありません。表を設定しても serve 用 `DraftPolicy` には渡りません（`engine/src/program/generate.cpp:16411-16429` と `24871-24890`）。

## 実行時の詳細

CLI の speculative decoding 部分で `DraftPolicy` を新規作成した後、環境値を一度走査して表を seed します。その後 `policy.set_robust(spec_cost)` と `mtp.set_chain_rule(...)` を設定し、各 MTP draft の確率を `keep_draft` に渡します。policy はコスト表と draft の受理率推定から次の検証窓の候補を比較し、最良幅を選んで追加 draft を続けるかを決めます（`engine/src/program/generate.cpp:24871-24897,25030-25040`、`engine/src/spec/draft_policy.cpp:975-1000`）。

context bucket は `< 6000`、`6000..23999`、`>= 24000` の位置区分です。該当 bucket に値がなければ、`set_context` が近い bucket のコストを重み 1 でコピーします。表にない幅のコストは既知幅からスケールした推定値、または組み込み形状値になります（`engine/src/spec/draft_policy.cpp:495-507,530-550`）。ここでいう「表」はプロセス間に保存される設定ファイルではなく、この `DraftPolicy` インスタンスに初期値を渡すものです。

表の読み取り後にプロセス環境を変更しても、この policy の初期値は再読込されません。表に関する個別の警告・エラー経路はなく、無効な要素は `seed_costs` の正数条件で登録されません（`engine/src/program/generate.cpp:24875-24890`、`engine/src/spec/draft_policy.cpp:521-528`）。

## ログと測定値

`STRATA_SPEC_COST` が有効な `strata generate` は処理後に stdout へ `spec cost table` と `policy.cost_table_text()` の結果を出します。ここには各 bucket の T 幅・コスト・サンプル重みが表示されます。表の不正値について専用ログはありません（`engine/src/program/generate.cpp:25264-25279`、`engine/src/spec/draft_policy.cpp:552-568`）。

## 根拠

- `engine/src/program/generate.cpp:24871-24897` — CLI 側での表読み取り、seed、cost rule 設定。
- `engine/src/program/generate.cpp:16411-16429` — serve loop に表の読み取りがないこと、および `STRATA_SPEC_COST` の評価。
- `engine/src/program/generate.cpp:4425-4449`、`engine/src/core/nv_defaults.cpp:15-18,176-205,222-233` — NVIDIA sm_121 での関連既定値とユーザー値の優先。
- `engine/src/spec/draft_policy.cpp:495-550,521-528,552-568,975-1000` — コスト推定・bucket fallback・表の表示・幅選択。
- `engine/include/strata/spec/draft_policy.hpp:152-155,196-206,287-301` — 表の形と cost-aware MTP rule の説明。
