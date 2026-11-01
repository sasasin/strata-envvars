# `USERPROFILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。外部ライブラリ側の動作は対象外です。

## 役割

Strata Control、ホストサーバー、デスクトップアプリが、Windows 上でユーザーの Documents、作業フォルダー、状態・診断ファイルの場所を組み立てるために参照します。また、ホストはエージェント用 Harness の子プロセスへこの環境変数を引き継ぎます。エンジンの推論動作を制御する変数ではありません。

## 値と判定

Strata は `USERPROFILE` の文字列を数値や真偽値に parse しません。用途ごとの未設定・空文字の扱いは異なります。

| 箇所・条件 | 未設定 | 空文字 | 設定値 |
|---|---|---|---|
| Control の Windows Documents 候補 | `_home(home)`（`home` 引数がなければ `Path.home()`）に fallback | `or` 判定で同じ fallback | そのまま `Path` にし、`Documents` を追加 |
| Host の既定 workspace / Downloads / Home ショートカット | `HOME`、さらに Node の `homedir()`（Home ショートカットは `HOME` まで） | nullish 判定なので空文字を採用。workspace は相対パスから作成を試み、Downloads 等も相対パスになる | そのまま採用。trim、絶対パス検査なし |
| Host のエージェント tracker 除外パス | `HOME`、さらに `homedir()` | nullish 判定なので空文字を採用 | `AppData` 等の除外先の基準に採用 |
| Host が Harness に渡す環境 | この変数は追加されない | 名前が allowlist に一致し、値が空でも除外されず転送 | allowlist を通して値を転送 |
| Desktop Rust の Windows データフォルダー | `temp_dir()` を基準にする | `var_os` は空文字も値として扱い、相対 `AppData/Local/Strata` になる | `USERPROFILE/AppData/Local/Strata`。絶対パス検査なし |
| Desktop Rust の Downloads | `temp_dir()` | 空値を値として扱い、相対 `Downloads` | `USERPROFILE/Downloads` |

Host の既定 workspace では `STRATA_WORKSPACE` が truthy ならそちらを優先します。未指定時は `USERPROFILE ?? HOME ?? homedir()` を基準に `<user>/Documents/Strata/Workspace`、次に `<user>/Strata/Workspace` の順で作成を試し、両方失敗すると基準値自体を使います。`WORKSPACE` はモジュール読み込み時に一度計算されます。診断保存先とローカルモデル一覧の Home ショートカットは各 HTTP リクエストで環境を参照します（`apps/host/server/index.mjs:102-115,1023-1025,1404-1408`）。

## 有効になる条件

- Control の Documents 候補では Windows 判定時だけ使用します。`STRATA_DOCUMENTS_DIR` が空でない場合、その候補が先に置かれます。`USERPROFILE/Documents` の後ろに `OneDrive`、`OneDriveConsumer`、`OneDriveCommercial` の各 `Documents` 候補が追加されます。非 Windows では `USERPROFILE` を使わず、`XDG_DOCUMENTS_DIR` と `home/Documents` を使います (`strata_control/discovery.py:64-87`)。
- Control の `data_dir_choices()` はアプリ内モード (`STRATA_SETTINGS_FILE` が truthy) では Documents 候補自体を追加しません。通常の Control 経路では候補の `Documents/Strata` がデータフォルダーとして採用されるのは、そこに `Models`、`models`、または `packs` の非空ディレクトリがある場合です。設定ファイルやアプリ側候補が先に選ばれることもあります (`strata_control/discovery.py:262-289`)。
- Host の `apps/host/server/platform-paths.mjs` では Windows の状態ディレクトリー計算で `LOCALAPPDATA` が truthy なら `USERPROFILE` より優先されます。`LOCALAPPDATA` が空または未設定なら、`USERPROFILE || homedir()` を使います。非 Windows は `USERPROFILE` を使いません (`apps/host/server/platform-paths.mjs:16-22`)。
- Desktop Rust の Windows データディレクトリーは `LOCALAPPDATA` が絶対パスならそれを優先します。未設定・相対値なら `USERPROFILE` を使い、こちらも未設定なら一時ディレクトリーに fallback します。非 Windows のコンパイルではこの関数は `USERPROFILE` を参照せず `XDG_DATA_HOME` / `HOME` を使います (`apps/desktop/src-tauri/src/desktoplog.rs:39-59`)。
- Desktop Rust の Downloads 選択は `cfg!(windows)` で実行時に `USERPROFILE` または `HOME` のどちらを読むか選びます。値があれば `Downloads` を付加し、なければ一時ディレクトリーです。保存ログ処理から呼び出されます (`apps/desktop/src-tauri/src/desktoplog.rs:516-518`; 呼び出し `apps/desktop/src-tauri/src/supervisor.rs:323`)。

