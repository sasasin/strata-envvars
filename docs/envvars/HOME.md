# `HOME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`HOME` は Strata 全体で統一的に解釈する設定ではなく、各処理がユーザー用ディレクトリを組み立てるために個別に参照するプロセス環境変数です。読み取り箇所はデスクトップシェル、Linux/macOS のホスト、SYCL engine、Linux/macOS 用インストーラー、および開発用シェルスクリプトにあります。用途ごとに優先順位や unset・空文字の扱いが異なります。

主な実行時の用途は、デスクトップのデータ／ログ保存先とセッションファイル、Linux ウィンドウプロセスのフォント検索先、ホストの既定ワークスペース・ダウンロード先・ファイル選択ショートカット、agent 子プロセスへの環境引き継ぎ、SYCL の int8 expert crossover キャッシュ先です。環境変数の値を真偽値や数値に変換する処理はありません。

## 値と判定

| 読み取り箇所 | unset | 設定値・空文字 | 優先順位・効果 |
|---|---|---|---|
| `tools/packaging/install.sh` | `set -u` の下で `$HOME` 展開に到達すると未設定変数として失敗。`STRATA_DATA_DIR` と `STRATA_BIN_DIR` の両方が非空なら該当展開は回避される | 文字列をそのままパスへ展開。空の `HOME` は `/.local/share/strata` と `/.local/bin` を作る既定値になる | `STRATA_DATA_DIR` が非空なら data 先、そうでなければ非空 `XDG_DATA_HOME`、さらに `$HOME/.local/share` の順。bin 先は非空 `STRATA_BIN_DIR`、なければ `$HOME/.local/bin`。詳細は下記「実行時の詳細」 |
| デスクトップログ `desktoplog.rs`（非 Windows build） | `XDG_DATA_HOME` が絶対パスでなければ `HOME` 由来の base も試し、`HOME` も未設定なら `std::env::temp_dir()` | `var_os` なので空文字・非 UTF-8 も値として保持。空 `HOME` は `.local/share/strata`（相対パス）になる | 絶対 `XDG_DATA_HOME` が最優先。次に `HOME/.local/share`、最後に temp。`STRATA_DESKTOP_DATA_DIR` が設定されていれば全てに優先 |
| デスクトップ session file `supervisor.rs` | `std::env::temp_dir()/.strata/app-session.json` | `var_os` の値をそのまま `PathBuf` 化。空文字なら相対 `.strata/app-session.json` | 設定済み `STRATA_APP_SESSION_FILE` が最優先。HOME 経路はそれが未設定のときだけ |
| デスクトップ `downloads_dir()` | 非 Windows では temp directory。Windows build は `HOME` を読まず `USERPROFILE` を使う | 非 Windows は `var_os` の値をそのまま `Downloads` に連結。空文字なら相対 `Downloads` | この関数では HOME の前に別の環境変数はない |
| Linux window の fontguard | HOME 由来のディレクトリを追加しない | `std::env::var(...).ok()` 経由なので非 UTF-8 は未設定相当。空文字も `filter` で除外 | `XDG_DATA_HOME` が非空ならその `fonts` を使い、HOME 由来の `.local/share/fonts` は追加しない。`HOME/.fonts` は XDG_DATA_HOME の有無にかかわらず追加 |
| Host (`index.mjs`) | `USERPROFILE` も未設定なら `node:os` の `homedir()` を使用。`/api/local-models/browse` の Home shortcut は省略 | `??` 判定なので空文字は設定済みとして残り、`homedir()` へ fallback しない | workspace と Downloads は `USERPROFILE ?? HOME ?? homedir()`。workspace は非空 `STRATA_WORKSPACE` が最優先。Home shortcut は `USERPROFILE ?? HOME` |
| Linux host の text editor 検索 | 空文字に置換 | 値をそのまま `/.../.local/share/applications` の候補へ連結 | HOME は Linux で gio の desktop entry を探すときの候補の一つ |
| SYCL prefill cache | `STRATA_CACHE_DIR` が空／未設定なら `LOCALAPPDATA` を試す。両方なければ cache path なし | 非空 `STRATA_CACHE_DIR` が最優先。HOME は設定有無だけを見て文字列連結し、空文字も `/.cache/strata` になる | `STRATA_CACHE_DIR` → `HOME/.cache/strata` → `LOCALAPPDATA/strata` → cache 無効 |
| agent harness child environment | 元の環境に HOME がなければ子にも追加しない | allowlist にある HOME を値を変えず子環境にコピー | AppImage 起動時は元環境の復元結果を使い、それ以外は host の環境を基にする。明示 `extra` は後から上書き |

