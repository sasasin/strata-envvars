# `APPDIR`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

`APPDIR` は、この環境変数を参照する Strata のコードでは設定用スイッチではありません。Linux AppImage 内で起動したとき、外部プログラムに渡す環境から AppImage 固有の値やパスを除くためのディレクトリ値、および desktop のクラッシュ/ログ採取時に AppImage 内の WebKitGTK ファイルを調べる起点として使われます。生成処理や通常の起動動作を切り替える環境変数としては使われていません。

## 値と判定

| 箇所 | 未設定・空文字 | 設定値と判定 |
|---|---|---|
| `apps/host/server/external-env.mjs` | `env.APPDIR || ''` は空文字として扱われます。`insideAppImage()` は `APPIMAGE` も空で `APPDIR` も空なら false です。 | `insideAppImage()` は `APPIMAGE` または `APPDIR` の JavaScript truthy 判定だけをします。`withoutAppImage()` は `APPDIR` を文字列として、等値・`APPDIR/`・`APPDIR//` で始まるパスの判定に使います。文字列の形式やディレクトリの存在は検証しません。 |
| `apps/desktop/src-tauri/src/desktoplog.rs` の環境一覧 | `graphics_environment()` は Unicode として取得できない値や未設定値を一覧から省きます。空文字は取得でき、`APPDIR=` として出力します。 | `bundled_webkit()` は `var_os()` で取得するため非 Unicode 値もパスとして扱います。空文字も「設定あり」となり、相対パス `usr/lib` を調べます。 |

## 有効になる条件

- Node 側の環境整理は `externalEnvironment()` が呼ばれたとき、`APPIMAGE` または `APPDIR` が truthy、あるいは `STRATA_ORIGINAL_ENV` が truthy の場合に行われます。`APPDIR` が空でも `APPIMAGE` が truthy なら整理経路に入ります。どちらの marker もなく original record もなければ環境のコピーをそのまま返します。
- desktop 側のファイル確認は、クラッシュレポート作成または `--save-logs` によるログ採取で `bundled_webkit()` が呼ばれた場合に限られます。プラットフォーム条件の分岐はありませんが、対象ファイル名は WebKitGTK の Linux ライブラリ名です。
- CLI 引数や別の設定ファイルが `APPDIR` を上書きする処理はありません。Node の `externalEnvironment(env, extra)` では `extra` が最後にマージされるため、呼び出し元が明示的に `extra.APPDIR` を渡せば返却環境上の値を上書きします。ただし確認できた通常の呼び出し箇所は `extra` を渡していません。

## 実行時の詳細

Node 側では、`withoutAppImage()` が新しい環境オブジェクトを作り、`APPDIR` を含む AppImage 専用変数を無条件に削除します。`APPDIR` が空でなければ、GTK/GDK/GIO/GST/GI/GSETTINGS/WEBKIT 系の値にその文字列を含むものも削除し、`PATH`、`LD_LIBRARY_PATH`、`XDG_DATA_DIRS` などのパスリストから `APPDIR` 自体またはその下のパスを取り除きます。残った項目がなければ該当するパス変数も削除します。パスリストの区切りは `:` です。

`externalEnvironment()` は、`STRATA_ORIGINAL_ENV` を復号して項目が得られた場合、その記録済み環境を使います。record がないか復号結果が使えない場合は上記の `withoutAppImage()` を使います。したがって通常の AppImage 起動では、配布 launcher が記録した起動元環境が優先され、古い AppImage のように記録がない経路では現在の環境から `APPDIR` や AppImage 内パスを除去します。環境は helper 呼び出しごとに渡されたオブジェクト（既定では `process.env`）から処理され、値の static cache はありません。

この helper は folder chooser、`xdg-open`/ファイルを開く処理、通知、さらに assistant の shell 用環境の組み立てなどで使われます。外部プログラムに渡す環境を整えるのが Strata 側の効果であり、削除された変数が外部プログラム内部でどう解釈されるかはここでは扱いません。根拠: `apps/host/server/external-env.mjs:17-26,43-70`、呼び出し箇所は `apps/host/server/folder-dialog.mjs:117-127,153-154`、`apps/host/server/chat-files.mjs:89-93`、`apps/host/server/artifacts.mjs:5-6`、`apps/host/server/app-ui.mjs:38,56-58`、`apps/host/server/open-text-file.mjs:26-29`、`apps/host/server/agent/harness-runtime.mjs:25-36,79-83`。

desktop 側では、`graphics_environment()` が `APPDIR` を含む環境名一覧を `std::env::var()` で読み、取得できた値を `NAME=value` の行として診断情報に追加します。`bundled_webkit()` は値を `PathBuf` に変換し、その下の `usr/lib` を走査して `libwebkit2gtk-4.1.so` または `libjavascriptcoregtk-4.1.so` で始まる項目を列挙します。シンボリックリンク先が読めれば表示に加え、見つかった名前をソートして `; ` で連結します。`APPDIR` が未設定なら `not an AppImage (the system's WebKitGTK is used)`、ディレクトリを読めないか対象項目がない場合は `no WebKitGTK file found in the AppImage` と記録します。これは診断文字列の生成であり、WebKit の選択やロードを変更する処理ではありません。

`bundled_webkit()` と環境一覧はクラッシュレポート本文に含まれます。window process の異常終了時にレポートを作成して保存し、通常ログに保存先または失敗を記録します。また `--save-logs` は同じ情報を採取ファイルに含め、成功時は保存先を stdout、失敗時はエラーを stderr に出して終了コード 1 を返します。根拠: `apps/desktop/src-tauri/src/desktoplog.rs:186-212,241-259,281-289,310-320`、`apps/desktop/src-tauri/src/supervisor.rs:303-313,322-331`。

## 根拠

- Node 側の直接参照、判定、クリーンアップ、record との優先順位: `apps/host/server/external-env.mjs:17-26,43-70`。
- 外部プログラム起動への適用例: `apps/host/server/folder-dialog.mjs:117-146,153-154`、`apps/host/server/chat-files.mjs:89-93`、`apps/host/server/artifacts.mjs:5-6`、`apps/host/server/app-ui.mjs:38,56-58`、`apps/host/server/open-text-file.mjs:26-29`、`apps/host/server/agent/harness-runtime.mjs:25-36,79-83`。
- desktop 診断値の読み取りと WebKit ファイル検索: `apps/desktop/src-tauri/src/desktoplog.rs:186-212,241-259,310-320`。
- クラッシュ時および `--save-logs` からの呼び出しと観測可能な結果: `apps/desktop/src-tauri/src/supervisor.rs:303-331`。

`docs/DETAILS.md` を含む Strata の docs には `APPDIR` の意味を直接説明する記述は見つかりませんでした。環境変数の候補一覧にある名前だけではなく、上記の Strata 所有コードで確認できた処理を記載しています。
