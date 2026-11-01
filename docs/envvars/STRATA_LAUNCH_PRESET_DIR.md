# `STRATA_LAUNCH_PRESET_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の状態は `## main...origin/main` で、`git status --short --branch` に変更ファイルの表示はありませんでした。

## 役割

Strata Terminal の launch preset を保存・列挙・読み込み・削除するディレクトリを指定します。preset は `strata launch --save-preset` や TUI から保存され、`--preset`、`--list-presets`、`--delete-preset` などで使われます。Python の `strata_cli.launch.store` が値を読みます。engine の C++/CUDA/HIP/SYCL 実装やサーバーの環境変数として読む箇所はありません。

## 値と判定

| 環境変数の状態 | 使用するディレクトリ |
|---|---|
| 未設定 | `strata_control.profiles.profile_dir()` の親ディレクトリにある `launch-presets` |
| 空文字 | 未設定と同じ既定ディレクトリ（`if explicit` が偽になる） |
| 空でない文字列 | `Path(value).expanduser()` の結果をそのまま使用 |

数値や真偽値への変換、文字列の trim、存在確認、絶対パス化はありません。空白だけの値も空ではないためパスとして使われます。`~` は `expanduser()` で展開され、相対パスは絶対化されず、通常の `Path` 操作によりプロセスの現在ディレクトリから解決されます。環境変数に対する個別の CLI 上書きはありません。CLI の `--preset` はファイル名を選び、`--save-preset` は名前を指定するもので、ディレクトリ指定ではありません。

既定場所は `STRATA_PROFILE_DIR` が非空ならその展開済みパスの親、そうでなければ OS ごとの profile directory に追従します。後者は Windows で `APPDATA`（なければ home の `AppData/Roaming`）、それ以外で `XDG_CONFIG_HOME`（なければ `~/.config`）を使い、その下の `strata/profiles` を profile directory とします。したがって `STRATA_LAUNCH_PRESET_DIR` が非空ならこれらの既定場所を置き換え、空または未設定ならそれらの値に間接的に従います。

## 有効になる条件

Strata Terminal の Python launch preset store を通る操作で有効です。OS、GPU backend、build macro、モデル状態による分岐はありません。通常の `strata launch` 操作に加え、同モジュールの TUI からの保存・読み込みや preset 管理で、store の関数が呼ばれたときに使われます。エンジン起動後のサーバー処理がこの変数を読む実装は見つかりません。

変数が非空でも、指定先が存在しない／ディレクトリでない場合の扱いは操作ごとに異なります。列挙はディレクトリでなければ空リストを返します。読み込み・削除では該当 preset がなければ `PresetError` になります。保存時は親ディレクトリを作成します。作成不能などの `OSError` は CLI 共通のエラー経路に渡されます。

## 実行時の詳細

値は `preset_dir()` が呼ばれるたびに `os.environ.get()` で読み直され、結果を保持する cache はありません。preset の各操作が `_path()` または `list_presets()` 経由でディレクトリを得るため、実行中に環境を書き換えた場合も次の呼び出しから反映されます。既定パスを求めるときは、その時点で `profiles.profile_dir()` も評価されます。

個別 preset は `slug(name) + ".json"` の名前で指定ディレクトリに置かれます。列挙は `*.json` を読み、壊れた JSON などの `OSError` / `ValueError` はそのファイルだけ読み飛ばします。名前を指定して読み込み、対象がない場合は `There is no saved preset called '…'.` と候補案内を含む `PresetError` になります。破損・読み取り不能ファイルでは `The saved preset '…' cannot be read...`、JSON が object でない場合は `The saved preset '…' is damaged.` になります。`strata launch` のエラー経路はこれらを stderr の `strata: ...`（human 出力）または JSON エラーとして返し、終了コード 2 にします。ファイルシステム操作の `OSError` は CLI 共通処理でエラー表示され、終了コード 6 です。

保存先は複数の `save`, `load`, `_private_write` 呼び出しで使われます。`_private_write` は親ディレクトリを作成し、JSON を一時ファイルに書いて置換します。preset 内容には API key が含まれ得るため、Strata は Unix でファイル mode `0600` を設定し、Windows では現在ユーザーに制限する処理も試みます。この環境変数はその保存場所を変えるだけで、preset の値や engine に渡す設定の優先順位は変更しません。

## 根拠

- `strata_cli/launch/store.py:27-36` — 環境値の読み取り、空値時の既定パス、明示値の `expanduser()`、preset ファイル名。
- `strata_control/profiles.py:38-45` — 既定場所を決める profile directory と `STRATA_PROFILE_DIR` / `APPDATA` / `XDG_CONFIG_HOME` の関係。
- `strata_cli/launch/store.py:39-60,75-103,115-143` — 保存・読み込み・列挙・削除の I/O、エラー処理、読み取りごとのパス取得。
- `strata_cli/launch/settings.py:355-361` — preset 名をファイル名に変換する `slug()`。
- `strata_cli/launch/cmd.py:75-85,135,149-150,205-211,686-715,753-862,913-918` — CLI オプション、preset 読み込み／保存／列挙／削除とエラー応答。
- `strata_cli/cli.py:2153-2155,2174-2183` — launch command への振り分けとファイルシステムエラー処理。
- `strata_cli/launch/app.py:60-69,240-273,313-319,354-379,443-459` — TUI での preset 列挙、読み込み、保存。
- `docs/TERMINAL_LAUNCH.md:115-116` — launch preset と profiles folder の配置に関する説明。ソースの既定場所と整合します。
