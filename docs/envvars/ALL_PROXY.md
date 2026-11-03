# `ALL_PROXY`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata の Python setup が、ダウンロード失敗時に表示する案内を選ぶために環境変数の設定有無を確認します。`ALL_PROXY` 自体を URL や通信設定として読み取る処理は、この参照箇所にはありません。対象は setup のインストール・準備処理であり、エンジン実行時の環境変数ではありません。

## 値と判定

`proxy_hint()` は `HTTPS_PROXY`、`https_proxy`、`ALL_PROXY`、`all_proxy` の順に `os.environ.get()` で値を取得し、`any()` で真偽値を調べます（`setup.py:202-207`）。したがって `ALL_PROXY` については次の判定です。

| `ALL_PROXY` の状態 | この名前による判定 |
| --- | --- |
| 未設定 | 偽 |
| 空文字 | 偽 |
| 空文字以外 | 真 |

値の形式、大小文字、空白、URL としての妥当性は検査しません。ほかの3名のいずれかに空文字以外が設定されていれば、`ALL_PROXY` の値にかかわらず同じ「proxy is set」案内になります。逆に4名すべてが未設定または空文字なら、HTTPS_PROXY を設定する案内になります。CLI 引数や設定ファイルによる優先順位、無効値の fallback はありません。

## 有効になる条件

この判定が表示に影響するのは setup が通信失敗として `fail()` を呼び、案内文に `proxy_hint()` を含める経路です。HTTP エラーまたは `OSError` の5回目の試行失敗では、対象 URL に到達できない旨とともに案内が出ます（`setup.py:3142-3167`）。DeepSeek engine の取得前チェックでは、ローカル実行ファイル等がなく、パッケージ指定・保留中ファイル・ローカル feed がなく、GitHub の到達確認にも失敗した場合に同じ判定を使います（`setup.py:9051-9056`）。

## 実行時の詳細

`proxy_hint()` は呼ばれるたびに現在の `os.environ` を参照し、結果を cache しません（`setup.py:202-207`）。`ALL_PROXY` が真なら、表示は「`; a proxy is set in this terminal (HTTPS_PROXY): check that it is the right one and that it is running`」です。4名とも偽なら、表示は「`; behind a company or school proxy, set HTTPS_PROXY (for example HTTPS_PROXY=http://host:port) in this terminal first`」です。`fail()` はメッセージを出して `sys.exit(1)` します（`setup.py:965-970`）。DeepSeek の事前チェックでは `proxy_hint()` をメッセージ組み立て時に2回呼びます（`setup.py:9055-9056`）。

setup の `run()` は `env` 引数が省略された場合に `os.environ` を辞書へコピーして子プロセスへ渡します。明示された `env` がある場合はそちらをコピーします（`setup.py:1020-1037`）。これは `ALL_PROXY` を名前指定で加工・上書きする処理ではなく、渡された環境全体の引き継ぎです。このソースから子プロセスや外部ライブラリが `ALL_PROXY` をどう解釈するかは断定しません。

## 根拠

- `setup.py:202-207` — 4種類の proxy 名の存在判定と案内文。
- `setup.py:3142-3167` — ファイル取得の HTTP / OS エラー再試行と最終失敗案内。
- `setup.py:9051-9056` — DeepSeek engine の GitHub 到達失敗経路。
- `setup.py:965-970` — 失敗表示と終了コード 1。
- `setup.py:1020-1037` — setup 子プロセスへ渡す環境辞書。
