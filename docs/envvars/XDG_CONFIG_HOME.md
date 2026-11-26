# `XDG_CONFIG_HOME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata のターミナル版・セットアップ・接続管理・プロファイル管理が、ユーザー設定ファイルの場所を決めるために読む。Unix 系環境では、主に `${XDG_CONFIG_HOME}/strata/` を使い、未設定時は `~/.config/strata/` を使う。設定ファイルは `settings.json`、`profiles/`、`connections/` に分かれる。調査した Strata 所有コードでは、値はファイル保存先と Linux デスクトップの既定モデル場所決定に使われ、推論計算やバックエンド選択を変える用途は見つからない。

デスクトップホストは別に、Linux で既定モデル場所を決める際、`user-dirs.dirs` を読むディレクトリとしてこの変数を参照する。ここでは `STRATA_MODELS_DIR` が明示されていない場合に限り、また `XDG_DOCUMENTS_DIR` が環境変数で与えられていない場合に限り参照される（`app/host/server/model-directory-default.mjs:8-25`）。

## 値と判定

この変数を真偽値や数値として parse する実装はない。値はディレクトリパス文字列として使われ、内容の形式、大文字小文字、空白、数値らしさは検証されない。`0`、`true`、`false` もパス文字列として扱われる。大半の読み取り箇所では未設定と空文字のどちらも既定値に戻るが、プロファイル保存先では空文字が既定値にならない。

| 読み取り経路 | unset | 空文字 | 非空値の扱い |
|---|---|---|---|
| Unix 系の `settings.json`（セットアップ、設定探索、MCP ツール、デスクトップホストがターミナル設定を探す場合） | `~/.config/strata/settings.json` | 同じ既定値 | `<値>/strata/settings.json` |
| Unix 系の接続保存先 | `~/.config/strata/connections` | 同じ既定値 | `<値>/strata/connections` |
| Unix 系のプロファイル保存先 | `~/.config/strata/profiles` | `strata/profiles`（相対パス） | `<値>/strata/profiles` |
| Linux デスクトップの Documents 設定探索 | `<home>/.config/user-dirs.dirs` を読む | `<home>/.config/user-dirs.dirs` を読む | `<値>/user-dirs.dirs` を読む |

根拠は `terminal/strata_control/discovery.py:126-134`、`terminal/setup.py:7276-7289`、`terminal/tools/strata_mcp.py:780-785`、`terminal/strata_cli/connections.py:72-90`、`terminal/strata_control/profiles.py:38-46`、`app/host/server/model-folder.mjs:67-72`、`app/host/server/model-directory-default.mjs:14-25`。Python の `or` と JavaScript の `||` を使う箇所は空文字を fallback させる一方、`profiles.py` は `os.environ.get(name, default)` なので、設定済みの空文字をそのまま `Path` に渡す。

パスの絶対性や `~` 展開を `XDG_CONFIG_HOME` 自体に対して検証・実行する共通処理はない。相対値は相対パスとして後続処理に渡る。たとえば接続保存先では `STRATA_CONNECTION_DIR` が非空ならそちらが先に使われ、相対値はエラーになるが、これは XDG 値の検証ではない（`terminal/strata_cli/connections.py:72-90`）。

## 有効になる条件

- `os.name != "nt"` / `platform !== "win32"` の設定パス分岐で使われる。Windows では設定ファイル・接続・プロファイルの場所は `APPDATA` または `~/AppData/Roaming` が優先され、この変数は参照されない（`terminal/strata_control/discovery.py:126-134`、`terminal/strata_control/profiles.py:38-45`、`terminal/strata_cli/connections.py:72-82`、`terminal/setup.py:7283-7289`、`app/host/server/model-folder.mjs:67-72`）。
- `STRATA_SETTINGS_FILE` が非空なら、セットアップ、設定探索、MCP ツールの設定ファイルでは、その明示パスが XDG の場所に優先する。デスクトップホストがターミナル設定を探す関数では別名 `STRATA_TERMINAL_SETTINGS_FILE` が優先する（`terminal/strata_control/discovery.py:126-134`、`terminal/setup.py:7276-7289`、`terminal/tools/strata_mcp.py:780-785`、`app/host/server/model-folder.mjs:67-72`）。
- `STRATA_PROFILE_DIR` が非空ならプロファイル保存先を置き換える（`terminal/strata_control/profiles.py:38-45`）。`STRATA_CONNECTION_DIR` が非空なら接続保存先を置き換え、絶対パスでない場合は `ConnectionError` になる（`terminal/strata_cli/connections.py:72-82`）。
- セットアップの設定ファイルを読む `discovery.places()` は、`STRATA_INSTALL_DIR` が明示されるとその場所だけを候補にして早期 return するため、XDG 配下の「記憶済み install」探索には進まない（`terminal/strata_control/discovery.py:174-192`）。XDG は候補の優先順位を直接変えず、その候補となる `settings.json` の場所を選ぶ。
- Linux デスクトップの既定モデル場所に限り、`STRATA_MODELS_DIR` が非空ならそのパスを返し、`XDG_CONFIG_HOME` は読まれない。次に `XDG_DOCUMENTS_DIR` が非空ならそれを Documents とし、これも XDG 設定ファイルより優先する（`app/host/server/model-directory-default.mjs:8-25`）。この `documentsFolder()` 分岐は Linux 以外では `user-dirs.dirs` を読まない。
- デスクトップホストの既定モデル場所は `app/host/server/store.mjs` のモジュール評価時に `DEFAULT_MODELS_DIRECTORY` として一度計算される。従ってそのプロセス内で後から環境を変更しても、この既定値は再計算されない。保存済みモデル場所は優先され、既定場所が使えない場合には `STRATA_HOME/models` に fallback する（`app/host/server/store.mjs:62-85`）。

