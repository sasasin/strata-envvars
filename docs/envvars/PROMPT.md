# `PROMPT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PROMPT` は Strata のエンジンや通常のサーバー設定ではなく、同梱のホストアプリ E2E スクリプトが入力するテキストを上書きします。一方は chat 画面から送る文、もう一方はテスト用に作成する定期 task の `prompt` です。対象は `apps/host/scripts/mode-flow-s4b.mjs` と `apps/host/scripts/task-flow-s4b.mjs` です。

## 値と判定

両スクリプトとも `process.env.PROMPT ?? '<既定文>'` を使います。文字列の parse、trim、空文字の拒否、長さ制限はこの読み取り箇所にはありません。

| 環境値 | スクリプト内の値 |
|---|---|
| 未設定（`process.env.PROMPT` が `undefined`） | スクリプトごとの既定文 |
| 空文字 | 空文字のまま |
| その他の設定値 | 文字列のまま |

既定文は mode flow では `open my Downloads folder`、task flow では `Open my Downloads folder and tell me how many items are in it.` です。`??` を使うため、空文字は未設定として扱われません。数値や真偽値への変換、無効値時の fallback はありません。

## 有効になる条件

各スクリプトを Node.js で実行した場合に読み取られます。これはホストアプリの起動時設定ではありません。mode flow は `STRATA_URL` が必要で、chat ページを開き、入力欄に `PROMPT` を入れて送信します（`apps/host/scripts/mode-flow-s4b.mjs:8-11,18-28`）。task flow も `STRATA_URL` が必要で、`/api/tasks` へ task 作成要求を送るときに `PROMPT` を JSON の `prompt` フィールドへ入れます（`apps/host/scripts/task-flow-s4b.mjs:3,8-10,15-21`）。

## 実行時の詳細

値は各スクリプトのモジュール評価時に一度読み込まれ、定数 `PROMPT` に保持されます。その後の環境変更を再読込する処理はありません。mode flow では同じ値を Manual / Plan / Bypass の各モードで textarea に入力して送信します。task flow では task 作成リクエストに含めます。既定値や CLI 引数による上書きはなく、環境値があればそれが既定文に優先します。

スクリプトは prompt 自体をログ出力・検証しません。mode flow での失敗は UI 操作の例外や各モードの check によって `FAIL` と終了コード 1 に反映されます。task flow では作成後の task 状態・結果を確認し、完了条件に失敗すると `FAIL` と終了コード 1 になります。`PROMPT` の内容固有のエラー処理はこれらのスクリプト内にはありません（`apps/host/scripts/mode-flow-s4b.mjs:13,27-49`; `apps/host/scripts/task-flow-s4b.mjs:11,20-38`）。

## 根拠

- `apps/host/scripts/mode-flow-s4b.mjs:8-11,18-28,41-49` — `STRATA_URL` の必須確認、既定値付きの環境読み取り、値の入力と送信、フロー結果の判定。
- `apps/host/scripts/task-flow-s4b.mjs:3,8-11,15-21,31-38` — 実行説明、`STRATA_URL` の必須確認、既定値付きの環境読み取り、task 作成 API への値の転送、結果の判定。
- `docs/envvars/000_envvers.md:506` — 候補一覧に `PROMPT` があること。候補一覧だけでは用途を判断せず、上記の実装を根拠とした。

この調査で確認した `PROMPT` 読み取りは上記 E2E スクリプトの2か所です。アプリ本体やエンジンが `PROMPT` を環境から読む実装は確認できません。task API やモデル側で受け取った prompt をどう処理するかは、この変数の読み取り処理の説明範囲に含めていません。
