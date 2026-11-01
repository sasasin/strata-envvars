# `STRATA_DATA_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata Terminal のインストーラーでは Terminal 本体の配置ルートを指定します。Linux/macOS の `packaging/install.sh` と Windows の `packaging/install.ps1` がこの値を読み、`terminal/<version>` と `terminal/current` をその下に作ります（`packaging/install.sh:24-27,98-100,125-129`、`packaging/install.ps1:45-46,65-68,122-129`）。

実行時には、`strata launch` のインストール探索がこのルートの `install` サブフォルダーも候補に加えます。そこに保存済みモデル設定があれば、現在の Terminal フォルダーより先に使います（`strata_control/discovery.py:160-191`）。また、ランチャーの計画表示では、CLI で選んだモデルデータフォルダー、またはこの環境変数の値と現在のインストール場所を比べ、外にある既存インストールを使う場合に警告文を追加します（`strata_cli/launch/runner.py:39-55,2038-2055`）。

## 値と判定

値はパス文字列として扱われ、環境変数自体の形式検査や存在確認はありません。空白の trim や変数値の正規化も行われません。各読み取り箇所の扱いは次のとおりです。

| 読み取り箇所 | 未設定・空文字 | 非空値 |
|---|---|---|
| Linux/macOS インストーラー | どちらも既定値 `${XDG_DATA_HOME:-$HOME/.local/share}/strata` を使用 | その文字列を Terminal の配置ルートに使用 |
| Windows インストーラー | どちらも `%LOCALAPPDATA%\Strata`。ただし `LOCALAPPDATA` も空ならエラー終了 | `LOCALAPPDATA` が空でもその値を配置ルートに使用 |
| インストール探索 (`discovery.places`) | `install` 候補を追加しない | `~` を展開した値の下の `install` を候補に追加 |
| ランチャーの計画警告 | CLI の `data_dir` がなければ選択値なしとして警告判定をしない | CLI の `data_dir` が truthy ならそちらを使い、それ以外は環境変数を使う |
| `tools/dgx_smoke.py` | `~/Strata-data` | argparse の `--data-dir` 既定値として使用。明示した `--data-dir` が優先 |

インストール探索では `STRATA_INSTALL_DIR`（または呼び出し元から渡された明示的な `explicit` 引数）が存在すると、その場所だけを返して `STRATA_DATA_DIR` の候補追加を行いません。`STRATA_INSTALL_DIR` は `None` かどうかで判定されるため、空文字でも設定されていれば `Path("")` を明示場所として扱います（`strata_control/discovery.py:160-172`）。

ランチャーの `--data-dir` はモデルファイルの保存先で、値は `strata_cli/launch/cmd.py:226-231` でフォルダー検査を受けて設定に反映されます。これはインストーラーの Terminal 配置先や `discovery.places` の探索条件を切り替える引数ではありません。計画警告の比較値を選ぶときにだけ、truthy な CLI `data_dir` が `STRATA_DATA_DIR` より優先されます（`strata_cli/launch/runner.py:39-55`）。

## 有効になる条件

- `packaging/install.sh` は Linux/macOS 用インストーラー、`packaging/install.ps1` は Windows 用インストーラーです。GPU backend や build macro の条件はありません（`packaging/install.sh:1-3,24-27`、`packaging/install.ps1:1-3,45-46`）。
- 実行時のインストール探索で `STRATA_DATA_DIR` が候補になるのは、`STRATA_INSTALL_DIR` / 明示 `explicit` が未指定のときだけです。候補に保存済み設定がなければ結果から落ち、後続候補（Terminal 自身、記憶済み場所、アプリの場所など）が使われます（`strata_control/discovery.py:164-191`）。候補は順番に評価され、最初に設定ファイルが見つかった場所が `find_install()` の結果になります（同 `:195-203`）。
- 計画警告は、選択値と探索場所があり、先頭の場所が `source == "explicit"` でなく、その場所が選択値の内側にない場合に生成されます。`--plan` の preflight から呼ばれ、通常の起動を強制停止する処理ではありません。警告は「data folder only says where model files are kept」と明記します（`strata_cli/launch/runner.py:45-55,2038-2055`）。

## 実行時の詳細

インストーラーは起動時に値を変数へ一度読み込み、その後のダウンロード展開先と `current` リンク／ジャンクションの作成先に使います。Linux/macOS では `${STRATA_DATA_DIR:-...}` により未設定と空文字が同じ既定値になります。値が空白だけなら既定値にはならず、その文字列が使われます（`packaging/install.sh:24-27,98-100,125-129`）。Windows も PowerShell の真偽判定により未設定と空文字は同じ扱いです。両方が空の場合は `strata installer: Windows did not say where your user folder is...` を標準エラーに出して停止します。非空値があれば `%LOCALAPPDATA%` は不要です（`packaging/install.ps1:45-46`）。

インストール探索の Python 関数は呼ばれるたびに渡された `environ`（省略時は `os.environ`）を参照し、モジュール内の値キャッシュはありません。非空の `STRATA_DATA_DIR` から `install` 候補を作り、`config_files()` がそのフォルダー内で `strata-*.json`（shared-settings を除く）を見つけた場合だけ候補に残します（`strata_control/discovery.py:141-149,160-191`）。この候補が先にあると、保存済み設定を持つ Terminal 配下のインストールが、呼び出し元の `here` より優先され得ます。

ランチャーの `install_isolation_words()` は候補探索結果を受けて計画警告を組み立てます。CLI の選択値を優先し、なければ `os.environ` を参照します。選択値または候補がない場合、先頭候補が明示インストールの場合、あるいはその候補が選択値の内側なら警告を返しません。外側なら「Strata is using the earlier install ... not a clean one ...」という文面を返し、`preflight_words()` が計画の警告一覧に追加します。例外はこの警告処理内で握りつぶされるため、そこでの失敗は警告なしになります（`strata_cli/launch/runner.py:39-55,2038-2055`）。

同梱開発ツール `tools/dgx_smoke.py` では、環境変数を argparse の `--data-dir` 既定値として読みます。コマンドラインで `--data-dir` を指定すると argparse がその値を使います。環境変数が空文字の場合は `or` により `~/Strata-data` にフォールバックします（`tools/dgx_smoke.py:74-85`）。

## 根拠

- インストーラーの既定値と配置: `packaging/install.sh:20-27,98-100,125-134`、`packaging/install.ps1:18-19,45-46,65-69,122-137`。
- インストール探索・優先順位: `strata_control/discovery.py:160-203`。設定ファイル候補の条件: 同 `:141-149`。
- ランチャーの CLI データフォルダー検査と反映: `strata_cli/launch/cmd.py:90-93,226-231`。環境変数との警告比較・表示: `strata_cli/launch/runner.py:39-55,2038-2055`。
- 同梱 DGX smoke ツールの既定値: `tools/dgx_smoke.py:74-85`。

