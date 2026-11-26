# `USERPROFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`USERPROFILE` は Windows でユーザーのホーム／プロファイル基準パスとして使われます。Strata は一律に解釈せず、呼び出し箇所ごとに空値の fallback が異なります。主な用途は、Terminal が既存モデルのある `Documents/Strata` を候補に加えること、host が既定 workspace と Home shortcut と診断ファイルの場所を決めること、Windows desktop shell がデータフォルダーと `--save-logs` の保存先を決めることです。CUDA/HIP/SYCL engine の挙動を制御する変数ではありません。

参照候補のうち、実行時に値を読む実装は `terminal/strata_control/discovery.py`、`app/host/server/index.mjs`、`app/host/server/agent/agent-bridge.mjs`、`app/host/server/platform-paths.mjs`、`app/desktop/src-tauri/src/desktoplog.rs` にあります。`harness-runtime.mjs` の名前 allowlist は agent 子プロセスへ環境を転送するもので、名前の動的な読み取りではありません（`app/host/server/agent/harness-runtime.mjs:22-36,80-83`）。

## 値と判定

文字列全体を数値や boolean に parse せず、パスとして使います。空白除去、絶対パス検査、正規化をこの変数値そのものに対して行う共通処理はありません。未設定・空文字の扱いは箇所ごとに異なります。

| 読み取り箇所・条件 | unset | 有効になる値（例） | 空文字・無効値の例 |
|---|---|---|---|
| Terminal の `documents_dirs`、Windows (`windows=None` の既定は `os.name == "nt"`) | `Path.home()/Documents` を候補にする | 非空の任意の文字列を `Path` にし、その `Documents` を候補にする | `""` は `or` により `Path.home()` へ fallback。文字列の妥当性・絶対性は検査しない |
| host の既定 workspace（`STRATA_WORKSPACE` が truthy でない場合） | `HOME`、さらに Node の `homedir()` | 任意の文字列を user 基準に使う | `""` は nullish fallback を発生させず、その空文字を基準に `workspaceBases` へ渡す |
| host の Home shortcut と診断保存 | shortcut は `HOME`、未設定なら値なし。診断保存は `HOME`、さらに `homedir()` | 任意の文字列 | 空文字は nullish fallback されず、shortcut では `.filter(Boolean)` により項目が消える。診断保存では `Downloads` 相対パスになる |
| host Windows state path、`LOCALAPPDATA` が truthy でない場合 | `homedir()` を使う | 非空なら `<USERPROFILE>\\AppData\\Local\\Strata` | `""` は `||` により `homedir()` に fallback。絶対性は検査しない |
| Rust desktop、Windows の `LOCALAPPDATA` が未設定または絶対パスでない場合 | `USERPROFILE` があればその下の `AppData/Local`、なければ temp dir | `OsString` を `PathBuf` にして `AppData/Local` を追加 | 空でも `var_os` は値ありとして扱われ、その相対 `AppData/Local/Strata` が組み立てられる。USERPROFILE の絶対性検査はない |
| Rust desktop の `--save-logs`、Windows | `temp_dir()/Downloads` | `USERPROFILE/Downloads` | 空でも値ありとして `Downloads` が使われる。パス検証なし |

根拠: `terminal/strata_control/discovery.py:39-44,67-90`、`app/host/server/index.mjs:111-124,1545-1549`、`app/host/server/platform-paths.mjs:16-23`、`app/desktop/src-tauri/src/desktoplog.rs:39-47,516-518`。

## 有効になる条件

