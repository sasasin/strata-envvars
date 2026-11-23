# `STRATA_ALLOWED_HOSTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

サーバーが追加で応答する `Host` 名を指定し、API キー未設定時の DNS rebinding 対策に使います。`allowed_hosts_of()` は設定の `allowed_hosts` とこの環境変数の値を併合し、`serve()` がそれを含む既知ホスト名を作ります。Host 判定は HTTP リクエストの解析時に行われます。値を設定しても listen アドレスや API キーの設定は変わりません。[`terminal/serve/server_parts/http_api.py:176-195`](../../../../Niko1221/Strata/terminal/serve/server_parts/http_api.py) [`terminal/serve/server.py:6780-6790`](../../../../Niko1221/Strata/terminal/serve/server.py) [`terminal/serve/server.py:8243-8268`](../../../../Niko1221/Strata/terminal/serve/server.py)

## 値と判定

`main()` が `os.environ.get("STRATA_ALLOWED_HOSTS", "")` で読み、`allowed_hosts_of()` に渡します。未設定と空文字はどちらも追加項目なしです。空白だけのカンマ区切り要素も除外されます。項目ごとに前後空白を除き、小文字化し、`scheme://` より後ろと最初の `/` より後ろを除去します。ポートは `host_name()` が妥当な数字付きポートとして受け付け、最終的な名前から外します。末尾ドットも除かれます。[`terminal/serve/server.py:9062-9067`](../../../../Niko1221/Strata/terminal/serve/server.py) [`terminal/serve/server_parts/http_api.py:145-159`](../../../../Niko1221/Strata/terminal/serve/server_parts/http_api.py) [`terminal/serve/server_parts/http_api.py:176-195`](../../../../Niko1221/Strata/terminal/serve/server_parts/http_api.py)

| 条件 | 例 | 結果 |
|---|---|---|
| 未設定または空文字 | unset、`STRATA_ALLOWED_HOSTS=""` | 変数からは何も追加しない。設定ファイルの値はそのまま使う。 |
| 有効な名前 | `my-server`、`Example.COM`、`a.example.com:8080`、`https://a.example.com:8443/path` | `my-server`、`example.com`、`a.example.com` のように正規化して追加する。 |
| カンマ区切り | `one.example,two.example` | 各項目を個別に処理する。空項目は無視する。 |
| ドット始まり | `.example.com` | `example.com` 自身と、その下の名前を許可する。 |
| ワイルドカード | `*` | Host 名チェックをすべて通す。 |
| 無効な項目 | `bad host`、`https://`、`name:abc` | `ValueError` となり、`main()` は `[strata] config ...` を表示して `SystemExit` する。 |

比較は大文字小文字を区別しない形に正規化されます。整数・真偽値への変換はありません。`*` は項目全体が `*` の場合だけ特別扱いされ、`*.example.com` はワイルドカードとして解釈されず不正です。設定の `allowed_hosts` も同じ validator で検査され、環境変数に置き換わらず追加で結合されます。重複名は順序を保って一つにまとめます。[`terminal/serve/server_parts/http_api.py:176-195`](../../../../Niko1221/Strata/terminal/serve/server_parts/http_api.py)

## 有効になる条件

- Strata の Python HTTP サーバー起動経路を通ること。`main()` の共通初期化で読み、mock engine を含め engine/backend の条件分岐はありません。[`terminal/serve/server.py:8956-8979`](../../../../Niko1221/Strata/terminal/serve/server.py) [`terminal/serve/server.py:9062-9067`](../../../../Niko1221/Strata/terminal/serve/server.py)
- API キーが設定されている場合は Host チェックをスキップします。API キーなしの場合も、localhost、IP アドレス、listen 先など既知のホスト名は通ります。[`terminal/serve/server.py:6773-6781`](../../../../Niko1221/Strata/terminal/serve/server.py) [`terminal/serve/server_parts/http_api.py:198-208`](../../../../Niko1221/Strata/terminal/serve/server_parts/http_api.py)
- 設定または環境変数で `*` が指定されると、API キーの有無にかかわらず Host 名による拒否は起きません。[`terminal/serve/server.py:6780`](../../../../Niko1221/Strata/terminal/serve/server.py)
- 他の CLI 引数・環境変数によるこの値の上書きはありません。API キーは値の優先順位ではなく、Host チェック自体を無効にする別条件です。

## 実行時の詳細

値はモデル engine の起動後、`Service` の設定中に一度読み込まれ、`svc.allowed_hosts` に保持されます。続いて `serve()` が `host_names_for()` を呼び、allowed hosts と listen アドレス等から判定用集合を作ります。環境変数は子 engine に転送されず、リクエストごとの再読み込みや環境変数値の cache 更新はありません。実行中にプロセス環境を変更してもサーバー設定には反映されません。[`terminal/serve/server.py:8956-8979`](../../../../Niko1221/Strata/terminal/serve/server.py) [`terminal/serve/server.py:9062-9067`](../../../../Niko1221/Strata/terminal/serve/server.py) [`terminal/serve/server.py:8243-8268`](../../../../Niko1221/Strata/terminal/serve/server.py)

各 HTTP リクエストでは `parse_request()` が API キーの有無または Host 許可を判定します。未知の Host は `[strata] refused a request for Host ...: not a name this server answers to ...` を標準出力へ出し、403 JSON を返してそのリクエストを拒否します。設定項目が一つ以上ある場合、起動時には許可名、または `*` の場合に `[strata] Host check off: any name reaches this server (allowed_hosts "*")` を表示します。[`terminal/serve/server.py:6773-6790`](../../../../Niko1221/Strata/terminal/serve/server.py) [`terminal/serve/server.py:9065-9067`](../../../../Niko1221/Strata/terminal/serve/server.py)

## ログと測定値

測定値は該当しません。上記の起動ログ・拒否ログ・403 応答が観測できます。`docs/DETAILS.md` も、API キーなしの Host 制限、カンマ区切り、`.example.com`、`*` の扱いを説明しており、実装と一致します。[`docs/DETAILS.md:722-726`](../../../../Niko1221/Strata/docs/DETAILS.md)

## 根拠

- 環境変数の読み取り、ValueError 時の起動失敗、設定ログ: `terminal/serve/server.py:9062-9067`
- 環境変数と設定値の正規化・結合・重複排除: `terminal/serve/server_parts/http_api.py:176-195`
- Host 名の構文処理、ポートや末尾ドットの除去: `terminal/serve/server_parts/http_api.py:145-159`
- Host 許可判定と API キーによる迂回、403 経路: `terminal/serve/server.py:6773-6790`
- 判定対象ホストの作成と HTTP サーバー起動: `terminal/serve/server.py:8243-8268`
- Strata の説明との照合: `docs/DETAILS.md:722-726`
