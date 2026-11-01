# `STRATA_ALLOWED_HOSTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の Python HTTP サーバーに、待受先やローカル名以外で受け付ける `Host` 名を追加します。DNS rebinding 対策として、API key がない場合の全 HTTP リクエストで行う Host 検査に使われます。設定ファイルの `allowed_hosts` と環境変数の値は併合されます。

この変数は `serve/server.py` が読むサーバー設定です。C++/CUDA/HIP/SYCL engine に値を渡す処理は見つかりませんでした。

## 値と判定

値はカンマ区切りで分割され、各空白要素を無視した後、個々の要素の前後空白を除き小文字化します。値全体を真偽値や数値へ変換する処理はありません。

| 環境変数の状態・要素 | 処理 |
|---|---|
| 未設定 | `os.environ.get(..., "")` により空文字として扱い、追加ホストなし |
| 空文字 | 分割後の空要素は無視され、追加ホストなし |
| `a.example.com,b.example.com` | 2 つのホスト名を追加 |
| 空要素を含む値（例: `a,, b,`） | 空要素を無視し、残る名前を追加 |
| `*` | ワイルドカードとして保持。Host 検査の `any_host` が真になり、任意の Host 名を通す |
| `.example.com` | ドット付きのまま保持し、`example.com` 自身とその配下の名前を許可 |
| 不正なホスト要素 | `ValueError`。起動処理が `[strata] config ...` を伴う `SystemExit` とし、サーバーを開始しない |

各名前は `strip()` と `lower()` の後、`://` より後ろ（あれば）および最初の `/` より前を取り出します。そのため scheme と path は捨てられ、`host:1234` のような数値 port は `host_name()` が落とします。通常の名前は空でなく、文字が英数字・`-`・`.`・`_` のいずれかである必要があります。ポートが数値でないもの、scheme/path を除いた後に名前が空になるものなどは不正です。IPv6 の裸のアドレスは `host_name()` がコロンを含む場合に通すため、名前の整形として保持されます。重複は順序を保って除去されます。

## 有効になる条件

- `serve/server.py` の HTTP サーバー起動経路で有効です。環境値は `main` の初期化中に一度読み込まれ、`svc.allowed_hosts` に保存されます。起動後にプロセス環境を書き換えても再読込されません。
- 設定ファイルの `allowed_hosts` は環境変数より優先して置換する値ではなく、両方が連結されます。設定項目はホスト名の文字列または文字列リストである必要があり、誤った型も起動エラーです。CLI の `--host` は待受アドレスとして別に扱われ、そのアドレスから求めた名前に許可名が追加されます。
- API key が設定されている場合は `parse_request()` が Host 検査をスキップするため、この変数による許可名追加は実質不要です。API key がない場合に Host 検査が適用されます。
- OS、GPU backend、build macro、モデルのロード状態による分岐はこの変数の読み取り・適用にはありません。

## 実行時の詳細

サーバー初期化時、`allowed_hosts_of(cfg.get("allowed_hosts"), os.environ.get("STRATA_ALLOWED_HOSTS", ""))` で設定値を正規化し、`svc.allowed_hosts` に格納します。設定値があると、`*` を含む場合は `Host check off: any name reaches this server (allowed_hosts "*")`、それ以外は追加名を表示する `[strata] also answers to the host names ... (allowed_hosts)` ログを stdout に出します。不正値では `SystemExit(f"[strata] config {e}")` となり、通常のサーバー待受開始まで進みません。

`serve()` は待受アドレス、`svc.allowed_hosts`、`trusted_origins` から `svc.host_names` を組み立てます。API key がないリクエストでは、`parse_request()` がリクエストの `Host` を検査します。許可された名前に該当しない場合、stderr ではなく stdout に `[strata] refused a request for Host ...` を出し、HTTP 403 と DNS rebinding protection のエラー JSON を返して、そのリクエストを拒否します。`*` が許可リストにあるとすべての Host が通ります。

Host 検査では、許可名のほか、空の Host、IP アドレス、`localhost` とそのサブドメインも通ります。待受アドレスが非 loopback の場合は、この PC の名前や LAN アドレスなども `host_names` に加わります。したがって `STRATA_ALLOWED_HOSTS` は追加許可名であり、許可名だけに絞り込む設定ではありません。

同じ名前の全参照を検索した結果、実際の環境読み取りは `serve/server.py:9381` の一箇所です。ほかのソース上の一致はコメントと拒否応答文、説明文書、候補一覧です。動的な helper の引数 `env` は `allowed_hosts_of()` の第二引数で、上記の起動処理から渡されます。

## 根拠

- `serve/server.py:9381-9386` — 環境値の読み取り、設定項目との併合、エラー処理、起動ログ。
- `serve/server.py:8303-8322` — 型検査、カンマ分割、空要素処理、正規化、wildcard、無効値と重複の処理。
- `serve/server.py:8272-8286` — Host 名および port の構文処理。
- `serve/server.py:8325-8342,8438-8444` — 待受名・許可名・trusted origin からの Host 名集合作成とサーバーへの適用。
- `serve/server.py:6875-6892,8345-8355` — API key を条件とする Host 検査、拒否時のログ・403、および許可される Host の判定。
- `serve/server.py:9134-9142,9013-9018` — `STRATA_API_KEY`、`--api-key`、設定値から API key を決める別経路。API key があると Host 検査がスキップされる。
- `docs/DETAILS.md:632-636` — Host 許可設定に関する利用者向け説明。実装の追加許可名、wildcard、API key による検査解除と一致します。
- `docs/LLAMA_SWAP.md:19-27,37-53` — proxy で使う例と環境変数・設定項目の同等性の説明。
