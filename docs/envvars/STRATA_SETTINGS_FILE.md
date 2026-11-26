# `STRATA_SETTINGS_FILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

設定ファイルのパスを指定する環境変数。Terminal のセットアップ CLI、Control の Python CLI / MCP サーバー、`strata_control` の install・data folder discovery は、この値が空でなければ指定先をそれぞれの設定ファイルとして使う。Windows では通常 `%APPDATA%/Strata/settings.json`、それ以外では `$XDG_CONFIG_HOME/strata/settings.json`（未設定なら `~/.config/strata/settings.json`）を使うため、アプリはこの環境変数で Terminal の設定と別の `app-settings.json` を選べる（`terminal/setup.py:7276-7294`、`terminal/strata_control/discovery.py:126-135`、`terminal/tools/strata_mcp.py:780-793`）。

Desktop app の host は同じパスを app 側設定として読み書きし、packaged Control / installer の子プロセスにも渡す。`control-runtime.mjs` は components directory がある場合、継承した値が truthy ならそのまま、そうでなければ components の親にある `app-settings.json` を子環境へ設定する（`app/host/server/native-control.mjs:186-189`、`app/host/server/control-runtime.mjs:88-107,140-146`）。

## 値と判定

数値や真偽値への変換はない。Python 側は `os.environ.get(...)` の文字列を truthiness で判定し、truthy ならそのまま `Path(...)` に渡す。Node 側も `||` で truthy 判定する。大文字小文字・空白・パスの存在確認による値検証はなく、空白だけの値もパスとして採用される。値の規則は読み取り経路で次のように分かれる。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Terminal の `setup.py`、`strata_control.discovery`、`tools/strata_mcp.py` | OS 既定パスへ fallback | 空でない任意の文字列。例: `/tmp/app-settings.json`、`relative.json`、` ` | 空文字 `""` は未指定と同じ。`0`、`false`、`true` は文字列として truthy なので無効値ではなくファイル名になる |
| App Host の `controlSettingsFile()` と `controlEnvironment()` | components directory があれば `dirname(components)/app-settings.json`。components がなければ子環境にこの変数を追加しない | 継承した空でない文字列をそのまま使用・転送 | 空文字は `||` により fallback。`0`、`false`、`true` は文字列として採用 |

相対パス、空白を含むパス、存在しないパスを拒む検査はこの変数の読み取り時にはない。Python の `Path` は `expanduser()` も呼ばれない。後続のファイル操作が失敗すれば各機能の fallback / 警告になります（`terminal/strata_control/discovery.py:126-135`、`terminal/setup.py:7276-7280`、`app/host/server/control-runtime.mjs:98`、`app/host/server/native-control.mjs:186-189`）。

## 有効になる条件

- Terminal の設定ファイルを読む `setup.py`、`strata_control`、`strata_mcp.py` の処理で参照される。既定パスの OS 分岐は `WIN` / `os.name == "nt"` で、それ以外は XDG 配下を使う（`terminal/setup.py:7283-7289`、`terminal/strata_control/discovery.py:126-135`）。
- `strata_control.discovery` では、truthy な値が「app mode」の判定にも使われる。この場合、Terminal は自身の設定ファイルから remembered installs を読む一方、別の app 設定ファイルから旧 install を採用する経路を飛ばす。また app mode のときは Terminal / app 間の data-dir 同期と Documents 候補を使わない（`terminal/strata_control/discovery.py:62-65,174-195,258-291`）。ただし明示した `STRATA_INSTALL_DIR` または関数の `explicit` 引数があれば、その install folder だけを調べる優先経路が先にある（`terminal/strata_control/discovery.py:174-181`）。
- `setup.py` の data folder 等の設定読み書き、`strata_control` の保存済み backend 読み書き、MCP サーバーの `data_dir` / 許可 root 算出で、それぞれの設定ファイルパスに反映される（`terminal/setup.py:7292-7306,7428-7430`、`terminal/strata_control/engine_component.py:513-539`、`terminal/tools/strata_mcp.py:780-800`）。CLI の `--data-dir` は data folder の選択値を渡す引数であり、設定ファイルの場所を選び直す引数ではない（`terminal/setup.py:7419-7430,7513-7516`）。
- App Host が packaged mode で Control / installer 子プロセスを開始するとき、`controlEnvironment()` が変数を作成・転送する。Control 子プロセスの環境作成は `runCli()` と installer 起動から呼ばれる（`app/host/server/control-runtime.mjs:89-119,140-146`、`app/host/server/native-control.mjs:201-202`）。
- env 値そのものについて backend、GPU、build macro、モデル状態による有効条件はない。設定ファイルの読取り側がファイル不在・JSON不正を処理するため、空でない値を与えるだけでは設定内容の存在・妥当性は保証されない（`terminal/strata_control/discovery.py:93-99`、`terminal/setup.py:7292-7296`、`terminal/tools/strata_mcp.py:787-793`）。

