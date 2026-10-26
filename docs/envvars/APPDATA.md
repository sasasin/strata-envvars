# `APPDATA`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows で、コマンドライン版 Strata のユーザー設定、保存済み接続、サーバープロファイルを置く基準ディレクトリとして使われます。未設定または空文字なら、`Path.home()\AppData\Roaming`（Node 側は `homedir()\AppData\Roaming`）へフォールバックします。主なパスは次のとおりです。

| 用途 | `APPDATA` が設定されている場合 |
|---|---|
| setup と CLI が共有する設定 | `<APPDATA>\Strata\settings.json` |
| 保存済み接続 | `<APPDATA>\Strata\connections` |
| サーバープロファイル | `<APPDATA>\Strata\profiles` |

デスクトップアプリは `STRATA_SETTINGS_FILE` で指定する独自設定ファイルを使い、古いコマンドライン版の `%APPDATA%\Strata\settings.json` をそのまま共用しません。デスクトップアプリの Control は、パッケージ版で Terminal の設定とモデルフォルダーを同期するときに `APPDATA` を使った Terminal 側の設定パスを参照します。

## 値と判定

値の数値変換、文字列比較、大小文字変換はありません。Windows の設定ファイル、接続、プロファイルのパスを組み立てる際、`APPDATA` の文字列をそのまま基底パスとして使います。相対パスを拒否する検査は `APPDATA` にはなく、接続先に `STRATA_CONNECTION_DIR` を指定した場合に限り、その値が絶対パスか検査します。

| 状態 | Windows の設定・接続・プロファイルの基底ディレクトリ |
|---|---|
| 未設定 | `Path.home()\AppData\Roaming`（Node 側は `homedir()\AppData\Roaming`） |
| 空文字 | 未設定時と同じフォールバック |
| 空でない値 | その値を使用 |

設定ファイルについては、空でない `STRATA_SETTINGS_FILE` が `APPDATA` より優先されます。保存済み接続では空でない `STRATA_CONNECTION_DIR`、プロファイルでは空でない `STRATA_PROFILE_DIR` がそれぞれ優先されます。これらの上書き変数も空文字なら優先されず、`APPDATA` に戻ります。

## 有効になる条件

- 設定ファイル、接続、プロファイル、およびデスクトップアプリから Terminal 設定への同期では、OS が Windows と判定されたときに `APPDATA` 分岐を使います。Linux/macOS のそれらのパスは `XDG_CONFIG_HOME` またはホームディレクトリを使い、`APPDATA` は使いません。
- `strata_control.private_files.user_roots()` は OS を限定せず、空でない `APPDATA` をユーザー所有データのルート候補に加えます。Windows のアクセス修復では `known_roots()` が存在する `<APPDATA>\Strata` を走査候補に加えます。修復処理自体は Windows 以外では即時に空の結果を返します。
- DeepSeek Harness を起動するホストは、子エージェント環境に残すユーザー環境変数の許可リストに `APPDATA` を含めます。`APPDATA` が設定されていれば、その値を子プロセスへ渡します。
- Web エージェントの file tracker は、追跡対象から除外するディレクトリ候補に `APPDATA` の値を追加します。
- Windows インストーラーのアンインストール時に「Strata のデータも削除」を選び、更新ではない場合、空でない `$APPDATA` の下の `Strata` ディレクトリを削除します。チェックボックスは既定でオフです。

## 実行時の詳細

setup、`strata_control.discovery`、`tools/strata_mcp.py` は、コマンドライン版設定のパスを呼び出し時に計算します。setup はそのファイルから `data_dir` などを読み、保存時には親ディレクトリを作成して JSON を書きます。読み込み時の `OSError` / JSON 値エラーは空の設定として扱い、保存失敗の `OSError` は警告にします。MCP サーバーも同じ設定ファイルから `data_dir` を読み、読めない場合は設定なしとして扱います。

接続とプロファイルの保存先は各操作時に関数で求めます。接続ディレクトリ作成時には Strata の private-directory helper を通し、既存ディレクトリが不正な種類、または POSIX 上で所有者限定でない場合はエラーにします。プロファイルの読み書き、履歴、編集用一時ファイルも `profile_dir()` の結果を使います。

Windows CLI のアクセス修復は、権限エラー後の再試行時や repair コマンドから呼び出されます。`APPDATA` が空でなければ、その直下と `<APPDATA>\Strata` をそれぞれユーザー所有ルート／Strata 固有ルートの候補にします。Strata 固有ルートは存在するものだけを走査します。修復処理は候補内のエントリーを最大 20,000 件確認し、アクセス権を直せた項目を記録します。

パッケージ版 Control が Terminal の設定を読む同期処理は、モデル保存先の変更時に実行されます。Node の `terminalSettingsFile()` は、まず `STRATA_TERMINAL_SETTINGS_FILE`、次に Windows なら `APPDATA`、最後にホームディレクトリを使って Terminal の `settings.json` を決めます。これは Control の `STRATA_SETTINGS_FILE` が指すアプリ専用設定ファイルとは別です。

## 文書との照合

`docs/TERMINAL.md:44,156` は接続情報とプロファイルの Windows 保存先を `%APPDATA%/Strata/...` と説明し、実装と一致します。`docs/DETAILS.md:1102` も setup の設定ファイルを `%APPDATA%\Strata\settings.json` と記載し、実装と一致します。これらの文書は空文字 fallback や、アクセス修復・Web エージェントでの利用までは説明していません。

## 根拠

- `setup.py:89,5995-6025` — Windows 判定、`STRATA_SETTINGS_FILE` の優先、`APPDATA` から設定パスを作る処理、設定の読み書き。
- `strata_control/discovery.py:123-131` — 同じ設定パスの解決。`tools/strata_mcp.py:595-608` — MCP サーバーの設定読み取り。
- `strata_cli/connections.py:72-94,149-164,190-200` — `STRATA_CONNECTION_DIR` の優先、接続ディレクトリの生成・検査と利用。
- `strata_control/profiles.py:38-55,169-190` — `STRATA_PROFILE_DIR` の優先、プロファイル保存先と利用。
- `strata_control/private_files.py:415-439,506-550`、`strata_cli/cli.py:2085-2116` — ユーザー所有ルートの判定、`APPDATA\Strata` の修復対象化、修復の呼び出し。
- `apps/host/server/model-folder.mjs:67-72`、`apps/host/server/native-control.mjs:91-94,145` — Terminal 設定パスの解決とモデル保存先変更時の同期。
- `apps/host/server/agent/agent-bridge.mjs:126-135` — Web エージェントの file tracker の除外候補。`apps/host/server/agent/harness-runtime.mjs:20-36,75-83` — 子エージェント向け環境に `APPDATA` を維持。
- `apps/desktop/src-tauri/nsis/installer.nsi:487-508,968-991` — データ削除確認画面と、条件付きの `$APPDATA\Strata` 削除。
- 文書との照合: `docs/DETAILS.md:1102` は Windows の設定ファイルを `%APPDATA%\Strata\settings.json` と記載しています。`docs/TERMINAL.md:44,156` は接続先・プロファイル保存場所と各上書き変数を記載しており、上記の実装と一致します。
