# `STRATA_CONNECTION_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata CLI と portable monitor bundle が使う、保存済み接続情報（JSON）のディレクトリを指定します。保存接続にはサーバー URL や資格情報を参照する環境変数名が格納されますが、資格情報の値そのものは保存しません。GPU engine の動作を制御する変数ではありません。

接続ファイルの作成・表示・一覧・更新、`STRATA_CONNECTION` または `--connection` で保存接続を選ぶ status/monitor/logs/config コマンド、および `strata models list --served` の接続解決で使われます。通常の URL 接続では、この変数だけで URL は選択されません。

## 値と判定

`strata_cli/connections.py:72-90` が `os.environ.get("STRATA_CONNECTION_DIR")` を呼び出し、次のようにディレクトリを選びます。

| 値・条件 | 選ばれるディレクトリ／結果 |
|---|---|
| 未設定、または空文字 | Windows では `%APPDATA%/Strata/connections`。`APPDATA` も未設定または空なら `~/AppData/Roaming/Strata/connections`。それ以外の OS では `$XDG_CONFIG_HOME/strata/connections`。`XDG_CONFIG_HOME` が未設定または空なら `~/.config/strata/connections`。 |
| 空でない絶対パス | `Path(...).expanduser()` 後のパス。先頭の `~` は展開されます。 |
| 空でない相対パス | `ConnectionError("STRATA_CONNECTION_DIR must be absolute")`。例外の既定終了コードは 2 です。 |

値の trim、環境変数形式の展開、数値変換はしません。空白だけの値も空文字ではなく相対パスとして扱われ、拒否されます。絶対パスのディレクトリが存在する場合、実体がディレクトリでない場合は「connection directory must be owner-only」（終了コード 5）になります。POSIX ではさらに所有者が実行ユーザーであり、group/other の権限ビットがないことを検査します。Windows ではこの POSIX 所有者・mode 検査を行いません (`strata_cli/connections.py:85-90`)。

## 有効になる条件

- `strata connection create/show/list/set` と `strata config show` は接続ストアを直接使います (`strata_cli/monitor_commands.py:132-164`)。
- `status`、`monitor`、`logs`、`config show` および served model listing は接続解決を使います。`--connection` が指定されればその保存接続を読み、未指定かつ `--url` も未指定なら `STRATA_CONNECTION` を選択名として読みます (`strata_cli/connections.py:273-301`, `strata_cli/monitor_commands.py:195-199`, `strata_cli/cli.py:568-572`)。
- URL 選択の優先順位は `--url` / `--connection` と `STRATA_CONNECTION` / `STRATA_URL` の規則に従います。`--url` と `--connection` の同時指定はエラーです。選択する保存接続があれば、その URL/prefix/credential reference を読みます。`STRATA_CONNECTION_DIR` はそのファイルの場所だけを変えます (`strata_cli/connections.py:277-301`)。
- Python の接続モジュールは source CLI と portable monitor bundle で共有される設計です (`strata_cli/connections.py:1-5`; `docs/TERMINAL.md:44,188`)。CUDA/HIP/SYCL、build macro、モデル状態による条件はありません。

## 実行時の詳細

値はモジュール読み込み時の定数や `static` に cache されません。`connection_dir()` が呼ばれるたびに `os.environ` を読みます (`strata_cli/connections.py:72-73`)。そのため、同一プロセス内でも呼び出し間に値が変更されれば次の呼び出しで再評価されます。

`load()` は選んだディレクトリ内の `<name>.json` を開きます。ファイルがなければ `connection '<name>' is not saved; use strata connection create`（終了コード 5）、不正なファイルや権限条件の違反も終了コード 5 の `ConnectionError` になります (`strata_cli/connections.py:93-94,128-146`)。一覧ではディレクトリが存在しない場合は空一覧を返します。作成・更新時はディレクトリを private mode で作成し、既存ディレクトリも検証します (`strata_cli/connections.py:83-90,149-164,190-193,221-242`)。

monitor 系 CLI は `ConnectionError` を捕捉し、通常表示では stderr に `strata: <message>`、JSON 表示では JSON error を出し、例外の終了コードを返します (`strata_cli/monitor_commands.py:124-129,231-240`)。相対パス指定時はこの経路で終了コード 2、ディレクトリ条件や接続ファイルの問題では通常終了コード 5 になります。

## 根拠

- 環境値の読み取り、空値判定、OS ごとの既定値、絶対パス条件、ディレクトリ検査: `strata_cli/connections.py:72-90`。
- 接続ファイルパスと読み込み・失敗処理: `strata_cli/connections.py:93-94,128-146`。
- 一覧・作成・更新での適用: `strata_cli/connections.py:149-164,190-193,221-242,256-270`。
- 保存接続の選択と URL の優先順位: `strata_cli/connections.py:273-301`。
- CLI での接続ストア利用とエラー出力: `strata_cli/monitor_commands.py:132-164,195-199,231-240`; served model listing: `strata_cli/cli.py:568-572`。
- 保存接続と既定場所に関する文書上の説明: `docs/TERMINAL.md:44,188`。コード上は Windows ACL の検査は見当たらず、同文書も Windows ACL の適格性を未解決事項としている。
