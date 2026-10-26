# `XDG_CONFIG_HOME`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata のコマンドライン版と関連ツールが使う設定ファイル、保存済み接続、操作プロファイルの基準ディレクトリを指定します。また Linux のデスクトップアプリは、ユーザーの Documents フォルダー設定ファイル `user-dirs.dirs` をこのディレクトリから探します。

## 値と判定

環境変数の値を数値やフラグとして parse する箇所はありません。各箇所は文字列をパスとして使います。多くの読み取り箇所では未設定または空文字ならホームディレクトリ配下の `.config` に戻ります。空白の除去、絶対パス検査、正規化は共通には行われません。

| 読み取り経路 | 未設定時 | 空文字 | 非空文字 |
|---|---|---|---|
| setup の設定ファイル、`strata_control.discovery`、接続ファイル、MCP ツール、Terminal の共有設定ファイル | `~/.config` を使う | `~/.config` を使う | その値を設定ルートとして使う |
| `strata_control.profiles.profile_dir()` | `~/.config` を使う | 値が設定済みとして扱われ、相対パス `strata/profiles` になる | その値を設定ルートとして使う |
| Linux アプリの Documents 検出 | `~/.config/user-dirs.dirs` を読む | 同じく `~/.config/user-dirs.dirs` を読む | `<値>/user-dirs.dirs` を読む |

Python の多くの経路は `os.environ.get("XDG_CONFIG_HOME") or ...`、Node.js の経路は `env.XDG_CONFIG_HOME || ...` です。一方、プロファイル保存先だけは `os.environ.get("XDG_CONFIG_HOME", 既定値)` なので、空文字の場合の結果が異なります。非空の相対パスは拒否されず、プロセスの作業ディレクトリからの相対パスになります。

## 有効になる条件

- Windows では、設定ファイルや接続・プロファイルの基準ディレクトリに `APPDATA` が使われ、この変数はその経路で参照されません。
- `setup.py` の `STRATA_SETTINGS_FILE` が非空なら、設定ファイルはそのパスになり、`XDG_CONFIG_HOME` より優先します。`strata_control.discovery` も同様に `STRATA_SETTINGS_FILE` を優先します。
- 接続情報では非空の `STRATA_CONNECTION_DIR` が優先し、プロファイルでは非空の `STRATA_PROFILE_DIR` が優先します。操作プリセットは非空の `STRATA_PRESET_DIR`、Terminal の launch preset は非空の `STRATA_LAUNCH_PRESET_DIR` がそれぞれ優先します。
- アプリの Terminal 共有用設定ファイルは非空の `STRATA_TERMINAL_SETTINGS_FILE` を優先します。
- Linux アプリの新規モデル保存先決定では、`STRATA_MODELS_DIR` があれば先に採用し、次に `STRATA_DOCUMENTS_DIR`、その次に `XDG_DOCUMENTS_DIR` を見ます。これらがない場合に限り、`XDG_CONFIG_HOME` を使って `user-dirs.dirs` を探します。このファイルから読んだ Documents 値は `$HOME` を展開し、絶対パスで、他の `$` 参照を含まない場合に採用します。ファイルを読めない、該当値がない、値が不正な場合はホーム直下の `Documents/Strata/Models` に戻ります（`apps/host/server/model-directory-default.mjs:8-19`）。

## 実行時の詳細

コマンドライン版 `setup.py` は、他の設定ファイル指定がない非 Windows 環境で `<XDG_CONFIG_HOME>/strata/settings.json` を使います。読み込みに失敗すると空の設定として扱い、保存時は親ディレクトリを作成して JSON を書きます。ここに保存された `data_dir` は setup と Terminal が共有するモデルデータ場所の選択に使われます（`setup.py:5995-6025`, `strata_control/discovery.py:123-131,241-280`）。アプリ内プロセスは `STRATA_SETTINGS_FILE` でアプリ専用ファイルを指定し、古いコマンドライン版のファイルをそのまま設定ファイルとして使わない設計です。

非 Windows の接続情報は `<XDG_CONFIG_HOME>/strata/connections/<名前>.json` に保存・列挙されます。設定ディレクトリを作る際はプライベートなディレクトリとして作成し、既存ディレクトリやファイルの所有者・権限なども検査します（`strata_cli/connections.py:72-95,130-164,190-218`）。

プロファイルは `<XDG_CONFIG_HOME>/strata/profiles/<名前>.json` に置かれ、編集履歴は同じ場所の `.history/<名前>/` 以下に置かれます。保存・編集・ロールバック時に `profile_dir()` を呼び直すため、Python プロセスではこの環境変数を各呼び出し時に参照します（`strata_control/profiles.py:38-55,169-189,270-295,312-357`）。プリセットや Terminal の launch preset もそれぞれプロファイルディレクトリの隣を基準にするため、個別の override がなければこの変数の影響を受けます（`strata_control/presets.py:45-50`, `strata_cli/launch/store.py:32`）。

`tools/strata_mcp.py` も非 Windows では同じ `strata/settings.json` を参照します（`tools/strata_mcp.py:594-608`）。デスクトップアプリの Terminal 共有処理は `terminalSettingsFile()` の呼び出し時に環境を参照します（`apps/host/server/model-folder.mjs:67-72`, `apps/host/server/native-control.mjs:94`）。これに対し、Linux の `user-dirs.dirs` を使ったモデル既定フォルダーの計算結果は `apps/host/server/store.mjs` のモジュール読み込み時に定数へ保存されるため、読み込み後に `process.env` を変更しても再計算されません（`apps/host/server/store.mjs:60-61`）。

## 文書との照合

`docs/TERMINAL.md` は接続ファイルとプロファイルの Unix 側保存先として `${XDG_CONFIG_HOME:-~/.config}/strata/...` を説明しており、コードと一致します（同ファイル `:44,156`）。`docs/DETAILS.md:1102` は Linux の標準設定ファイル位置を `~/.config/strata/settings.json` と記していますが、これは変数未設定時の既定値です。コードでは `XDG_CONFIG_HOME` が設定されていればその値が使われます。

## 根拠

- `setup.py:5995-6025` — `STRATA_SETTINGS_FILE` の優先と設定ファイルの読み書き。
- `strata_control/discovery.py:123-131,241-280` — Terminal 側の設定ファイル選択と、アプリとのデータディレクトリ同期。
- `strata_cli/connections.py:72-95,130-164,190-218` — 接続ディレクトリ、列挙、権限検査、ロック。
- `strata_control/profiles.py:38-55,169-189,270-295,312-357` — プロファイル本体、保存履歴、編集用一時ファイル。
- `strata_control/presets.py:45-50`, `strata_cli/launch/store.py:32` — プロファイルに隣接するプリセット保存場所。
- `tools/strata_mcp.py:594-608` — MCP ツールの設定ファイル選択。
- `apps/host/server/model-folder.mjs:67-72`, `apps/host/server/native-control.mjs:94` — アプリと Terminal 間の設定共有。
- `apps/host/server/model-directory-default.mjs:8-19`, `apps/host/server/store.mjs:60-61` — Linux の Documents 設定ファイル探索と、その結果を既定値に使う時期。
- `docs/TERMINAL.md:44,156`, `docs/DETAILS.md:1102` — 保存先についての既存説明。
