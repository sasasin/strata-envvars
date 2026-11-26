# `XDG_DATA_DIRS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata がこの値を読む実装は二つある。

- Linux デスクトップのウィンドウ子プロセスでは、COLRv1 カラー絵文字フォントの有無を調べる検索先に各ディレクトリの `fonts` を追加する。これは WebKitGTK のウィンドウだけに適用するフォント回避策であり、シェル、App Host、engine、agent のフォント設定は変更しない（`app/desktop/src-tauri/src/main.rs:929-942,1295-1314`、`app/desktop/src-tauri/src/fontguard.rs:36-58`）。
- AppImage の host は、Strata 外のプログラムに渡す環境を作るとき、AppImage 内のパスをこの値から除くか、AppImage 起動前に記録された元の値を戻す。対象には folder chooser、portal 用 `gdbus`、`xdg-open`、agent の shell 等がある（`app/host/server/external-env.mjs:25-26,43-57,63-71`、呼び出し例: `app/host/server/folder-dialog.mjs:117-136,153-164`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/agent/harness-runtime.mjs:25-36`）。

## 値と判定

| 経路 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux ウィンドウのフォント探索 | `env("XDG_DATA_DIRS")` が `None` なら追加ディレクトリなし | `"/usr/share:/opt/share"` は二つの要素を読み、それぞれに `/fonts` を付けて追加 | 有効/無効値の検証はない。空文字は `Some("")` だが、空要素を除外するため追加なし。`":"` も追加なし |
| AppImage 外部プログラム向け環境 | 元環境に未設定なら未設定のまま。起動前環境の記録があればその記録に従う | 元環境の値をそのまま復元する。記録なしで `APPDIR` がある場合は、AppImage 配下でない非空の `:` 区切り要素を残す | 記録なしで `APPDIR` がある場合、値が空または全要素が AppImage 配下なら、出力環境からキー自体を削除 |

Linux フォント探索では、値を `:` で分割し、空要素だけを除外する。空白の trim、絶対パス確認、ディレクトリの存在確認、パス文字列の妥当性検査はしない。各非空要素 `d` を `PathBuf::from(d).join("fonts")` に変換する。変換後は既定の `/usr/share/fonts`、`/usr/local/share/fonts` 等と合わせて `Vec::dedup` するため、重複が隣り合う場合だけ一つにまとまる（`app/desktop/src-tauri/src/fontguard.rs:36-57`）。値は全体比較や数値変換を受けない。

AppImage の経路では `PATH_LISTS` の一要素として名前を動的に参照する。記録なしで `APPDIR` が空でない場合に限り、`:` 分割し、空要素および `APPDIR` と一致するかその配下 (`APPDIR/…` または `APPDIR//…`) の要素を除く。残りを `:` で連結し、残りがなければキーを削除する。`APPIMAGE` だけが設定され `APPDIR` がないケースでは、この helper は path list を掃除しない。起動時に記録された環境を復元する経路では分割・掃除をせず、値を記録どおりに戻す（`app/host/server/external-env.mjs:25-26,43-57,60-71`）。

## 有効になる条件

