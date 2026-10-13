# `STRATA_ALLOWED_HOSTS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。対象は Strata 所有ソース。外部ライブラリの動作は対象外。

## 役割

`serve/server.py` の HTTP サーバーが DNS rebinding 対策として受け付ける Host 名を追加します。設定ファイルの `allowed_hosts` と環境変数の値は結合されます。ホスト名の追加は API キーが未設定の場合の Host 検査に使われ、`/v1/*` のブラウザー Origin 判定でも「サーバー自身が答える名前」の一部として参照されます。

## 値と判定

環境変数は `os.environ.get("STRATA_ALLOWED_HOSTS", "")` で読み取られ、その文字列をカンマで分割します。空文字や空白だけの要素は捨てられます。各要素は前後空白を除去して小文字化され、同じ名前は重複排除されます。

| 入力要素 | 処理 |
|---|---|
| `example.com` | そのホスト名を許可リストに追加 |
| `https://example.com:8443/path` | scheme と `/` 以降を取り除き、`example.com` を追加。ポートは比較対象にならない |
| `.example.com` | `example.com` と、その配下の名前を許可（例: `a.example.com`） |
| `*` | 許可リストに `*` を追加し、HTTP Host 検査の全ホスト許可を有効にする |
| 不正な名前（例: 空のカンマ要素以外で名前が空、英数字・`-._` 以外を含む） | `ValueError`。起動時に `[strata] config ...` を表示して終了する |

環境変数が未設定または空文字の場合、環境変数由来の追加はありません。`"a,, b"` のような入力では空要素を無視し、`a` と `b` を追加します。数値としての解釈や真偽値変換はありません。`STRATA_ALLOWED_HOSTS=1` はホスト名 `1` として扱われ、`0` もホスト名 `0` として扱われます。

## 有効になる条件

- サーバー起動処理で環境変数を読み、設定ファイルの `allowed_hosts` と結合します。設定値は環境変数より先に処理され、両方の名前が有効になります。環境変数は設定値を置き換えません。
- `/` を含む要素では最初の `://` までを scheme とみなし、その後の最初の `/` 以降を捨てます。ホスト名の照合時はポートを取り除きます。名前と scheme の大文字小文字は小文字化で吸収されます。
- `.example.com` のような先頭ドット付き項目は、そのドメイン自体とサブドメインに一致します。`*` は Host 検査に限って全ホストを許可します。
- 有効な API キーが設定されている場合、`parse_request()` は Host 検査自体を省略します。キーなしの場合も、IP アドレス、`localhost` / `*.localhost`、Host ヘッダーなし、および bind address 等から作られた既定の名前は別途許可されます。
- 許可名の追加は CORS 設定そのものではありません。ブラウザーの `/v1/*` Origin 判定ではサーバーの名前として参照されますが、別の Origin 条件と JSON Content-Type 条件も適用されます。

## 実行時の詳細

環境変数は `main()` のサーバー初期化中に一度読み取られ、結果は `svc.allowed_hosts` に保持されます。`serve()` がその値から `svc.host_names` を構築してから HTTP サーバーを開始します。したがって稼働中にプロセス環境を変更しても、現在のサーバーには再反映されません。子プロセスへの転送はこの変数について実装されていません。

起動時に一つ以上の許可名があれば stdout に `[strata] also answers to the host names ... (allowed_hosts)` が出ます。`*` を含む場合は `[strata] Host check off: any name reaches this server (allowed_hosts "*")` が出ます。不正な値は `[strata] config allowed_hosts: ...` の形式の起動エラーになります。

API キーがなく、Host が既定の許可名・IP・localhost・`allowed_hosts` のいずれにも当たらない要求は 403 になります。標準出力には拒否理由と、設定の `allowed_hosts` または `STRATA_ALLOWED_HOSTS` に追加する案内を出し、応答 JSON にも DNS rebinding protection による拒否と設定方法を含めます。

## 根拠

- `serve/server.py:6317-6325` — 起動時の読み取り、設定値との結合、検証エラー、起動ログ。
- `serve/server.py:5767-5786` — 環境変数のカンマ分割、空要素除外、正規化、URL/ポート処理、ワイルドカード、無効値処理、重複排除。
- `serve/server.py:5789-5806,5886-5890` — 許可名と bind address 等から Host 名集合を作成しサーバーに設定。
- `serve/server.py:4703-4720,5809-5819` — API キー有無での Host 検査、許可/拒否と 403 応答。
- `serve/server.py:4722-4741,5865-5883` — ブラウザー Origin の検査で許可名を利用する条件。
- `docs/DETAILS.md:898-909` — Host 名制限、`STRATA_ALLOWED_HOSTS`、先頭ドット、`*` の利用説明。現行実装と整合。
- `docs/LLAMA_SWAP.md:19-22,33-48` — llama-swap の環境設定例と、ポートを無視して proxy の Host 名を登録する説明。