## 実行時の詳細

- `terminal/strata_control/discovery.py:126-134` の `own_settings_file()` は、`STRATA_SETTINGS_FILE`、Windows の `APPDATA`、それ以外の `XDG_CONFIG_HOME` の順で設定ファイルを決める。`places()` はこのファイルから過去の install 一覧を読み、見つかった install の設定候補に加える（`terminal/strata_control/discovery.py:174-208`）。`strata_control/models.py:49-59` も同じ helper を通じて記憶済み install を読む。
- `terminal/setup.py:7283-7306` は同じ優先順位で `settings.json` を決め、`data_dir` などを読み書きする。保存できない場合は `could not save {path} ({error})` の警告を出す。設定の読み込み失敗は空の設定として扱う（`terminal/setup.py:7292-7306`）。
- `terminal/tools/strata_mcp.py:780-800` は同じ設定場所から `data_dir` を読み、無効・欠落時には `self.root.parent / "Strata-data"` を使う。これはMCPツール側の許可ルート判定に使う。
- `terminal/strata_cli/connections.py:72-90` は接続保存先を `connection_dir()` の呼び出しごとに計算する。ディレクトリ作成または既存のディレクトリ・ファイルの所有者や権限に問題があれば `ConnectionError`（コード 5）になり、一覧取得時に不正な接続記録はエラー項目として返る（`terminal/strata_cli/connections.py:149-164`）。
- `terminal/strata_control/profiles.py:38-55` はプロファイル保存先を関数呼び出しごとに計算する。保存先はプロファイル・履歴・編集用一時ファイルの場所になる。環境変数の値をプロセス開始時に静的 cache する実装は見つからない。
- デスクトップホストの `terminalSettingsFile()` は、packaged アプリが `shareDataFolder()` でターミナル設定とモデル場所を同期するときに使われる。同期は packaged 条件下で行われ、失敗は catch されアプリ起動を止めない（`app/host/server/model-folder.mjs:67-72`、`app/host/server/native-control.mjs:186-189`）。
- Linux の `user-dirs.dirs` では、`XDG_DOCUMENTS_DIR="..."` という行に一致する値を取り出し、`$HOME` / `${HOME}` を home に置換する。置換後に他の `$` が残るか、絶対パスでなければ `<home>/Documents` に戻す。ファイル読み込み失敗も握りつぶす。モデル場所はその Documents に `Strata/Models` を加えたパスである（`app/host/server/model-directory-default.mjs:14-25`）。

## ログと測定値

`XDG_CONFIG_HOME` の値だけを記録する専用ログはない。通常は選ばれた場所が設定ファイルや保存先に反映される。セットアップの設定保存に失敗したときだけ、選んだパスと OS エラーを含む `could not save ...` 警告が出る（`terminal/setup.py:7299-7306`）。packaged デスクトップホストのモデル場所同期エラーは握りつぶされる（`app/host/server/native-control.mjs:188-189`）。資料に本変数の性能測定値はない。

## 根拠

- `terminal/strata_control/discovery.py:126-134,174-208,258-290` — 設定ファイル選択と設定・記憶済み install の探索。
- `terminal/strata_control/models.py:49-59` — 同じ設定ファイルからの記憶済み install 読み取り。
- `terminal/setup.py:7276-7306` — 設定ファイル選択、読込、保存と警告。
- `terminal/tools/strata_mcp.py:780-800` — 設定ファイル選択とデータ場所の許可判定。
- `terminal/strata_control/profiles.py:38-55` — プロファイル保存先。
- `terminal/strata_cli/connections.py:72-90,149-164` — 接続保存先と不正状態の扱い。
- `app/host/server/model-folder.mjs:67-72`、`app/host/server/native-control.mjs:186-189` — デスクトップホストからターミナル設定を参照する条件。
- `app/host/server/model-directory-default.mjs:8-25`、`app/host/server/store.mjs:62-85` — Linux の XDG user directories 読み取りとモデル既定場所への反映。
- `docs/TERMINAL.md:55,167` は接続・プロファイル保存先を説明する。`docs/DETAILS.md:1540` は `~/.config` を例示するが、現行コードでは非 Windows 環境で `XDG_CONFIG_HOME` を使って置き換えられる。