HOME はパスとして使われるため、数値境界・大小文字比較・`true`/`false` の parse はありません。パスの絶対性検査や空文字フィルターがあるかは上表のとおり読み取り箇所別です。特に Rust の `var_os` は UTF-8 変換を要求しませんが、fontguard の `env` closure は `var(...).ok()` なので非 UTF-8 値を取得できません。根拠: `app/desktop/src-tauri/src/desktoplog.rs:52-58,516-518`, `app/desktop/src-tauri/src/supervisor.rs:96-102`, `app/desktop/src-tauri/src/main.rs:1309-1314`, `app/desktop/src-tauri/src/fontguard.rs:37-55`, `app/host/server/index.mjs:114-124,1147-1149,1546-1549`, `app/host/server/open-text-file.mjs:10-21`, `engine/sycl/src/prefill/prefill.cpp:958-965`, `app/host/server/agent/harness-runtime.mjs:20-36`。

## 有効になる条件

- デスクトップログの HOME fallback は `cfg(not(windows))` の Linux/macOS build のみです。Windows は `LOCALAPPDATA`（絶対パスのみ）、`USERPROFILE`、temp の順を使い、HOME は読まれません（`app/desktop/src-tauri/src/desktoplog.rs:39-58`）。
- デスクトップの session path は `STRATA_APP_SESSION_FILE` が未設定の場合に HOME が関与します。書き込み時と読み取り・削除時に `session_path()` を呼び直すため、関数内キャッシュはありません（`app/desktop/src-tauri/src/supervisor.rs:96-102,104-108,125-139`）。
- `--save-logs` は `downloads_dir()` を出力先として使用します。保存失敗時は `[strata] could not save the logs: {e}` を stderr に出し、終了コード 1 を返します（`app/desktop/src-tauri/src/supervisor.rs:484-493`, `app/desktop/src-tauri/src/desktoplog.rs:516-518`）。
- fontguard が HOME を使うのは Linux の window-child 起動経路で、WebKit 起動前です。`FONTCONFIG_FILE` がすでに設定済みなら Strata は fontguard の設定を上書きしません。COLRv1 font が見つからない場合も HOME 由来の検索結果を使った設定ファイルは作りません（`app/desktop/src-tauri/src/main.rs:1295-1314`, `app/desktop/src-tauri/src/fontguard.rs:141-157`）。
- Host workspace は起動時に一度計算されます。`STRATA_WORKSPACE` が非空なら HOME は使いません。HOME 由来の基底ごとに `Strata/Workspace` を作成し、作成できる最初の場所を採用し、全て失敗した場合は `user` を返します（`app/host/server/index.mjs:114-124`）。
- host の diagnostics 保存先は API リクエスト時に決まり、`USERPROFILE` がある場合は HOME より優先されます（`app/host/server/index.mjs:1138-1149`）。ローカルモデル browse の `Home` shortcut も `USERPROFILE` を先に使いますが、両方 unset なら shortcut 自体が除外されます（`app/host/server/index.mjs:1546-1549`）。
- Linux text editor の desktop entry 検索は Linux 経路で gio が見つかった場合だけ HOME 由来ディレクトリを調べます。Gtk launch が見つかった場合はこの検索を行いません（`app/host/server/open-text-file.mjs:10-23`）。
- SYCL の HOME cache path は `STRATA_CACHE_DIR` が非空でない場合にのみ選ばれます。測定は該当する SYCL prefill の crossover 判定経路で呼ばれ、process 内の static map に `(queue, format)` ごとの結果も保持します。HOME 自体の値が変わっても、既存 map や既存 cache file の探索結果を自動で無効化する仕組みはありません（`engine/sycl/src/prefill/prefill.cpp:958-965,1006-1019,1126-1129,4867-4872`）。
- インストーラーは Linux / macOS 向けです。Windows 向けの `install.ps1` にはこの shell 展開を適用しません（`tools/packaging/install.sh:1-3,59-67`）。

