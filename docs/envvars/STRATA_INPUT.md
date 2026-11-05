# `STRATA_INPUT`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

Strata ホストアプリの「Settings → Tools」で登録した command ツールを実行するとき、ツール呼び出しの `input` をコマンドの子プロセス環境へ渡します。Strata 自身がこの環境変数を読み取って処理するのではなく、コマンド起動時に `STRATA_INPUT` を環境へ設定します。したがって値をどう解釈するかは起動されたコマンド側の処理です。

## 値と判定

MCP の command ツール入力 schema では `input` は任意の文字列です。未指定なら `runCommand` の引数既定値 `''` が使われ、明示的な `null` も環境設定時に `''` になります。それ以外は JavaScript の `String(...)` で文字列化されます。文字列の trim、数値変換、真偽値判定、長さ制限はこの環境変数を作る箇所にはありません。

| 呼び出し引数 `input` | 子プロセスの `STRATA_INPUT` |
|---|---|
| 省略 / `undefined` | 空文字列（引数既定値） |
| `null` | 空文字列 |
| 空文字列 | 空文字列 |
| その他 | `String(input)` の結果 |

## 有効になる条件

- ホストの agent profile に有効な command ツールが含まれ、そのツール呼び出しが `custom-tools-mcp.mjs` に到達する必要があります。有効な command ツールだけがツール JSON に書かれ、command のみのサーバーは command mode で起動されます（`apps/host/server/agent/tools-settings.mjs:99-111`, `apps/host/server/agent/profile.mjs:298-303`）。
- Manual モードでは command ツール実行前に確認を求めます。Plan モードは接続ツールを拒否するため、この経路ではコマンドは実行されません（`apps/host/server/agent/plugins/strata-gate.mjs:326-348,364-373`）。
- `STRATA_INPUT` の値を Strata 内で読み取る OS / backend / model / build macro 条件はありません。シェルの選択（Windows の PowerShell / cmd、その他の sh など）は起動コマンドの実行方法を決めますが、値の変換規則は変えません（`apps/host/server/agent/custom-command-run.mjs:41-49,78-87`）。

## 実行時の詳細

MCP サーバーは command ツールの呼び出しから `args.input` を `runCommand` に渡します。`runCommand` はコマンド起動ごとに `spawn` の `env` を作り、ホストプロセスの `process.env` を継承した上で `STRATA_INPUT` を設定値で上書きします。ホスト側に同名変数が既にあっても、そのコマンドの入力（未指定なら空文字列）が優先されます。プロセス起動時に値を固定保存する cache はなく、各コマンド呼び出しで設定します（`apps/host/server/agent/custom-tools-mcp.mjs:35-40`, `apps/host/server/agent/custom-command-run.mjs:78-87`）。

起動に失敗した場合は MCP tool result が `isError: true` となり、`The command could not start in ...` の文面が返ります。起動後は stdout と stderr をまとめて収集し、終了コード 0 なら成功、それ以外なら失敗として結果を返します。既定 timeout は 120 秒で、超過時はプロセスツリーを終了し `The command was stopped after ... seconds.` を返します。出力は 20,000 文字で切り詰めます。これらはコマンド実行結果の処理であり、`STRATA_INPUT` 自体の値をログ出力する処理ではありません（`apps/host/server/agent/custom-command-run.mjs:18-20,70-72,88-99`; MCP 結果への変換は `apps/host/server/agent/custom-tools-mcp.mjs:39-40`）。

## 根拠

- `apps/host/server/agent/custom-tools-mcp.mjs:24-28,35-40` — `input` schema と optional 入力の `runCommand` への受け渡し、失敗結果の MCP 返却。
- `apps/host/server/agent/custom-command-run.mjs:78-87` — 未指定時の既定値、nullish 値の空文字化、`String` 変換、子プロセス環境への上書き設定。
- `apps/host/server/agent/custom-command-run.mjs:88-99` — stdout/stderr の収集、timeout、出力上限、終了コードによる結果。
- `apps/host/server/agent/tools-settings.mjs:99-111` と `apps/host/server/agent/profile.mjs:298-303` — 有効な command ツールの公開と専用ツールサーバーの構成。
- `apps/host/server/agent/plugins/strata-gate.mjs:326-348,364-373` — Manual の確認と Plan の拒否。
