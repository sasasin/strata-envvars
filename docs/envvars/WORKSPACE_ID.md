# `WORKSPACE_ID`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 本体のエンジンや host サーバーがプロセス環境から直接読む設定ではありません。Strata 同梱の HTTP 操作用スクリプト `apps/host/scripts/agent-http.mjs` と `agent3-http.mjs` が、現在の workspace ID を `process.env.WORKSPACE_ID` から取得して、host API のリクエスト JSON の `workspaceId` に載せます。対象コマンドは `stream`、`timeskip`、および `agent-http.mjs` の `plan`、`modeswitch`、`long` です。

host はこの ID をチャットで使う workspace の指定として扱います。agent 経路では選択 workspace のフォルダーを作業場所にし、workspace に限定された skill の適用判定にも渡します。Time-skip では workspace ID から対象フォルダーを選びます。

## 値と判定

| 環境値 | スクリプト側の処理 | host 側での扱い |
|---|---|---|
| 未設定 | `process.env.WORKSPACE_ID` は `undefined`。JSON.stringify は該当プロパティを省く | チャットは保存済み chat folder があればそれを使い、なければ既定 workspace。Time-skip も既定 workspace |
| 空文字 | プロパティに空文字を設定して送る | chat の agent 経路では falsy のため既定 workspace にフォールバック。Time-skip も workspace ID が falsy なので既定 workspace |
| 非空文字列 | trim、数値変換、文字列形式の検証はせず、そのまま送る | 登録 workspace の ID と一致すればその path を使う。不一致なら既定 workspace にフォールバック |

長さ・文字種・大文字小文字の制限、無効値エラー、`WORKSPACE_ID` 専用ログは実装されていません。未設定と空文字ではチャットの agent 経路で異なり、空文字は JSON に含まれた後 host の `workspaceId` 文字列として受け取られますが、どちらも作業場所は既定 workspace になります。workspace ID は CLI 引数や別の環境変数と比較・優先選択されません。

## 有効になる条件

- `agent-http.mjs` / `agent3-http.mjs` を実行し、表に記載したコマンドを使う場合に限り読み取られます。これらは `process.env` をコマンド分岐の中で参照し、起動時の module-level cache はありません。
- 送信先 host がチャット stream または `/api/timeskip/start` を処理するときに効果があります。`STRATA_URL` は API 接続先を指定しますが、`WORKSPACE_ID` の値には影響しません。
- チャット stream の agent 経路では、同じ session の既存 chat folder が指定 ID より優先されます。そうした folder がなければ、登録 workspace の ID に対応するフォルダーを使い、対応しない ID や未指定では host の既定 `WORKSPACE` を使います。
- チャットが通常の remote/native-model 経路へ進む場合も、ID は `selectSkills` に渡され、`onlyIn` が設定された skill はその ID と一致する場合だけ候補になります。`agent3-http.mjs` と `agent-http.mjs` の `stream` は `PLAIN` が truthy なら `agent: false` も送ります。その場合 agent 実行は skip されますが、通常 chat 経路での workspace を使った skill 選別は引き続き行われます。
- Time-skip は `workspaceId` に一致する登録 workspace の path を選び、未指定・空・不一致では既定 workspace を使います。ただし session に既存 chat folder があればそちらを使います。サーバーは選択後に folder の存在、host 自身の folder でないこと、サイズを検査し、条件不成立なら API error を返します。
- `agent3-http.mjs` には `plan` / `modeswitch` / `long` コマンドがなく、これらの workspace 指定は `agent-http.mjs` にだけあります。両スクリプトの `goal` 系コマンドは `workspaceId` を送らず、環境変数は適用されません。

## 実行時の詳細

スクリプトの `stream()` は body を `JSON.stringify` して `/api/chat/stream` に POST します。host は `workspaceId` が文字列の場合だけ受け入れ、それ以外は `null` にします。agent chat の作業場所は `chatFolders.get(chatId)`、指定 workspace path、既定 `WORKSPACE` の順です。通常の remote/native chat 経路では workspace ID は `selectSkills` に渡され、skill が有効で、trigger がメッセージに一致し、かつ `onlyIn` が未指定または ID と一致する場合にその skill が適用されます。server の起動時に環境値をキャッシュするのではなく、クライアントスクリプトが各コマンドの API body を作る時点で値を読みます。

Time-skip の `/api/timeskip/start` handler は、`workspaceId` が文字列なら登録 workspace の path を検索し、見つからなければ既定 `WORKSPACE` にします。その後 chat folder があればそちらを優先します。標準経路で prompt が空なら HTTP 400 `Say what you want made or improved after /time-skip.`、folder が存在しなければ HTTP 400 `Time-skip works on a folder of your own. Choose a folder for this chat, then try again.`、host 自身の folder なら HTTP 400 `Time-skip works on a folder of your own. Choose a workspace folder for this chat, then try again.`、大きすぎる folder なら HTTP 400 `This folder is too big to try a change on a copy. Open a smaller folder for this chat, then try again.` になります。クライアントの `j()` は non-2xx 応答で例外にし、`<path> -> <status> <error>` を含む失敗になります。workspace ID が未登録という理由だけでは失敗しません。

`/api/chat/stream` は message が空なら HTTP 400 `message is required` を返します。workspace ID 自体の不一致は拒否せず、既定 workspace への fallback または skill scope の不一致になります。HTTP が non-2xx ならクライアントの `stream()` が `stream -> <status> <body>` の例外を投げます。server は agent unavailable / skipped などの notice を NDJSON で返し得ますが、`WORKSPACE_ID` を理由とする専用 notice やログはありません。

`docs/DETAILS.md` に `WORKSPACE_ID` の説明は見つかりませんでした。この変数について確認できた機能は同梱 HTTP スクリプトから host API へ workspace ID を転送することです。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:1707-1711`（候補として `WORKSPACE_ID` を掲載）。
- スクリプトの用途説明、直接参照、stream payload: `apps/host/scripts/agent-http.mjs:1-23,83-86,121-125,144-150,164-169,178-183`、`apps/host/scripts/agent3-http.mjs:1-23,68-75,105-109`。
- body の送信と HTTP error handling: `apps/host/scripts/agent-http.mjs:18-23,34-37`。
- chat API の workspace ID 型判定、agent 選択、通常 chat への転送: `apps/host/server/index.mjs:1987-2021,2026-2038`。
- agent 作業フォルダーと workspace skill 選別: `apps/host/server/index.mjs:605-608,634-639,649-655,681-684`、`apps/host/server/skill-selection.mjs:1-7`。
- Time-skip の workspace 解決、session folder 優先、検証とエラー: `apps/host/server/index.mjs:1132-1165`。