## 実行時の詳細

### インストール先

インストーラーは起動時に `DATA_DIR` と `BIN_DIR` を展開します。`STRATA_DATA_DIR` と `STRATA_BIN_DIR` は `${VAR:-...}` なので未設定と空文字のどちらも既定値へ進みます。data 先では非空 `XDG_DATA_HOME` があれば `$XDG_DATA_HOME/strata`、なければ `$HOME/.local/share/strata` です。bin 先は `$HOME/.local/bin` です。後続処理は data 先に Terminal を展開して `current` link を更新し、bin 先に `strata` link を作ります（`tools/packaging/install.sh:22-27,149-152,176-185`）。HOME が unset で、代替変数によって `$HOME` 展開が回避されないと `set -u` により本処理開始前に shell が終了します。空 HOME は unset 扱いではないため root 起点のパスになります。

### デスクトップ shell

非 Windows のログ data directory は `STRATA_DESKTOP_DATA_DIR`、絶対 `XDG_DATA_HOME`、`HOME/.local/share`、temp の順で決まります。Windows の経路は `LOCALAPPDATA`（絶対パスのみ）、`USERPROFILE`、temp です。`data_dir()` は呼び出しごとに環境を評価し、ログ開始時に `logs_dir()` からログファイルを開きます。書き込み不能時にはログ file が作れず、`Log::line` はその状態を無視します（`app/desktop/src-tauri/src/desktoplog.rs:32-63,122-142`）。

session file は `STRATA_APP_SESSION_FILE` があればそこ、なければ `$HOME/.strata/app-session.json`、HOME unset なら temp 配下です。session file の mkdir failure は無視され、file open failure は `[strata] could not write {path}: {e}` を stderr に出します。起動時の session 記録や browser mode への切り替えで write され、session lookup / remove 時にも現在の環境からパスを組み立てます（`app/desktop/src-tauri/src/supervisor.rs:96-102,104-122,125-139,544-563,591-595`）。

`--save-logs` は非 Windows で `$HOME/Downloads`（unset なら temp）へまとめログを書きます。保存先 directory 作成またはファイル書き込みの失敗は上記エラーと終了コード 1 になります（`app/desktop/src-tauri/src/desktoplog.rs:310-340,516-518`, `app/desktop/src-tauri/src/supervisor.rs:484-493`）。

### Linux window の fontguard

window-child は起動時に `std::env::var(k).ok()` を使う closure を `font_dirs()` と `config_for()` に渡します。HOME が非空なら `/home/.local/share/fonts`（`XDG_DATA_HOME` 未設定／空の場合）と `/home/.fonts` を font 探索対象へ追加します。空 HOME は除外されます。検索対象に COLRv1 font があれば、`STRATA_FONT_CONFIG` で指定された既存ファイルを使うか、既存の system font configuration を含む Strata 用設定を data directory に作成し、そのパスを window process の `FONTCONFIG_FILE` に設定します。HOME は検索先の構成にだけ影響し、HOME のみを理由にログやエラーを出す分岐はありません（`app/desktop/src-tauri/src/fontguard.rs:36-57,117-157`, `app/desktop/src-tauri/src/main.rs:1307-1314`）。

### Host、agent、SYCL

Host は `USERPROFILE ?? HOME ?? homedir()` を既定 workspace および diagnostics の Downloads base に使います。JS の nullish fallback は空文字を除外しないため、HOME が空文字なら `homedir()` へ移りません。workspace は module 初期化時に決まり、diagnostics は保存 API を処理するたびに評価されます（`app/host/server/index.mjs:114-124,1147-1149`）。Agent harness の allowlist は HOME のキーと値をそのまま child process の環境へ含めます。`extra` が HOME を含めばその値で上書きされます（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