- フォント探索の読み取りは `#[cfg(target_os = "linux")]` の `run_window_process` だけで行われる。Linux の通常起動では supervisor がウィンドウ子プロセスを動かし、子プロセス起動後、WebKitGTK を開始する前に一度探索する（`app/desktop/src-tauri/src/main.rs:929-942,1295-1314`）。Windows/macOS の埋め込み経路ではこのフォント探索を呼ばない。
- フォント探索の結果が設定に影響するには、`FONTCONFIG_FILE` が設定されておらず、`STRATA_FONT_CONFIG` が `off` でも既存ファイルパスでもなく、探索先に COLRv1 フォントがあり、システム設定 `/etc/fonts/fonts.conf` が存在し、設定ファイルを書ける必要がある。前二者のいずれかに該当すれば `XDG_DATA_DIRS` を読んだ後でも設定を変更しない。フォントがない場合や設定ファイルを用意できない場合も `FONTCONFIG_FILE` は設定されない（`app/desktop/src-tauri/src/fontguard.rs:117-156`、`app/desktop/src-tauri/src/main.rs:1307-1314`）。
- `colrv1_font_present` は各探索先を深さ 5 まで走査し、最初の一致で止まる。走査対象ディレクトリがない・読めない場合はその場所を無視する（`app/desktop/src-tauri/src/fontguard.rs:60-89`）。
- 外部プログラム向けの処理は `externalEnvironment` を呼ぶ経路に限る。AppImage 外で `APPIMAGE` と `APPDIR` がなく、`STRATA_ORIGINAL_ENV` の記録もなければ環境を変更しない。AppImage 起動時の記録がある場合は復元した環境を使い、記録がない場合は `APPDIR` が存在するときに限り現在の環境から AppImage 配下の path list 要素を掃除する（`app/host/server/external-env.mjs:43-57,60-71`）。

## 実行時の詳細

フォント探索では `run_window_process` 内の `env` closure が呼ばれるたびに `std::env::var(k).ok()` を評価するが、`font_dirs` の呼び出し自体はウィンドウ子プロセス起動時の一回であり、その `dirs` を `config_for` とフォント走査に渡す。実行中に環境変数を変更しても、この探索先リストは再構築されない。Strata は `XDG_DATA_DIRS` を設定・上書きせず、この経路で設定するのは条件を満たした場合の `FONTCONFIG_FILE` である（`app/desktop/src-tauri/src/main.rs:1307-1314`、`app/desktop/src-tauri/src/fontguard.rs:37-58,147-156`）。

外部プログラム向け helper は呼び出しごとに渡された環境（既定では `process.env`）から戻り値を作り、呼び出し側が `extra` を指定した場合はその値を最後に重ねる。起動前環境を AppImage launcher が `STRATA_ORIGINAL_ENV` に記録する処理は `app/desktop/scripts/repack-appimage.sh:79-85` にある。フォルダ選択では同じ環境を `zenity`、`kdialog`、`gdbus` に渡し、artifact を開く処理では `xdg-open` に渡す。agent 環境ではさらに許可名フィルターを通るが、`XDG_.*` は許可対象なのでこの変数名はフィルターで落ちない（`app/host/server/folder-dialog.mjs:117-136,153-164`、`app/host/server/artifacts.mjs:5-6,17-20,39-42`、`app/host/server/agent/harness-runtime.mjs:20-36`）。

## ログと測定値

`XDG_DATA_DIRS` の分割、除去、復元そのものに関する Strata のログはない。フォント設定を作れない場合も、この処理はエラーを記録せず環境をそのままにする（`app/desktop/src-tauri/src/fontguard.rs:117-156`）。外部プログラムの起動失敗や chooser の失敗表示は個々の呼び出し側が扱うもので、環境 helper は理由ログを出さない（例: `app/host/server/folder-dialog.mjs:124-145`）。この変数に関する測定値は該当なし。

## 根拠

- `app/desktop/src-tauri/src/fontguard.rs:36-58` — フォント探索先への `XDG_DATA_DIRS` の変換。
- `app/desktop/src-tauri/src/fontguard.rs:60-89,117-156` — COLRv1 の検出、設定生成の条件と失敗時の扱い。
- `app/desktop/src-tauri/src/main.rs:929-942,1295-1314` — Linux のウィンドウ子プロセス起動時の読み取り。
- `app/host/server/external-env.mjs:25-26,43-57,60-71` — path list としての動的参照、AppImage 環境の復元・除去規則。
- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage 起動前環境の記録。
- `app/host/server/folder-dialog.mjs:117-145,153-164`、`app/host/server/artifacts.mjs:5-6,17-20,39-42`、`app/host/server/agent/harness-runtime.mjs:20-36` — helper が環境を渡す呼び出し例。
