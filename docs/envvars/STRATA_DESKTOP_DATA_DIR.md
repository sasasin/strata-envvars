# `STRATA_DESKTOP_DATA_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数は対象外。

## 役割

デスクトップアプリの `desktoplog::data_dir()` が使うデータディレクトリを指定します。この値はデスクトップアプリ自身の run/crash log、`shell-prefs.json`、Save logs が探す `runtime` ディレクトリの基点になります。エンジン本体の保存先を一括変更する処理ではありません。コード上の直接の利用先は `desktoplog.rs` と `shell.rs` です。

`docs/INSTALL.md` はエンジン components の既定位置を Windows の `%LOCALAPPDATA%\Strata\components`、Linux/macOS の `$XDG_DATA_HOME/strata/components` と記載しています（同ファイル 128-135 行）。ただし、この変数の直接参照はデスクトップ Rust コード内の `data_dir()` に限られ、components の保存先を変更する参照は確認できませんでした。

## 値と判定

| 状態 | 選択されるパス |
|---|---|
| 設定あり（空文字を含む） | 環境値をそのまま `PathBuf` に変換したパス |
| 未設定、Windows | `%LOCALAPPDATA%` が絶対パスならその下の `Strata`。それ以外は `%USERPROFILE%/AppData/Local`、なければ一時ディレクトリの下の `Strata` |
| 未設定、Linux/macOS | `XDG_DATA_HOME` が絶対パスならその下の `strata`。それ以外は `$HOME/.local/share`、なければ一時ディレクトリの下の `strata` |

設定値には空文字かどうか以外の検査、絶対パス検査、正規化、変換、範囲制限はありません。`var_os` を使うため Unicode 文字列への変換も要求しません。明示された相対パスもそのまま使われ、空文字なら `data_dir()` は空の `PathBuf` です。その場合、利用先の `join` により `logs`、`runtime`、`shell-prefs.json` などの相対パスになります。

優先順位は `STRATA_DESKTOP_DATA_DIR` が最優先で、未設定時のみ OS ごとの既定値を計算します。CLI 引数による上書きはこの関数にはありません。既定値内では上表の環境変数に加え、Windows は `USERPROFILE`、Linux/macOS は `HOME` が fallback に使われます。

## 有効になる条件

この読み取りは Strata デスクトップアプリの Rust コードにあります。GPU backend、モデル状態、build macro による分岐はありません。`data_dir()` は Windows・Linux・macOS の各ビルドで呼ばれます。値は `data_dir()` の呼び出し時に毎回読み直され、キャッシュされません。したがって、同一プロセス内で環境値が変更された場合、後続の呼び出しは新しい値を参照します。

## 実行時の詳細

- Linux の shell ログ、Windows/macOS の起動ログ、crash log は `data_dir()/logs` 配下を使います。通常起動では `Log::open()` がディレクトリ作成を試み、run log を append mode で開きます。作成・open エラーはそこで無視され、ファイルが開けなければログ本文はファイルへ書かれません。crash log の書き込みは失敗すると `None` になります。
- `shell-prefs.json` の読み書き対象は `data_dir()` 直下です（パス定義は `shell.rs`）。
- `--save-logs` は `data_dir()/logs` から desktop log を、`data_dir()/runtime` から `.server.log` を探します。これらのディレクトリを読めない場合、ログ収集上は空として扱われます。出力先の作成・書き込みに失敗すると Linux shell は `[strata] could not save the logs: ...` を stderr に出し、終了コード 1 を返します。成功すると保存先を stdout に表示します。
- Linux で crash log が書けない場合は「The crash log could not be written.」を shell log / terminal に出します。Windows/macOS の起動失敗報告では crash file が書けなければ run log の場所（または data dir）を案内先に使います。パスの不正や書き込み権限による失敗をこの変数固有の警告として出す処理はありません。
- 直接検索では、変数名の本番コード参照は `desktoplog.rs:33` の一箇所です。`set_var` / `remove_var` の他の2参照はテスト内です。desktop host や window child を起動するコードは個別の環境変数を追加していますが、この変数を明示的に上書き・転送する処理は見つかりませんでした。

## 根拠

- `apps/desktop/src-tauri/src/desktoplog.rs:31-63` — 環境値読み取り、OS 別 fallback、logs パス。
- `apps/desktop/src-tauri/src/desktoplog.rs:122-132,281-289` — run log / crash log の作成と失敗時の扱い。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-341` — `--save-logs` の探索先と出力。
- `apps/desktop/src-tauri/src/desktoplog.rs:363-370,472-488` — Windows/macOS 起動時のログ初期化と失敗報告。
- `apps/desktop/src-tauri/src/shell.rs:33-34,51-53` — `shell-prefs.json` の場所。
- `apps/desktop/src-tauri/src/supervisor.rs:316-332` — Linux の `--save-logs` 呼び出し、表示、終了コード。
- `apps/desktop/src-tauri/src/desktoplog.rs:552-574` — 変数設定・解除を行うテストコード。
- `docs/INSTALL.md:128-135` — components の既定位置。`STRATA_DESKTOP_DATA_DIR` の説明ではなく、上記の区別の照合用。