## 実行時の詳細

Control の `documents_dirs()` は `environ` 引数が省略された場合に `os.environ` を参照します。明示的に渡された環境辞書と `windows` / `home` 引数で動作を差し替えられます。そこで作られた Documents 候補は、通常モードのデータフォルダー探索に渡されます。候補が存在しない、またはモデル用ディレクトリーを含まない場合は採用されず、後続候補または既定値になります (`strata_control/discovery.py:64-87,262-289`)。

Host サーバーは `WORKSPACE` をモジュール初期化時に決め、優先先のフォルダーを作れなければ次候補へ進みます。API `/api/native/logs/save` は環境変数から Downloads を選び、`mkdirSync` と `writeFileSync` で診断テキストを書き、成功時に JSON の `path` を返します。このブロックでは書き込みを囲む `try/catch` がなく、失敗すれば通常のリクエスト処理へ例外が伝わります。ローカルモデル閲覧 API は `USERPROFILE ?? HOME` を Home ショートカットとして返し、どちらも falsy の場合はそのショートカットを除きます (`apps/host/server/index.mjs:102-115,1014-1025,1404-1408`)。

Agent bridge は `USERPROFILE` をユーザープロファイル配下の `AppData`、`.cache`、`.config`、`.local`、`Library` を tracker の除外対象にするため参照します。`env` の既定値は `process.env` ですが、生成時に環境オブジェクトを注入できます (`apps/host/server/agent/agent-bridge.mjs:120-135`)。Harness 起動時には `agentEnvironment()` が親環境のうち allowlist に合う変数だけを子プロセス環境へコピーします。`USERPROFILE` は大文字小文字を区別しない allowlist に含まれ、別途 `extra` で上書きもできます (`apps/host/server/agent/harness-runtime.mjs:20-36,75-83`)。これは Strata による転送の記述であり、Harness 内部での変数利用は説明対象外です。

## 根拠

- `strata_control/discovery.py:64-87,262-289` — Windows の Documents 候補、データフォルダー探索と採用条件。
- `apps/host/server/index.mjs:102-115,1014-1025,1404-1408` — workspace の初期化、診断ファイル保存、Home ショートカット。
- `apps/host/server/platform-paths.mjs:16-22` — Windows 状態ディレクトリーと `LOCALAPPDATA` 優先。
- `apps/host/server/agent/agent-bridge.mjs:120-135` — tracker 除外先の基準。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-83` — allowlist による子プロセスへの環境転送。
- `apps/desktop/src-tauri/src/desktoplog.rs:39-59,516-518`、`apps/desktop/src-tauri/src/supervisor.rs:323` — Windows データディレクトリーと Downloads の選択、ログ保存からの呼び出し。

候補一覧には `USERPROFILE` が載っています (`000_envvers.md:1694`)。Strata 所有の本番コードに上記の読み取り・転送が確認できました。`docs/DETAILS.md` にある `%USERPROFILE%` の記述 (`docs/DETAILS.md:852`) は Codex CLI の設定場所の説明で、Strata による読み取りの根拠にはしていません。