SYCL は `STRATA_CACHE_DIR` が非空ならそれを使い、次に HOME、`LOCALAPPDATA` の順で `i8-crossover.txt` の位置を作ります。cache hit 時は `strata: int8 experts: crossover ... from the cache ...` を stderr に出して測定を省略します。miss 時は GPU 上の int8／FP16 crossover 測定を行い、結果を stderr に記録して cache へ書きます。測定失敗時は `strata: int8 experts: the crossover measurement failed (...): the int8 path is used below 64 rows per expert` と出し、64 rows の低信頼 fallback を返します。cache path がない場合や file 操作に失敗した場合は cache を使えないまま測定側へ進みます（`engine/sycl/src/prefill/prefill.cpp:958-1003,1006-1019,1099-1129,4871`）。

## ログと測定値

HOME の値そのものを出力するログや HOME 固有のエラー文言は見つかりませんでした。観測可能な結果は、ログ・session・診断ファイル・フォント設定・性能 cache のパスが変わることと、SYCL の cache hit／測定結果／測定失敗ログです。SYCL の測定値は HOME の効能を比較した値ではないため記載しません。`docs/DETAILS.md` に HOME の環境変数動作を説明する記述はありません。

## 根拠

- Host の HOME 直接参照と優先順位: `app/host/server/index.mjs:114-124,1147-1149,1546-1549`; agent path exclusion: `app/host/server/agent/agent-bridge.mjs:181-190`; text editor: `app/host/server/open-text-file.mjs:10-23`; child environment transfer: `app/host/server/agent/harness-runtime.mjs:20-36,75-83`。
- Desktop data/log/download path: `app/desktop/src-tauri/src/desktoplog.rs:32-63,122-142,310-340,516-518`; session path and call sites: `app/desktop/src-tauri/src/supervisor.rs:96-139,544-563,591-595`。
- Linux window font search: `app/desktop/src-tauri/src/main.rs:1295-1314`; `app/desktop/src-tauri/src/fontguard.rs:36-57,117-157`。
- SYCL cache path and runtime: `engine/sycl/src/prefill/prefill.cpp:958-1003,1006-1129,4871`。
- Installer: `tools/packaging/install.sh:22-27,149-185`。
- 開発用 build shell references: `tools/packaging/mac/build_engine.sh:40-49`; `tools/packaging/build_hip_gfx1103.sh:2-23`; `engine/src/inkling2/cuda/build_cuda.sh:10-20`; `engine/src/hy4flash/metal/build_mac.sh:1-5`; `engine/src/hy4flash/metal/build_vis.sh:1-4`; `engine/src/inkling2/metal/build_mac.sh:1-7`; `engine/metal/tools/gen_grids.sh:1-4`。これらはビルド／生成時の作業パスや CUDA 探索に使い、実行時の Strata 設定ではありません。
- `tools/release_grid/cell_runner.py:756-764` と `tools/packaging/smoke_terminal.py:74-75` は test harness の child process に隔離用 HOME を設定します。`app/host/scripts/test.mjs:15-17` も test process 用の HOME を生成して設定します。`app/host/scripts/agent-lost-e2e.mjs:29-65` は E2E の既定 fixture path を `process.env.HOME ?? ''` から作ります。候補一覧に現れる test fixture／文書・コメント上の `$HOME` は、通常利用時の環境変数 read と区別しました。

Node の `homedir()` を使う箇所（`app/host/server/store.mjs:14-16`、`app/host/server/model-directory-default.mjs:7-25`）は Strata のソース内で `HOME` を直接取得していません。ここでは Strata 側の環境変数 read としては扱わず、Node runtime が `homedir()` をどう決めるかも説明対象に含めません。`model-directory-default.mjs:22` の `$HOME` は `XDG_DOCUMENTS_DIR` の値に含まれる文字列を `home` 引数で置換する処理です。
