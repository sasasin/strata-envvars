# `STRATA_INSTALL_TEST_TRUST`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Linux/macOS 用 `packaging/install.sh` と Windows 用 `packaging/install.ps1` にある、ローカルのテスト feed をインストール時に検証するためのフックです。有効にすると、feed の `test-trust.json` を一時ディレクトリへ取得し、そのファイルのパスを `STRATA_UPDATE_TRUSTED_KEYS` として Terminal の `strata update --check --no-engine --feed ...` に渡します。通常の実行エンジンやサーバーはこの変数を読みません。

この名前は `000_envvers.md` に載っていますが、実際の参照はインストーラーだけです。通常利用者向けの Terminal 設定ではありません。

## 値と判定

| インストーラー | unset / 空文字 | 有効になる値 | それ以外 |
|---|---|---|---|
| `install.sh` | 無効 | 文字列が厳密に `1` | 無効 |
| `install.ps1` | 無効 | PowerShell の `-eq '1'` が真になる値。環境変数の文字列 `1` が想定値 | 無効 |

シェル版は `${STRATA_INSTALL_TEST_TRUST:-}` と文字列 `1` の完全一致を比較するため、`01`、`1 `、`true`、空文字は有効になりません。PowerShell 版も数値変換や trim をせず `-eq '1'` で比較します。どちらも有効／無効の結果をキャッシュせず、インストーラーがこの分岐に到達した時点で判定します。

## 有効になる条件

- `install.sh` または `install.ps1` を実行し、Terminal アーカイブを展開した後の署名確認段階まで進む必要があります。
- `STRATA_INSTALL_TEST_TRUST=1` の場合、選択中の `STRATA_FEED` の直下に `test-trust.json` が必要です。取得に失敗すると、展開中の Terminal を削除して終了します。Linux/macOS 版は `the test feed has no test-trust.json`、Windows 版は `the test feed has no test-trust.json` をエラーに含めます。
- 変数が未設定、空、または `1` 以外なら、test key ファイルは取得されず、既定の組み込み update key で署名を確認します。インストーラーは test key による確認を強制しません。
- `packaging/make_local_feed.py` は、ローカルテスト用 feed の公開鍵を `test-trust.json` として出力します。テスト秘密鍵は feed 署名に用いられ、公開鍵ファイルがインストーラーから渡されます。

## 実行時の詳細

両インストーラーは Terminal を一時的な `.incoming` ディレクトリへ展開し、検証用の一時ディレクトリに `test-trust.json` を保存します。有効時には、そのファイルのパスを `STRATA_UPDATE_TRUSTED_KEYS` に設定してから、展開した Terminal に `update --check --no-engine --feed <FEED>` を実行させます。チェックが失敗すると `.incoming` を削除し、インストールを止めます。成功後に初めて `.incoming` を正式な配置先に移します。

Terminal の `strata_control.signing.load_trusted_keys()` は組み込み `update_keys.json` の鍵に加えて `STRATA_UPDATE_TRUSTED_KEYS` のファイルの鍵も読み込みます。つまり追加鍵の指定であり、コード上は組み込み鍵を置き換えたり無効化したりしません。追加ファイルが読めない、JSON の `keys` 配列がない、公開鍵形式が不正などの場合は署名検証エラーになり、feed check は成功しません。`strata update --check` は成功時に終了コード 0 を返し、通常出力では追加鍵の利用を `note: trusting the extra keys in ... (a test setup)` と stderr に表示します。

シェル版は子プロセス `sh` 内で環境変数を export して Terminal を起動するため、呼び出し元シェルの環境を変更しません。PowerShell 版は環境変数を設定した後に Terminal を起動しますが、その値を削除・復元する処理はありません。また `finally` で一時ディレクトリを削除します。そのため PowerShell で `irm ... | iex` と実行した場合、インストーラー終了後も現在の PowerShell プロセスには `STRATA_UPDATE_TRUSTED_KEYS` が残り、削除済み一時ファイルのパスを指す可能性があります。これは `install.ps1` のコード上の副作用です。

## 文書との照合

インストーラーのコメントは有効時に「trust only that key」と説明しますが、現在の Terminal 実装の `load_trusted_keys()` は組み込み鍵と追加鍵を結合します。コード上の実際の動作は追加信頼鍵です。`packaging/UPDATES.md` と `packaging/make_local_feed.py` の記述も追加鍵として説明しており、実装と一致します。

## 根拠

- `packaging/install.sh:17-21,24-27,104-115` — 設定説明、feed、一時鍵ファイル取得、環境変数設定、署名確認、失敗時の `.incoming` 削除。
- `packaging/install.ps1:16-20,29-30,87-103,137-139` — Windows 版の設定、鍵ファイル取得と環境変数設定、署名確認、終了時の一時ディレクトリ削除。
- `packaging/make_local_feed.py:10-18,96-104` — テスト feed と公開鍵 `test-trust.json` の生成。
- `strata_control/signing.py:194-216` — 組み込み鍵と環境変数で指定した追加鍵の読み込み・形式検証。
- `strata_cli/update_cmd.py:23-25,189-201` — 署名鍵読込、追加鍵利用の stderr 注記、`--check` の実行。
- `strata_control/feed.py:294-319,322-335` — trusted key による署名確認と検証エラー。
- `packaging/UPDATES.md:53-56,101-110` — 鍵の扱いと追加テスト鍵の説明。
