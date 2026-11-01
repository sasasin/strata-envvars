# `CHROME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`CHROME` は Strata 本体の実行時設定ではなく、リポジトリ内の開発・画面確認スクリプトが Playwright の headless browser として起動する実行ファイルのパスを指定します。確認できた参照は `apps/desktop/scripts/` と `apps/host/scripts/` にあるスクリプトです。アプリ本体やサーバーの設定値として読む箇所は確認できませんでした。

## 値と判定

各スクリプトは Node.js の `process.env.CHROME ?? fallback` で評価します。文字列を parse せず、パス文字列として `chromium.launch({ executablePath: ..., headless: true })` に渡します。

| 環境値 | Strata 側の扱い |
|---|---|
| 未設定（`undefined`） | スクリプトごとの既定候補を使います。候補配列では `existsSync` で最初に存在するパスを選びます。 |
| 空文字 | `??` の右辺には進まず、空文字をパスとして後続処理へ渡します。`language-shots.mjs` では falsy 判定により「No Chrome or Edge found; set CHROME.」を stderr に出し、終了コード 1 で終了します。 |
| その他の設定値 | 文字列をそのまま browser の `executablePath` に渡します。存在確認、正規化、trim、妥当性検査、fallback はしません。 |
| 候補のどれも存在しない | `find(existsSync)` は `undefined` を返します。`language-shots.mjs` は明示的にエラー終了します。他の参照箇所はこの値をそのまま Playwright の起動引数に渡します。 |

大半のスクリプトは既定候補に Windows の `C:/Program Files/Google/Chrome/Application/chrome.exe` と Linux の `/usr/bin/google-chrome` を使います。`first-run-ui.mjs` は macOS の Google Chrome パスも加えます。`agent-flow.mjs` と `agent-flow-s4b.mjs` も macOS 候補を含み、`language-shots.mjs` は Windows の Edge も候補に含みます。`process.platform` で候補を絞らず、配列の順番で最初に存在するものを選ぶ実装です。

## 有効になる条件

対象はこれらの Node.js 開発・QA・スクリーンショット用スクリプトを実行するときに限られます。アプリの通常起動、Strata server の環境設定、モデルや backend の選択には使われません。CLI 引数や別の環境変数と `CHROME` の優先順位を決める共通 helper はなく、各スクリプト内で直接参照します。

同名の直接読み取りは次の 15 箇所です。

- `apps/desktop/scripts/make-installer-images.mjs:23`
- `apps/desktop/scripts/make-icons.mjs:20`
- `apps/desktop/scripts/installer-mockups.mjs:22`
- `apps/desktop/scripts/ui-flows.mjs:36`
- `apps/desktop/scripts/first-run-ui.mjs:36`
- `apps/host/scripts/agent2-flow.mjs:26`
- `apps/host/scripts/agent-flow-s4b.mjs:30`
- `apps/host/scripts/agent2-tools-flow.mjs:24`
- `apps/host/scripts/skills-shot.mjs:7`
- `apps/host/scripts/agent-flow.mjs:35`
- `apps/host/scripts/tools-shots.mjs:15`
- `apps/host/scripts/task-flow-s4b.mjs:10`
- `apps/host/scripts/mode-flow-s4b.mjs:12`
- `apps/host/scripts/approval-flow.mjs:21`
- `apps/host/scripts/language-shots.mjs:21`

なお、共有 helper `apps/host/scripts/ui-drive.mjs:5` が読むのは `CHROME_PATH` です。これも `CHROME` とは別名です。`tools/webtest/lib.mjs` が読むのは `CHROME_BIN` です（`tools/webtest/lib.mjs:11-13`）。いずれも本書の対象環境変数には含めません。

## 実行時の詳細

値は各 ES module のトップレベルで一度取得され、その module 実行中はローカル定数が使われます。プロセス環境を実行途中で変更しても再読込するコードはありません。例として、インストーラー画像生成は `CHROME` を `chromium.launch` に渡して headless 起動し、画像を生成します（`apps/desktop/scripts/make-installer-images.mjs:23,45-61`）。アイコン生成も同様に起動します（`apps/desktop/scripts/make-icons.mjs:20,54-63`）。画面フローは各シナリオで browser を起動し、再起動シナリオでは persistent context にも同じパスを渡します（`apps/desktop/scripts/ui-flows.mjs:36,156,686`）。初回起動確認も同じく起動します（`apps/desktop/scripts/first-run-ui.mjs:36,82-94`）。

`language-shots.mjs` だけは、選択された値が falsy の場合に stderr へ `No Chrome or Edge found; set CHROME.` を出して `process.exit(1)` します（`apps/host/scripts/language-shots.mjs:21-22`）。設定値が空文字の場合もこの分岐になります。値が truthy なら headless 起動へ進みます（同:48）。その他のスクリプトでは起動時に値を明示検査せず、そのまま `executablePath` として渡します。したがって、起動失敗時の具体的なエラーや挙動は Playwright/browser 側のものであり、Strata の処理としてはここでは断定しません。

## 根拠

- 15 個の直接読み取りと既定候補: 上記「有効になる条件」の各スクリプトの行を参照。
- Playwright 起動への受け渡し: `apps/desktop/scripts/make-installer-images.mjs:45`、`apps/desktop/scripts/make-icons.mjs:54`、`apps/desktop/scripts/installer-mockups.mjs:59`、`apps/desktop/scripts/ui-flows.mjs:156,686`、`apps/desktop/scripts/first-run-ui.mjs:82`。Host 側では `apps/host/scripts/agent2-flow.mjs:26,30`、`apps/host/scripts/agent-flow-s4b.mjs:30,35`、`apps/host/scripts/agent2-tools-flow.mjs:24,28`、`apps/host/scripts/skills-shot.mjs:7-8`、`apps/host/scripts/agent-flow.mjs:35-45`、`apps/host/scripts/tools-shots.mjs:15,44`、`apps/host/scripts/task-flow-s4b.mjs:10,12`、`apps/host/scripts/mode-flow-s4b.mjs:12,14`、`apps/host/scripts/approval-flow.mjs:21,44`、`apps/host/scripts/language-shots.mjs:21-22,48`。
- 似た名前だが別の値: `apps/host/scripts/ui-drive.mjs:1-5,17` は `CHROME_PATH`、`tools/webtest/lib.mjs:3,11-19` は `CHROME_BIN`、`apps/host/scripts/qa2-flows.mjs:3,15,25` は `STRATA_CHROME` を読みます。