## 実行時の詳細

Python の各 `settings_path()` / `own_settings_file()` 呼び出し時に `os.environ` を参照し、値を関数間で恒久 cache しない。`setup.py` は選ばれたファイルを `load_settings()` で読み、OS error / JSON parse error は空 dict にする。保存時は親 directory を作り、書込み `OSError` を `could not save {path} ({error})` の警告にする（`terminal/setup.py:7276-7306`）。`strata_control.discovery._read_json()` は I/O・Unicode・JSON error を空 dict にし、install 探索を続ける（`terminal/strata_control/discovery.py:93-99,191-195`）。

`strata_mcp.py` は MCP リクエスト処理から `data_dir()` が呼ばれるたびに設定 JSON を読み、失敗時は `{}` として `root.parent/Strata-data` に fallback する（`terminal/tools/strata_mcp.py:780-800`）。したがって起動後に環境変数自体を変更すれば、以後の path 関数呼び出しが参照する値は変わりうるが、すでに起動済みのプロセス環境を外から変更する手順は Strata にない。

App Host は `controlSettingsFile()` の呼び出し時に `process.env` を見て app 設定ファイルを選ぶ。packaged Control / installer の各 spawn 時には `controlEnvironment()` が子環境 object を組み立てる。Host の `shareDataFolder()` は同期処理の失敗を握りつぶし、共有設定の不調でアプリを停止しない（`app/host/server/native-control.mjs:186-189,201-202`）。

## ログと測定値

この環境変数の値が空であることや、設定ファイルを読めないことだけを理由に出す専用ログは見当たらない。`setup.py` の保存失敗は前述の警告を出す。`setup.py` の読み込み失敗、`discovery._read_json()` の失敗、MCP の settings 読み込み失敗は、それぞれ空設定として扱われる。Host の app / Terminal 間同期エラーも無視される（`terminal/setup.py:7292-7306`、`terminal/strata_control/discovery.py:93-99`、`terminal/tools/strata_mcp.py:787-793`、`app/host/server/native-control.mjs:189`）。この変数の性能測定値は該当しない。

## 根拠

- `terminal/setup.py:7276-7306` — app path と OS fallback、読み込み・保存・警告。
- `terminal/strata_control/discovery.py:57-65,93-99,126-135,174-209,258-291` — app mode、設定ファイル選択、install / data-dir discovery。
- `terminal/strata_control/engine_component.py:513-539` — 保存済み backend の読取り・書込み先。
- `terminal/tools/strata_mcp.py:780-800` — MCP サーバーの設定 path と data folder fallback。
- `app/host/server/control-runtime.mjs:88-119,140-146` — Control / installer 子プロセス環境への値の設定・転送。
- `app/host/server/native-control.mjs:186-202` — Host の app settings path と packaged installer 起動。
- `docs/DETAILS.md:1540` — 通常の Terminal 設定ファイルと `--data-dir` の説明。対象 env による app 固有 path は現行ソースを根拠とした。
