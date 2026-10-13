# `APPDATA`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Windows 上のセットアップと同梱 MCP サーバーが、ユーザーごとの `settings.json` の保存・読み込み場所を決めるために参照する。Strata のエンジン実行時設定ではない。設定ファイルにはセットアップ済みデータフォルダー (`data_dir`)、過去のインストール先 (`installs`)、PC ごとの調整結果 (`calibration`) などが保存される。MCP サーバーは同じファイルから `data_dir` を読み、Strata フォルダーとともに操作を許すルートとして扱う。

## 値と判定

| 状態 | Windows で使う設定ファイルの場所 |
| --- | --- |
| `APPDATA` 未設定 | `Path.home() / "AppData" / "Roaming" / "Strata" / "settings.json"` |
| `APPDATA` が空文字 | 未設定時と同じ既定値 |
| `APPDATA` が空でない文字列 | `Path(APPDATA) / "Strata" / "settings.json"` |

値は `os.environ.get("APPDATA") or ...` で選ばれ、そのまま `Path` に渡される。空白だけの値も空とはみなされず、前後の空白除去、文字列の正規化、存在確認はこの箇所では行わない。相対パスが与えられた場合に絶対パスへ解決する処理もない。

## 有効になる条件

- `setup.py` と `tools/strata_mcp.py` はそれぞれ `WIN = os.name == "nt"` をモジュール読み込み時に決める。`WIN` が真のときだけ `APPDATA` を参照する。
- Windows 以外では `APPDATA` は読まれず、代わりに `XDG_CONFIG_HOME`、未設定または空なら `Path.home() / ".config"` が基準になる。
- セットアップの `data_folder(requested)` では CLI の `--data-dir` があればそれが既存の `data_dir` 設定より優先される。CLI 指定がなければ設定済み `data_dir`、それもなければ Strata フォルダーの隣の `Strata-data` が使われる。`APPDATA` はこの設定を読む・保存するファイルの場所を選ぶだけで、これらの値の優先順位は変更しない。

## 実行時の詳細

`setup.py` の `settings_path()` は関数呼び出しごとに環境変数を参照する。`load_settings()` はそのパスから UTF-8 の JSON を読み、読み込み失敗 (`OSError`) または JSON 不正 (`ValueError`) の場合は空の辞書を返す。`save_settings()` は親ディレクトリーを作って JSON を書き、書き込み時の `OSError` は `could not save <path> (<error>)` の警告にする。セットアップ開始時のデータフォルダー選択と保存、前回のインストール引き継ぎ、および調整値の読み書きがこの設定を利用する。

同梱 `tools/strata_mcp.py` の `Manager.settings_path()` も同じ Windows のパス規則を使う。`data_dir()` はファイルの読み込みまたは JSON 解析に失敗した場合、あるいは辞書内に有効な `data_dir` がない場合、MCP 管理対象 Strata フォルダーの隣の `Strata-data` を返す。`allowed_roots()` は Strata フォルダーとこのデータフォルダーを許可ルートにする。環境変数自体の値はキャッシュされず、各 `settings_path()` 呼び出し時に参照される。一方、Windows/非 Windows の分岐はモジュール読み込み時に決まる。

## 根拠

- `setup.py:62` は `WIN` を定義し、`setup.py:3695-3713` は設定ファイルパス、読み込み、保存、失敗時の扱いを実装する。
- `setup.py:3805-3815` は `--data-dir`、保存済み `data_dir`、既定の `Strata-data` の選択を行い、`setup.py:3854-3855` はインストール先とデータ先を保存する。
- `setup.py:4169-4172` と `setup.py:4182-4194` は調整結果の保存・再利用で設定ファイルを使う。
- `tools/strata_mcp.py:44` および `tools/strata_mcp.py:435-449` は MCP 側の OS 判定、`APPDATA` を使ったパス決定、`data_dir` 読み込み、許可ルートを実装する。
- `docs/INSTALL.md:197-200` と `docs/DETAILS.md:423-427` は、Windows の `%APPDATA%\\Strata\\settings.json` にデータフォルダーの場所を記憶する説明をしており、コードと一致する。
