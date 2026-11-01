# `TITLE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`TITLE` は Strata の通常エンジンやサーバー設定ではなく、同梱の実時間タスク UI フロースクリプト `apps/host/scripts/task-flow-s4b.mjs` が、スケジュールタスク作成 API に渡すタイトルを指定するために読みます。このスクリプトはタスク作成・実行と画面確認を行う E2E 用フローです。Strata 本体の C++/CUDA/HIP/SYCL エンジンやサーバー起動時の設定として `TITLE` を読む箇所は確認できませんでした。

## 値と判定

| 状態 | スクリプトが API に送る値 | サーバー側の処理 |
|---|---|---|
| 未設定 | `Open my downloads folder` | 先頭・末尾の空白を除去し、1〜120 文字なら受理 |
| 空文字 | 空文字（既定値へ置換されない） | `trim()` 後に空になり、HTTP 400 `Use a task name of 1–120 characters.` |
| その他の文字列 | 環境変数の文字列をそのまま JSON の `title` に設定 | `String(...)` で文字列化後 `trim()`。空、または `length > 120` なら HTTP 400。それ以外は trim 後の値を保存 |

スクリプトの `??` は未設定（`undefined`）時だけ既定値を使い、空文字は値として保ちます。サーバーの長さ判定は JavaScript の文字列 `length` によるもので、追加の文字種・大文字小文字・数値変換はありません。タイトルの引数・設定ファイル・別環境変数との優先順位はなく、API リクエスト本文の `title` にそのまま反映されます。

## 有効になる条件

`TITLE` を読むのは上記 E2E スクリプトを Node.js で実行した場合だけです。環境変数はそのスクリプトの起動時に `process.env.TITLE` として参照され、タスク作成リクエストを組み立てます。既定値は同じ箇所で選択されます。実行中の環境変更を再読する処理やキャッシュはありません。

このフローは `STRATA_URL` がなければ起動直後に `STRATA_URL required` を stderr に出して終了コード 2 になります。`TITLE` を渡しても、サーバーが `/api/tasks` の作成要求を検証して受理しなければタスクは作られません。通常の Strata 起動や CLI で `TITLE` を設定しても、この E2E スクリプトを通らない限り効果はありません。

## 実行時の詳細

スクリプトは `TITLE ?? 'Open my downloads folder'` を `/api/tasks` への POST JSON 本文の `title` に入れます。本文には別途、既定または `PROMPT` の指示、実行時刻、毎日スケジュール、ローカルタイムゾーン、既定または `MODE` の値も含めます。`TITLE` はこれらの値の選択には影響しません。リクエストに対する HTTP ステータスをスクリプト自身は検査せず、応答を JSON として読みます。

Strata サーバーは作成要求を `tasks.put()` に渡し、`validateTask()` でタイトルを trim して空文字と 120 文字超を拒否します。検証エラーは API handler から HTTP 400 とエラーメッセージ JSON で返ります。受理されたタイトルはタスク記録に保存され、タスク通知の `title` と実行時クライアント名 `Task: <title>` にも使われます。これらは API を通った後のタスクタイトルの利用であり、サーバーが環境変数 `TITLE` を直接読むものではありません。

完全一致で確認したソース参照では、`.github/workflows/title-area.yml` の `TITLE` は GitHub Actions が PR/issue タイトルを検査するための workflow 環境値です。Strata 実行プロセスの環境変数読み取りではありません。他の完全一致は UI の `TITLE` 定数、通常のタイトル文字列、またはライセンス文中の語でした。

## 根拠

- `apps/host/scripts/task-flow-s4b.mjs:3,8-10,20-21` — E2E スクリプトの起動条件、環境値の読み取りと既定値、タスク作成 API 本文。
- `apps/host/server/index.mjs:1266-1267` — POST `/api/tasks` を `tasks.put()` に渡し、例外を HTTP 400 にする処理。
- `apps/host/server/tasks.mjs:10-22,51-59` — タイトルの文字列化・trim・空/長さ検証とタスク記録への保存。
- `apps/host/server/index.mjs:923-938` — 保存済みタイトルを通知および `Task: <title>` の実行クライアント名へ使う処理。
- `.github/workflows/title-area.yml:20-26` — 同名の workflow 変数は PR/issue タイトル検査で使われる。