- Terminal の Documents 候補では Windows 判定が必要です。`STRATA_DOCUMENTS_DIR` が truthy ならそれが先の候補になり、`USERPROFILE/Documents` より前に調べられます。`OneDrive`、`OneDriveConsumer`、`OneDriveCommercial` が設定されていればそれぞれの `Documents` も候補に追加されます（`terminal/strata_control/discovery.py:67-90`）。
- その Documents 候補がデータフォルダーとして採用されるには、アプリ内モードでなく、先行する settings/app のデータ指定で決まらず、`Documents/Strata` 以下の `Models`、`models`、`packs` のいずれかに中身のあるディレクトリーが必要です。満たさなければ `data_dir` は指定された default を返します（`terminal/strata_control/discovery.py:258-291,294-314`）。
- host の既定 workspace では truthy な `STRATA_WORKSPACE` が最優先で、その場合 `USERPROFILE` は workspace 選択に使われません。通常は `<user>/Documents/Strata/Workspace` を作成し、作成に失敗すれば `workspaceBases` の次の候補を試し、全候補で失敗すれば user 値自体を返します。`WORKSPACE` はモジュール初期化時に一度決まり、その後 workspace、chat の fallback、Skills などに使われます（`app/host/server/index.mjs:111-124,419,539-552,644`、`app/host/server/model-directory-default.mjs:28-42`）。
- host の state path は Windows でのみ `USERPROFILE` fallback を使います。truthy な `LOCALAPPDATA` があれば `USERPROFILE` は参照されず、`STRATA_TUNE_DIR`／`STRATA_TIMESKIP_DIR` の明示値は state root より優先します（`app/host/server/platform-paths.mjs:16-32`）。
- Rust desktop の `USERPROFILE` によるデータ path fallback は Windows build だけです。`LOCALAPPDATA` は絶対パスなら優先され、未設定または相対パスなら `USERPROFILE`、それも未設定なら temp directory へ進みます（`app/desktop/src-tauri/src/desktoplog.rs:39-47`）。
- Rust `--save-logs` 分岐は CLI 引数が必要です。`downloads_dir` は Windows では `USERPROFILE`、それ以外では `HOME` を使います。保存先 directory の作成・ファイル書き込みが成功すると stdout に `Saved to ... Please send this file to us.`、失敗すると stderr に `[strata] could not save the logs: {e}` を出して終了コード `1` を返します（`app/desktop/src-tauri/src/supervisor.rs:43-53,478-494`、`app/desktop/src-tauri/src/desktoplog.rs:310-341,516-518`）。
- host の diagnostics API は `/api/native/logs/save` の POST 時に限り、`USERPROFILE ?? HOME ?? homedir()` の `Downloads` にファイルを作成して path を返します。shortcut API は `/api/local-models/browse` で Home を表示します（`app/host/server/index.mjs:1138-1149,1545-1549`）。
- agent の deliverable tracking では `trackerFolders()` が `USERPROFILE ?? HOME ?? homedir()` を基準に `AppData`、`.cache`、`.config`、`.local`、`Library` を除外対象に加えます。tracker の生成時に計算され、`USERPROFILE` 単独でファイル操作や agent の cwd は決まりません（`app/host/server/agent/agent-bridge.mjs:181-190,534`）。agent subprocess には host の環境から `USERPROFILE` 名が許可されていれば値が転送されます（`app/host/server/agent/harness-runtime.mjs:22-36,80-83`）。

## 実行時の詳細

- Python の `documents_dirs` は呼び出しごとに渡された `environ` を参照し、未指定ならその時点の `os.environ` を使います。`USERPROFILE` の値を cache しません。`windows=None` の OS 判定は `_windows` が行います（`terminal/strata_control/discovery.py:39-44,67-90,279-306`）。
- host server は import 初期化中に `defaultWorkspace()` を実行して `WORKSPACE` 定数を作ります。`USERPROFILE` の実行中変更はこの既定 workspace に再反映されません。diagnostics と Home shortcut は各 API handler が `process.env` を参照するため、handler 到達時の値を使います（`app/host/server/index.mjs:111-124,1138-1149,1545-1549`）。
- `stateRoot` は既定引数で `process.env` と `process.platform` を受け、`tuningDir`／`timeSkipDir` が呼ぶたびに計算します。固定 cache はありません（`app/host/server/platform-paths.mjs:16-32`）。
- Rust desktop の `platform_data_dir()` と `downloads_dir()` は呼び出すたびに `std::env::var_os` を読みます。値を別の static cache に保存しません（`app/desktop/src-tauri/src/desktoplog.rs:31-59,516-518`）。

## ログと測定値

`USERPROFILE` 自体について有効／無効を通知するログは見つかりませんでした。host は起動時に `workspace    ·  <path>` を stdout に表示します。診断保存 API は成功時に生成 path をレスポンスに含み、Rust の `--save-logs` は上記の成功・失敗文言を出力します。測定値は該当しません（`app/host/server/index.mjs:310-316,1138-1149`、`app/desktop/src-tauri/src/supervisor.rs:484-493`）。

## 根拠

- `terminal/strata_control/discovery.py:39-44,67-90,258-314`
- `app/host/server/index.mjs:111-124,310-316,1138-1149,1545-1549`
- `app/host/server/model-directory-default.mjs:7-25,28-42`
- `app/host/server/platform-paths.mjs:16-32`
- `app/host/server/agent/agent-bridge.mjs:181-190,534`
- `app/host/server/agent/harness-runtime.mjs:22-36,80-83`
- `app/desktop/src-tauri/src/desktoplog.rs:31-59,310-341,516-518`
- `app/desktop/src-tauri/src/supervisor.rs:43-53,478-494`
