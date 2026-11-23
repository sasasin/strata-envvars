# `FONTCONFIG_FILE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux デスクトップのウィンドウ子プロセスで、利用者が `FONTCONFIG_FILE` をすでに設定しているかを調べます。設定があれば値を読んだり検証したりせず、その選択を優先して Strata のフォント設定ファイルを適用しません。未設定なら、COLRv1 フォントが見つかった場合に限って Strata が作成する設定ファイルをこの変数に設定します。従って、この変数は Strata のフォント描画機能一般を切り替える設定ではなく、Linux デスクトップの当該子プロセスでの自動設定を抑止する判定にも使われます（`app/desktop/src-tauri/src/fontguard.rs:141-157`、`app/desktop/src-tauri/src/main.rs:1298-1314`）。

## 値と判定

`config_for` は環境変数取得 helper の `Option<String>` に対して `is_some()` を使います。文字列の比較、数値変換、空白除去、パス検証はしません。Rust の `std::env::var(k).ok()` を helper にしているため、Unicode 文字列として取得できる値は空文字でも「設定あり」です。Unicode として取得できない値は helper が `None` にするため、この判定では未設定と同じ扱いになります（`app/desktop/src-tauri/src/main.rs:1309-1313`、`app/desktop/src-tauri/src/fontguard.rs:147-150`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux デスクトップのウィンドウ子プロセス | Strata が後述の条件を満たす場合に自動設定を試みる | Unicode の空文字を含む任意の値。Strata はその値を変更せず自動設定を見送る | Unicode 文字列として取得できる設定値に「無効」はない。Unicode で取得できない値は helper 上 `None` となる |
| Windows/macOS の埋め込みウィンドウ、Linux のシェルやホスト | この `fontguard` 経路は呼ばれない | 同左 | 同左 |

たとえば空文字、`0`、`1`、`true`、`false`、`0anything` はいずれも、取得できる限り同じく設定済みとして扱われます。大文字小文字や値の前後の空白による判定差もありません。既存値のファイル存在確認もありません（`app/desktop/src-tauri/src/fontguard.rs:147-150`）。

## 有効になる条件

- この判定を行うのは `#[cfg(target_os = "linux")]` の `run_window_process` です。Windows/macOS の `run_embedded` からは呼び出されず、Linux の通常シェルプロセスもウィンドウ子プロセスとして起動された場合だけこの箇所に進みます（`app/desktop/src-tauri/src/main.rs:929-945`、`1295-1314`）。
- 既存の `FONTCONFIG_FILE` があれば、`STRATA_FONT_CONFIG` の値やシステム設定、フォントの有無を調べる前に終了し、Strata はこのプロセスの値を上書きしません（`app/desktop/src-tauri/src/fontguard.rs:147-150`）。
- 未設定の場合、`STRATA_FONT_CONFIG=off`（完全一致）なら自動設定をしません。`STRATA_FONT_CONFIG` に別の値があれば、その値をパスとして扱い、通常ファイルが存在する場合だけそのパスを選択します。存在しなければ何も設定しません（`app/desktop/src-tauri/src/fontguard.rs:30-31,147-156`）。
- `STRATA_FONT_CONFIG` も未設定なら、`font_dirs` が列挙するフォントディレクトリを深さ 5 まで走査し、ファイル名に `colrv1` を含むフォントが見つかった場合だけ自動設定ファイルの生成へ進みます（`app/desktop/src-tauri/src/fontguard.rs:36-58,60-90,155-156`）。
- 自動設定には `/etc/fonts/fonts.conf` が存在し、データフォルダー内の `fonts` ディレクトリと設定ファイルを書き込めることが必要です。条件を満たさない場合は `None` となり、`FONTCONFIG_FILE` は設定されません（`app/desktop/src-tauri/src/fontguard.rs:117-138`）。

## 実行時の詳細

Linux の `main` は `--window-child` と親シェルの確認を通過した後に `run_window_process` を呼びます。同関数は WebKit/Tauri の Builder を起動する前に環境を読み、選ばれた設定ファイルがあれば `std::env::set_var("FONTCONFIG_FILE", conf)` を実行します。これはウィンドウ子プロセス内での設定であり、Strata のコメントもホスト・engine・agent には影響させないとしています（`app/desktop/src-tauri/src/main.rs:929-945,1295-1314`）。

生成する設定ファイルは `<data>/fonts/fonts-no-colrv1.conf` です。システム設定 `/etc/fonts/fonts.conf` を先に include し、COLRv1 名の顔を除外する指定と `Noto Color Emoji` に対して `Noto Emoji` を優先する alias を記述します。Strata は内容が同一なら書き直さず、異なる場合は一時ファイルから置換します（`app/desktop/src-tauri/src/fontguard.rs:27-34,92-114,117-138`）。

判定はこの起動経路で一度行われ、値をキャッシュして後続リクエストで再利用する処理はありません。プロセス起動後の環境変更を再読込するコードも、この `fontguard` 経路にはありません（`app/desktop/src-tauri/src/main.rs:1309-1314`）。

## ログと測定値

自動設定を適用した・見送った理由や設定ファイル生成失敗を出力するログは、この経路にはありません。`ensure_config` の失敗は `None` として伝播し、呼び出し側は値を設定せずそのままウィンドウ起動へ進みます（`app/desktop/src-tauri/src/fontguard.rs:117-157`、`app/desktop/src-tauri/src/main.rs:1310-1314`）。

別の診断経路では `desktoplog::graphics_environment` が `FONTCONFIG_FILE` を含む環境名の一覧を走査し、Unicode として取得できた値を `名前=値` の行にします。この情報はウィンドウクラッシュレポートと `--save-logs` に含まれます。診断コードは呼び出し元プロセスの環境を読むため、ウィンドウ子プロセスだけで後から設定した値をシェル側の診断が読むものではありません（`app/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`）。測定値の記載はありません。

## 根拠

- `app/desktop/src-tauri/src/fontguard.rs:141-157` — 既存値の優先、関連設定との順序、適用条件。
- `app/desktop/src-tauri/src/fontguard.rs:92-138` — 生成設定の内容、出力先、書き込みと失敗時の戻り値。
- `app/desktop/src-tauri/src/main.rs:929-945,1295-1314` — Linux ウィンドウ子プロセスの経路と環境変数設定の時点。
- `app/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320` — 診断情報での環境値の読み取りと出力先。
