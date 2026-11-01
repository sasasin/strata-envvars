# `STRATA_INSTALL_TEST_TRUST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Strata Terminal のワンラインインストーラーが、テスト用 feed の公開鍵ファイル `test-trust.json` を取得し、インストールした Terminal に署名確認をさせるときに使います。Linux/macOS 用 `packaging/install.sh` と Windows 用 `packaging/install.ps1` に読み取り箇所があり、通常のアプリ実行やモデル実行の設定ではありません。

フラグが有効だと、インストーラーは選択中の feed から `test-trust.json` を一時ディレクトリへダウンロードし、そのパスを `STRATA_UPDATE_TRUSTED_KEYS` として `strata update --check` の子プロセスに渡します。公開鍵の生成元は同梱ツール `packaging/make_local_feed.py` が出力するテスト feed の公開鍵です（`packaging/make_local_feed.py:107-118`）。

## 値と判定

両インストーラーとも値全体が文字列 `1` と一致するときだけ有効です。数値変換や trim はありません。

| インストーラー | 未設定・空文字 | 値が `1` | その他の値 |
|---|---|---|---|
| Linux/macOS `install.sh` | 無効 | 有効 | 無効。比較はシェルの文字列完全一致 |
| Windows `install.ps1` | 無効 | 有効 | 無効。文字列比較 `-eq '1'` |

たとえば `true`、`01`、` 1`、`1 ` は有効になりません。読み取りは署名確認の直前に行われ、値を保存する static cache はありません。インストーラーの起動時に値を設定しておく必要があります。

## 有効になる条件

- `install.sh` を使う Linux/macOS、または `install.ps1` を使う Windows のインストールであること。どの Terminal アーカイブを選ぶか、GPU/backend、モデル状態には依存しません。
- 環境変数が正確に `1` であること。
- 通常のインストール手順が署名確認の段階まで到達すること。先行する feed manifest や Terminal アーカイブの取得・検査に失敗すれば、この変数の分岐には到達しません。

`STRATA_FEED`（PowerShell 側では `$env:STRATA_FEED`）が選ぶ feed が、`test-trust.json` の取得先にも使われます。値が `1` 以外のとき、インストーラー自身はこのファイルを取得せず、`STRATA_UPDATE_TRUSTED_KEYS` もこの分岐では設定しません。その場合、呼び出し元から同名変数が既に継承されていればその値は子プロセスにも残ります。

## 実行時の詳細

1. インストーラーは manifest から対象 Terminal を決定し、アーカイブを取得、SHA-256 を照合して一時配置します。
2. フラグが有効なら、`$FEED/test-trust.json` を一時ディレクトリへ取得します。取得できない場合は配置中の Terminal を削除し、`the test feed has no test-trust.json` として終了します。
3. 取得したファイルのパスを `STRATA_UPDATE_TRUSTED_KEYS` に設定し、配置中の `strata` に `update --check --no-engine --feed "$FEED"` を実行させます。PowerShell でも対応する `strata.cmd` に同じオプションを渡します。
4. チェックが失敗すると、チェック出力を標準エラーに表示し、配置中の Terminal を削除して署名確認失敗のメッセージで終了します。成功すれば `Signature ok.` を表示し、その後に Terminal を正式配置します。

Terminal 側の `strata_control.signing.load_trusted_keys()` は、組み込み鍵と `STRATA_UPDATE_TRUSTED_KEYS` が指す追加鍵ファイルを読み込みます。したがって、このフラグは組み込み鍵を置き換える処理ではなく、追加の鍵ファイルを指定する処理です。追加鍵の適用中は通常の CLI 経路で `note: trusting the extra keys in ... (a test setup)` が標準エラーに出ます。鍵ファイルが読めない・形式が不正・署名鍵が信頼対象にない場合は feed の確認に失敗します。

## 根拠

- `packaging/install.sh:17-21` は feed と変数の用途を説明し、`:24-27` は feed/data/bin の既定値を定めます。`:83-123` はアーカイブ検査後のフラグ判定、test-trust の取得、環境変数の export、署名確認、失敗時の削除と成功表示を実装します。
- `packaging/install.ps1:16-19` は設定を説明し、`:29-30` は feed を決めます。`:48-63` と `:65-102` はダウンロード・ハッシュ検査・展開を行い、`:104-120` はフラグ判定から署名確認の結果処理までを実装します。
- `strata_control/signing.py:31` は追加鍵用の変数名を定義し、`:194-216` は組み込み鍵に環境変数で指定されたファイルの鍵を加えて読み込みます。`:219-221` は追加鍵が有効かを環境から判定します。
- `strata_cli/update_cmd.py:230-240` は `update --check` の鍵読み込みと追加鍵使用時の注記を実装します。`strata_control/feed.py:335-350` は feed 署名を照合し、信頼されない署名をエラーにします。
- `packaging/UPDATES.md:119-123` は tester/local-test key を `STRATA_UPDATE_TRUSTED_KEYS` で渡す運用を説明します。`packaging/make_local_feed.py:107-118` は local feed と公開 `test-trust.json` の生成を示します。
