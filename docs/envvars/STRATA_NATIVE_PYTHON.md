# `STRATA_NATIVE_PYTHON`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`app/host` の Python resolver に対し、ホストが Python スクリプトを起動するときの interpreter 候補を明示します。`server/python-resolver.mjs` は `STRATA_PYTHON` を先に選び、空でなければ `STRATA_NATIVE_PYTHON` を選択します。どちらも空なら呼び出し側が渡す Control 同梱 Python、リポジトリ `.venv`、OS ごとの候補へ進みます。resolver の利用先には host の tuning / Time-skip と、source checkout の native MCP client、auto-tuner、更新系操作があります（`app/host/server/python-resolver.mjs:2-13,33-53`; `app/host/server/index.mjs:800-805,954-963`; `app/host/server/native-control.mjs:142,191,195-205,735-741`）。

この変数は Strata の C++/GPU engine の設定ではなく、ホスト側の interpreter 選択です。source checkout の native server 起動は `venvPython(repo())` を直接使うため、この変数の選択対象外です（`app/host/server/native-control.mjs:625,689`）。packaged app の native MCP client と Control 子プロセスも Control component の interpreter を直接使い、Control 子プロセスの環境から `STRATA_NATIVE_PYTHON` を削除するため、その経路ではこの変数による選択は行われません（`app/host/server/native-control.mjs:137-145,195-201`; `app/host/server/control-runtime.mjs:88-100,140-146`）。

過去の handover 文書は、未指定時に installed venv またはシステム Python を使うと記しています（`docs/history/apps/host/docs/native-engine-handover.md:42`）。現行 resolver では `STRATA_PYTHON` と bundled Control がそれらより先に評価され、OS ごとの候補も列挙されています。上記は調査対象 commit のコードで確認した現在の分岐です（`app/host/server/python-resolver.mjs:36-53`）。

## 値と判定

値全体の形式検証や interpreter の起動確認は、明示値には行いません。JavaScript の `||` による選択なので空文字は偽となり、空でない文字列はそのまま `command` として返されます。空白だけの値も非空として採用されます。`true`、`1`、大文字小文字、前後の空白を特別扱いせず、パスや実行可能ファイル名として検査・正規化もしません（`app/host/server/python-resolver.mjs:33-39`）。

| 条件 | unset / 空文字 | 設定時に有効になる値 | 無効・選択されない値 |
|---|---|---|---|
| resolver を使う source checkout 経路 | `STRATA_PYTHON` も空なら次の候補へ進む | 任意の非空文字列。例: `/opt/python/bin/python`, `python3`, `true`, `0`, `0anything` | `STRATA_PYTHON` が非空ならこの変数は優先順位で選ばれない。自身の空文字は interpreter として採用されない |
| native server 起動（source checkout） | `.venv` Python を使う | 該当なし | resolver を通らないため設定値は参照されない |
| packaged app の native-control 経路 | Control の bundled interpreter を直接指定する | 該当なし | resolver を通らず、Control 子プロセスの環境からも削除される |

source checkout で変数未設定または空文字のときは、`STRATA_PYTHON` が非空ならそちら、次に `control.python`、次に repo の `.venv` Python、Windows なら起動確認に成功する `py -3` または `python.exe`、最後は `python.exe` fallback、POSIX なら存在する Homebrew Python 3.11 / 3.10、最後に `python3` が選ばれます。明示値は候補検査を通らず、失敗しても後順位候補へ切り替わりません（`app/host/server/python-resolver.mjs:36-53`）。

## 有効になる条件

- `app/host` の resolver を通る経路で使われます。`STRATA_PYTHON` が非空ならそちらが優先されます（`app/host/server/python-resolver.mjs:36-39`）。
- `server/index.mjs` はモジュール初期化時に resolver を一度呼び、その結果を tuning と Time-skip などで共有します。起動後に環境変数を書き換えても、この interpreter 選択には反映されません（`app/host/server/index.mjs:800-805,886-895,954-963`）。
- `native-control.mjs` の source-checkout 経路は native MCP client、auto-tuner、更新系操作の Python 起動時に resolver を呼びます。選択結果は入力値を含むキーで Map にキャッシュされ、同じ repo / Control Python / `STRATA_PYTHON` / `STRATA_NATIVE_PYTHON` / platform の組み合わせでは再利用されます。値が変われば別キーです（`app/host/server/python-resolver.mjs:31-35,54-56`; 呼び出し箇所 `app/host/server/native-control.mjs:142,191,197,735`）。
- source checkout の native server 起動は `.venv` interpreter を直接指定し、存在確認も行います。`.venv` がなければ “The Strata Python environment is missing. Use Download / repair first.” で失敗します。`STRATA_NATIVE_PYTHON` はこの経路に影響しません（`app/host/server/native-control.mjs:625,689`）。
- `native-control.mjs` の calibration は resolver で選んだ Python を `.venv` の Python に置き換えます（`.venv` がなければ “Prepare the Python environment first.” で失敗）。従ってこの操作では変数は実行 interpreter を決めません（`app/host/server/native-control.mjs:735-737`）。
- packaged app では Control component の interpreter を使い、`controlEnvironment` は `STRATA_NATIVE_PYTHON` と `STRATA_PYTHON` を子環境から削除します（`app/host/server/native-control.mjs:142-145,197-201`; `app/host/server/control-runtime.mjs:88-100`）。

## 実行時の詳細

resolver は変数を数値・真偽値に変換せず、選んだ文字列を `{ command, args: [] }` として返します。明示値について `pythonStarts` は呼ばれません。したがって、パスが存在しない、実行できない、または Python でない場合でも選択時点では検出されず、起動側の spawn 結果に委ねられます。候補 fallback のうち Windows の `py -3` / `python.exe` だけは `spawnSync` で `-c 'import sys'` を実行して確認します（`app/host/server/python-resolver.mjs:23-29,36-53`）。

`index.mjs` および source 経路の native MCP / 更新子プロセスの環境には元の環境が複製されるため、`STRATA_NATIVE_PYTHON` も環境に残ります。ネイティブ server は別経路で、選択した `.venv` interpreter に Python ログ用環境変数を加えて起動します（`app/host/server/index.mjs:892-895`; `app/host/server/native-control.mjs:201,625,689,741`; `app/host/server/control-runtime.mjs:82-85`）。本書は、子プロセスや外部ライブラリが同名変数をどう扱うかは説明しません。

resolver 自体は選択ログを出しません。無効な明示値を選んだ場合の失敗は起動先で観測されます。tuning は spawn error を `{ ok: false, error }` として返します。native MCP client は起動 error を snapshot に設定し、stderr を `control` log に追加し、終了時に接続待ちを reject します。更新系操作は spawn error で reject し、子 stdout / stderr の内容を job log に追加します（`app/host/server/index.mjs:890-905`; `app/host/server/native-control.mjs:201-205,741`）。

## 根拠

- `app/host/server/python-resolver.mjs:2-13,19-29,31-56` — resolver の対象、候補順、値選択、Windows の候補起動確認、キャッシュ。
- `app/host/server/index.mjs:800-805,886-905,954-963` — module 初期化時の選択と tuning / Time-skip の利用。
- `app/host/server/native-control.mjs:137-145,142,191,195-205,625,689,735-741` — source / packaged の interpreter 選択、native server の `.venv` 固定、子プロセス起動、失敗処理、calibration の例外。
- `app/host/server/control-runtime.mjs:82-85,88-100,140-146` — source server 環境と Control 子環境での変数保持・削除。
