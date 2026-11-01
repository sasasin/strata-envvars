# `STRATA_INPUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部コマンド自身が行う環境変数の読み取りは対象外。

## 役割

Strata Host の「Settings → Your own tools」で設定された command tool を実行するとき、tool 呼び出しの `input` を起動する子プロセスの `STRATA_INPUT` として渡します。Host 自身が既存の `STRATA_INPUT` を環境から読み込んで動作を変える設定ではありません。候補一覧には載っていますが、実装上確認できるのはカスタムコマンドへの値の受け渡しです。

## 値と判定

| 入力 | 子プロセスの `STRATA_INPUT` |
|---|---|
| `input` が省略または `null` | 空文字列 `''` |
| 文字列 | その文字列をそのまま渡す。文字列内容の parse や trim はしない |
| それ以外の値が runner に渡された場合 | `String(input)` の結果 |

MCP の command tool schema では `input` は任意の文字列で、追加プロパティは許可されません（`apps/host/server/agent/custom-tools-mcp.mjs:24-29`）。呼び出し側から渡された値は `runCommand` に渡り、`String(input ?? '')` に変換されます（同 `:35-40`; `apps/host/server/agent/custom-command-run.mjs:77-88`）。空文字を含め、入力がないときも子環境にはキーを設定します。親 Host の `process.env.STRATA_INPUT` を継承値として使う経路はなく、`{ ...process.env, STRATA_INPUT: ... }` の後勝ちで子環境の値を上書きします（`custom-command-run.mjs:88`）。

この変数値について数値変換、範囲判定、無効値 fallback はありません。設定入力の上限は tool 呼び出しの `input` に関してこの実装では定められていません。Strata は値を環境に設定するだけで、その文字列をどう解釈するかは設定されたコマンド側の処理です。

## 有効になる条件

- Settings に有効な `kind: 'command'` のカスタム tool があり、command tool server がその tool を呼び出すこと。設定ファイルには有効な instruction/command tools のみを書き出します（`apps/host/server/agent/tools-settings.mjs:95-114`）。profile は有効な command tool があるときに `strata-commands` MCP server を追加します（`apps/host/server/agent/profile.mjs:298-303`）。
- 実行にはコマンドを開始できることと、作業ディレクトリが存在することが必要です。作業ディレクトリは呼び出し時の `cwd`、tool 設定の `cwd`、ホームディレクトリの順に選択されます（`apps/host/server/agent/custom-command-run.mjs:50-62,80-89`）。
- Manual mode では command tool は承認を求め、Plan mode では拒否されます（`apps/host/server/agent/README.md:79`; `apps/host/server/agent/tools-settings.mjs:7-11`）。この条件で実行自体が許可されない場合、子プロセスは起動せず、値も渡されません。別の環境変数、GPU backend、モデル状態による判定はありません。

## 実行時の詳細

MCP server はリクエストごとに JSON 設定ファイルを読み直し、`tools/call` では該当 tool の command と `input` を runner に渡します（`apps/host/server/agent/custom-tools-mcp.mjs:22,35-40`）。runner はコマンド起動時に現在の Host 環境を複製し、`STRATA_INPUT` を今回の入力値で上書きした環境を `spawn()` に渡します（`apps/host/server/agent/custom-command-run.mjs:80-89`）。そのため tool 呼び出しごとに値が決まり、Host の環境変数として読み取った値を cache する処理はありません。子プロセスの環境を後から変更して再評価する処理もありません。

設定されたコマンドが正常終了すれば stdout と stderr をまとめた出力が MCP tool の応答に返ります。非ゼロ終了は tool error になり、出力がなければ終了コードを含む文が返ります。コマンド開始失敗、タイムアウト、無効な作業ディレクトリも `ok: false` と説明テキストになります。タイムアウトの既定は 120 秒、設定上限は 3600 秒です（`custom-command-run.mjs:17-20,80-100`; tool 呼び出しへの接続は `custom-tools-mcp.mjs:39-40`）。`STRATA_INPUT` 値そのものを記録する Host のログはこの経路にありません。

## 根拠

- `apps/host/server/agent/custom-tools-mcp.mjs:24-29,35-40` — 入力 schema と MCP 呼び出しから runner への引き渡し。
- `apps/host/server/agent/custom-command-run.mjs:77-100` — 入力の既定値・文字列化、環境の複製と上書き、子コマンド起動および結果・失敗の返却。
- `apps/host/server/agent/tools-settings.mjs:95-114` と `apps/host/server/agent/profile.mjs:298-303` — 有効な command tool の設定ファイル化と MCP server の追加。
- `apps/host/server/agent/README.md:79` — Host の command tool と Manual / Plan の説明。
