# `STRATA_FONT_CONFIG`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

Linux デスクトップ版の window-child が使うフォント設定を選びます。`off` なら Strata のフォント設定介入を止め、既存ファイルパスならそのファイルを `FONTCONFIG_FILE` に設定します。変数が未設定の場合は、COLRv1 フォントがインストールされている環境で Strata が専用の設定ファイルを生成し、COLRv1 フォントを除外する設定を window-child に適用します。Linux の shell/host や engine、agent にはこの処理を適用しません（`apps/desktop/src-tauri/src/main.rs:869-880,1221-1239`、`apps/desktop/src-tauri/src/fontguard.rs:1-15`）。

## 値と判定

値は boolean や数値に変換せず、Rust の `String` として取得して文字列・パスで判定します。`off` との比較は大文字小文字を区別する完全一致です（`apps/desktop/src-tauri/src/fontguard.rs:30-31,147-156`）。

| 値・状態 | Strata の処理 |
|---|---|
| 未設定 | `FONTCONFIG_FILE` も未設定ならフォントを走査します。COLRv1 フォントが見つかれば自動設定ファイルを作成します。 |
| `off` | 自動設定を行いません。`OFF` は小文字の完全一致なので `OFF` や `off ` は別の値です。 |
| それ以外の文字列 | その文字列をパスとして扱い、`Path::is_file()` が真ならそのパスを採用します。存在しないパス、ディレクトリ、空文字列など `is_file()` が偽の値は採用しません。 |
| 非 UTF-8 の OS 環境値 | window-child の読み取りクロージャは `std::env::var(k).ok()` を使うため、文字列取得エラーは未設定と同じ `None` になります。 |

値が `off` 以外の無効なパスでも、未設定時の自動検出へ fallback しません。`Some(custom)` の分岐でファイル判定を終え、その結果（`None` を含む）を返します（`apps/desktop/src-tauri/src/fontguard.rs:151-154`）。

## 有効になる条件

- **Linux デスクトップの window-child のみ**: Linux の起動処理で `--window-child` の場合だけ `run_window_process()` に入り、その中で設定を評価します。通常の Linux shell は supervisor を実行して終了し、Windows/macOS は別の embedded 経路です（`apps/desktop/src-tauri/src/main.rs:869-880,1221-1225`）。
- **既存の `FONTCONFIG_FILE` が最優先**: `FONTCONFIG_FILE` が設定済みなら値が空でも `is_some()` が真になり、`STRATA_FONT_CONFIG` の値にかかわらず Strata は変更しません（`apps/desktop/src-tauri/src/fontguard.rs:147-149`）。
- **明示パス**: `FONTCONFIG_FILE` が未設定で `STRATA_FONT_CONFIG` が `off` 以外の場合、指定パスがファイルであればそれを採用します。この経路では COLRv1 フォント検出や `/etc/fonts/fonts.conf` の存在確認をしません（同 `:151-154`）。
- **自動設定**: 両変数が未設定の場合、フォント探索先に COLRv1 を含むファイルが見つかり、かつ `/etc/fonts/fonts.conf` が存在して設定ファイルを書けた場合にだけ採用されます。探索先は `/usr/share/fonts`、`/usr/local/share/fonts` に加え、`HOME`、`XDG_DATA_HOME`、`XDG_DATA_DIRS` から組み立てられます。COLRv1 検索はファイル名を小文字化して `colrv1` を含むかで判定し、探索深さは 5 です（同 `:36-57,60-90,121-138,155-156`）。

## 実行時の詳細

`run_window_process()` の起動時に環境変数を読み、`config_for()` の戻り値があれば同プロセスの `FONTCONFIG_FILE` を `std::env::set_var()` で設定します。呼び出しはこの起動経路にあり、値を static cache したりリクエストごとに再評価したりする実装ではありません（`apps/desktop/src-tauri/src/main.rs:1225-1239`、`apps/desktop/src-tauri/src/fontguard.rs:147-157`）。

自動生成されるファイルは desktop data directory の `fonts/fonts-no-colrv1.conf` です。内容が既存と異なる場合はプロセス ID 付き一時ファイルから rename し、内容が同一なら再書き込みしません。生成設定は `/etc/fonts/fonts.conf` を先に include し、ファイル名に COLRv1 を含む font face を reject し、`Noto Color Emoji` に `Noto Emoji` を優先する alias を設定します（`apps/desktop/src-tauri/src/main.rs:1237-1239`、`apps/desktop/src-tauri/src/fontguard.rs:20-34,92-115,117-138`）。

指定パスがファイルでない、COLRv1 フォントが見つからない、システム設定ファイルがない、または生成先の作成・書き込みに失敗した場合、Strata は `FONTCONFIG_FILE` を設定せず処理を続けます。これらの分岐に専用の警告・エラー出力はありません（`apps/desktop/src-tauri/src/fontguard.rs:121-138,147-156`）。後続の window 起動失敗時には、クラッシュ記録と `--save-logs` の Graphics session に `STRATA_FONT_CONFIG` と `FONTCONFIG_FILE` の値が列挙されます（`apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`）。これは診断用の記録で、変数の制御結果を示す専用ログではありません。

## 根拠

- 値の判定・優先順位・自動 fallback: `apps/desktop/src-tauri/src/fontguard.rs:141-157`
- window-child に限定した評価と `FONTCONFIG_FILE` 設定: `apps/desktop/src-tauri/src/main.rs:869-880,1221-1241`
- COLRv1 探索先・深さ・判定: `apps/desktop/src-tauri/src/fontguard.rs:36-90`
- 自動設定ファイルの内容と書き込み失敗時の戻り値: `apps/desktop/src-tauri/src/fontguard.rs:92-138`
- 診断ログへの環境値記録: `apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`
