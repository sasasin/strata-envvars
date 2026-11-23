# `STRATA_AGENT_PLAN_BRIEF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の host agent bridge で plan の brief / Read 検証機能を有効にする。値が有効な場合、`/plan` の生成指示に検証ルールの書式を加え、plan を Goal として実行するとき各 step の goal objective を短い brief にし、step に明示されたファイル検証を Harness の `read` ツール結果で確認する。未設定または有効値以外では、通常の全体 plan 情報を含む step objective を使い、検証ルールを追加・処理しない（`app/host/server/agent/agent-bridge.mjs:268,1077,1106-1108,1507,1551`、`app/host/server/agent/plan.mjs:28-47,120-134`）。

この機能は Strata の Node host agent bridge の plan / goal 経路に属し、エンジンの CUDA/HIP/SYCL backend を切り替えない。bridge は `env` 引数（既定値 `process.env`）を受け取り、通常の host server は `createAgentBridge` を起動時に呼び出す（`app/host/server/agent/agent-bridge.mjs:156,160,268`、`app/host/server/index.mjs:214-245`）。

## 値と判定

`env.STRATA_AGENT_PLAN_BRIEF === '1'` という JavaScript の文字列完全一致で一度だけ判定する。`process.env` では値は文字列であり、`'1'` だけが有効。大文字小文字変換、trim、数値変換、真偽値変換はない（`app/host/server/agent/agent-bridge.mjs:160,268`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| host agent bridge 初期化時 | 無効（`undefined === '1'` は false） | `1` | 空文字、`0`、`true`、`false`、`01`、` 1`、`1 `、`TRUE` など `'1'` と完全一致しない文字列 |

CLI 引数、設定ファイル、または別の環境変数によるこの判定の上書きはありません。`createAgentBridge` に明示的な `env` オブジェクトを渡す呼び出し元では、そのオブジェクトの値が使われます（`app/host/server/agent/agent-bridge.mjs:160,268`）。

## 有効になる条件

- host server が agent bridge を生成し、`env` に `STRATA_AGENT_PLAN_BRIEF: '1'` を渡していること。通常起動では `env` の既定値が `process.env` です（`app/host/server/agent/agent-bridge.mjs:160,268`、`app/host/server/index.mjs:214`）。
- `/plan` の生成指示、plan の編集・Goal 実行、または番号付き項目を含む `/goal` の経路を通ること。単なるチャットや他の agent 機能にはこのフラグの分岐はありません（`app/host/server/agent/agent-bridge.mjs:1507-1514,1543-1552,1580-1617`）。
- 読み取り検証の完了条件は、step に有効な `[verify-read 相対パス | exact line]` ルールがあり、実行中の親 session で対象ファイルを `read` して、その成功した結果の行情報が要件を満たすこと。パスは相対形式で各部分が `.` / `..` でなく、文字種・長さの制限に合う必要がある。指定行は最大 120 文字（`app/host/server/agent/plan-brief.mjs:4-14,35-44,107-140`）。
- plan を Goal として実行するには、plan mode 以外であること、および Goals が Settings -> Tools で無効化されていないことも必要です。これらは plan 実行側の条件であり、環境変数の値を変換しません（`app/host/server/agent/agent-bridge.mjs:1606-1617`）。
- OS、GPU backend、build macro による追加条件は見つかりません。

## 実行時の詳細

値は bridge の生成時に `const planBrief` へ読み込まれ、その bridge の生存中はキャッシュされます。実行中に環境を変更しても反映されず、再評価には bridge の再生成が必要です（`app/host/server/agent/agent-bridge.mjs:160,268`）。

有効時の処理は次のとおりです。

- `/plan` のモデル向け指示に、exact file/line が指定されている場合だけ検証マーカーを付けるよう追加します。生成された numbered plan の解析もマーカーを保持します（`app/host/server/agent/plan.mjs:28-47,54-85`、`app/host/server/agent/agent-bridge.mjs:1074-1080,1551`）。
- `/goal` の番号付きポイント、および利用者が編集した plan でもマーカーを認識して保持します（`app/host/server/agent/plan.mjs:88-114,173-188`、`app/host/server/agent/agent-bridge.mjs:1506-1511,1580-1588`）。
- plan を Goal として走らせるとき、各 step の objective は全 step の本文を再掲する代わりに、全体目標、現在の step、完了 step 数、直近の結果、workspace 指示、最新の利用者指示、検証指示を含む brief になります。検証要件がある step には `StepEvidence` を作ります（`app/host/server/agent/plan-brief.mjs:67-85`、`app/host/server/agent/agent-bridge.mjs:1101-1108`）。
- bridge は session の event を監視し、該当パスへの `read` 呼び出しと対応する成功結果を照合します。該当パスへの後続 write/edit、または `pwsh` / `bash` / `run_code` 呼び出しは既存の証跡を消します。利用者の live 指示が検証対象を正当に変えた場合も証跡をリセットします（`app/host/server/agent/plan-brief.mjs:87-140`、`app/host/server/agent/agent-bridge.mjs:1028-1038,864-872`）。
- step が終わっても証跡がなければ step は完了扱いにならず、plan を paused に戻します。要件マーカーが不正なら `This plan step still needs a valid read verification rule.`、指定行未確認なら `The plan step is paused until the required line is verified with Read.`、行指定なしのファイル未確認なら `The plan step is paused until the corrected file is verified with Read.` を chat delta として出します（`app/host/server/agent/agent-bridge.mjs:1125-1134`）。Goal phase が Harness 側で complete になっていても、検証要件付きの paused plan では表示上 paused に戻します（同 `:1407-1417`）。

これは plan の goal 実行経路に適用されます。plan の approve が返す通常メッセージ用 `planAsPrompt` はこのフラグを引数に取らず、Read 証跡チェックも `planGoal` / plan の goal run で設定されるため、approve 後の通常メッセージ実行と区別されます（`app/host/server/agent/plan.mjs:168-170`、`app/host/server/agent/agent-bridge.mjs:1580-1595,1606-1617`）。

## ログと測定値

環境変数の読み取りや有効化を知らせる専用の stdout / stderr ログはありません。値による測定値もありません。検証未達時は上記の英文を chat delta として通知し、plan を paused にします。通常の成功時は検証済みファイル（必要なら行番号）が step summary に記録されます（`app/host/server/agent/agent-bridge.mjs:1125-1148`）。

## 根拠

- `app/host/server/agent/agent-bridge.mjs:156-160,264-269` — `env` 引数と初期化時の完全一致判定。
- `app/host/server/agent/plan.mjs:28-47,54-85,88-134,168-188` — 検証ルールを含む plan prompt、解析、brief objective、編集。
- `app/host/server/agent/plan-brief.mjs:35-85,87-141` — 検証ルールの形式、brief 内容、read event と結果の照合。
- `app/host/server/agent/agent-bridge.mjs:864-872,1028-1038,1073-1108,1125-1148,1332-1348,1407-1417,1501-1514,1543-1552,1580-1617` — event 監視、証跡による pause、Plan / Goal の適用経路。
- `app/host/server/index.mjs:214-245` — host server が bridge を生成し通常の環境を用いること。
