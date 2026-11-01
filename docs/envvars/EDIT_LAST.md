# `EDIT_LAST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱の HTTP 操作用スクリプト `apps/host/scripts/agent-http.mjs` を `plan` コマンドで実行したとき、生成された plan の末尾に追加する 1 ステップの文を指定します。Strata の host サーバーやエンジンが直接読む設定ではなく、このスクリプトが plan 編集 API に送る値です。候補一覧には記載されていますが、確認できた読み取りはこのスクリプトの一箇所です。

## 値と判定

| 状態・値 | スクリプトでの扱い |
|---|---|
| 未設定 | 条件が偽になり、編集 API を呼びません。生成した plan はそのまま後続処理へ進みます。 |
| 空文字 (`EDIT_LAST=`) | JavaScript の空文字は falsy のため、未設定と同じく編集しません。 |
| 空でない文字列 | truthy なら文字列をそのまま既存の step 文列の末尾に追加し、`/api/plan/edit` に送ります。数値・真偽値としての parse はありません。たとえば `0`, `false`, 空白だけの値もこの条件では truthy です。 |

サーバー側では各 step が空白の連続を一つにし、前後の空白を除き、`**`・`__`・バッククォートを取り除いてから最大 140 文字に切り詰められます。step は最大 12 件で、超過分は末尾から落ちます。そのため元の plan がすでに 12 件なら、追加した `EDIT_LAST` の step は保存結果に残りません。編集時は残った全 step の状態が `pending` に戻り、plan は `proposed` になります。

## 有効になる条件

- `agent-http.mjs plan <task>` の `plan` コマンドを選んでいること。`stream` など他のコマンドではこの変数を参照しません。
- `STRATA_URL` が設定されて host に接続でき、保存済みモデル接続があり、`/plan <task>` の応答に plan frame が含まれること。
- plan frame がない場合、スクリプトは `NO PLAN FRAME ...` を表示して終了するため、この変数による編集は行われません。
- `planId` が有効で、plan が `proposed` または `approved` 状態であること。サーバーはそれ以外の状態の plan を編集しません。

この変数自体には OS、GPU backend、ビルド macro、モデル状態に応じた分岐はありません。変更された plan は、`STOP_AT_PLAN` が設定されていればその指定アクションの後にスクリプトが終了し、設定されていなければ `start-goal` API に渡されて実行開始へ進みます。

## 実行時の詳細

`EDIT_LAST` はプロセス起動時に別の設定値へコピー・cache されず、`plan` コマンドが plan frame を受け取った後、編集 API を呼ぶ条件式と step 追加式で `process.env.EDIT_LAST` を参照します。スクリプト実行中に環境変数を書き換えて再評価する処理はありません。

編集成功時、スクリプトは `-- edit <step数> steps` を経過時間付きで標準出力に表示します。`/api/plan/edit` が非 2xx を返すと HTTP helper が `<path> -> <status> <error>` の Error を投げ、スクリプトは編集後の `STOP_AT_PLAN` / `start-goal` に進みません。host の plan control は存在しない plan に `409`、使用済み plan に `409`、step の不正（配列でない、または有効 step がない等）に `400` を返します。通常このスクリプトは既存 step を含む配列を送るため、末尾値が空白のみでも既存 step が有効なら edit 自体は成立します。

## 根拠

- `apps/host/scripts/agent-http.mjs:13-23,27-32` — `STRATA_URL` の必須確認、HTTP helper と保存済み model 接続取得。
- `apps/host/scripts/agent-http.mjs:144-163` — `plan` コマンドの処理、plan frame がない場合の終了、`EDIT_LAST` 条件判定・step 追加・編集要求、編集後の `STOP_AT_PLAN` / `start-goal`。
- `apps/host/server/index.mjs:1902-1909` — `/api/plan/edit` のルーティングと plan control 例外の HTTP status 変換。
- `apps/host/server/agent/agent-bridge.mjs:1032-1055` — plan の存在・状態確認、step 編集、状態を `proposed` に戻す処理。
- `apps/host/server/agent/plan.mjs:18-23,163-175` — step 数・文字数上限、文字列の正規化・切り詰め、空 step の除外と最低 1 件の検証。
