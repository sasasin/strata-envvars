# `--url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（委譲先: `python tools/strata_bench.py`） |
| オプション | `--url` |
| 別名 | なし |
| 値 | 値を取る文字列。実行中の Strata server のベース URL |

## 役割

ベンチマーク自身が設定ファイルから server を起動する代わりに、指定した URL で稼働中の Strata server を利用します。URL を指定した場合、health endpoint で Strata server と確認できなければ起動処理へ切り替えずに終了します（`tools/strata_bench.py:935, 975-987`）。

## 使い方

Strata checkout のルートから、既に稼働している server の API ルートを指定します。

```sh
./bench.sh --url http://127.0.0.1:8080
```

Windows では同じ引数を `BENCH.bat` に渡せます。両 wrapper は引数を `tools/strata_bench.py` にそのまま渡します（`bench.sh:6-10`, `BENCH.bat:8-16`）。

## 値と既定値

値は必須の文字列で、未指定時は `None` です。parser に `type`、choices、URL 形式の validation はありません。値を `rstrip("/")` したものをベース文字列として使い、`/health`、`/v1/chat/completions` などの endpoint を連結します。そのため、指定値は API endpoint を組み立てられる server のベース URL である必要があります。末尾の `/` は除去されます（`tools/strata_bench.py:932-936, 975-979`、HTTP request の構築は `117-120, 130-141`）。

URL が無効・到達不能・Strata 以外の server を指す場合の parser-level validation はありません。値を受理した後、`/health` の応答から `service == "strata"` を確認できるかで判定します（`tools/strata_bench.py:123-127, 667-669, 982-987`）。

## 実行時の動作

`--url` があれば末尾の slash を落とした値を base とし、`GET <base>/health` を行います。Strata server と判定された場合、同じ base に対して server 状態・metrics・properties・models を取得し、固定ベンチマークの chat completion 要求を送ります（`tools/strata_bench.py:667-669, 975-984, 601-605, 130-141`）。

この経路では server subprocess を起動しません。したがって `--port` は server 起動に使われず、`--gpu` も server 起動引数としては使われません。ただし `--gpu` が指定されているとレポートのローカル GPU 選択情報に使われる場合があります（`tools/strata_bench.py:936-937, 988-1002, 601, 613-619`）。

`--config FILE` を同時に指定すると config は読み込まれますが、URL 経路では server 起動に使われません。config 内の `api_key` は `--api-key`（既定値は `STRATA_KEY` 環境変数）に値がない場合の fallback となり、設定・モデル情報は取得可能な範囲でレポートに使われます。`--api-key` / config のキーは Bearer authorization として HTTP 要求に付与されます（`tools/strata_bench.py:938, 957-974, 117-120, 130-141, 601-646`）。

## 適用条件と副作用

指定 URL の Strata server が起動済みで、ベンチマークから到達可能であることが条件です。外部・別ホストの server を指定した場合も、このコマンドは `/health`、`/v1/status`、`/metrics`、`/props`、`/v1/models` および chat completion endpoint に通信します。既存 server へのベンチマーク要求は推論負荷を発生させ、server が公開する metrics 等も読み取ります（`tools/strata_bench.py:601-605, 667-669, 130-141`）。

この URL 経路では `started` は false のままであり、終了時の `stop_server` は実行中 server を停止しません。処理結果のレポートは通常 `bench/results/` 以下に新規ディレクトリとして作成されます（`tools/strata_bench.py:981-982, 1017-1018, 1035-1037, 910-918`）。

## 出力とエラー

- 指定先が Strata server と確認できない場合、stderr に `No Strata server answers at <base>.` を出し、終了コード `2` で戻ります。接続失敗や `/health` の JSON 読み込み失敗は `try_json` が例外を握りつぶして `None` とするため、この経路に含まれます（`tools/strata_bench.py:123-127, 667-669, 982-987`）。
- URL は有効だが個々の completion が失敗した場合、HTTP/その他の例外は request 結果の error として記録されます。ベンチマーク結果をレポートへ書いた後、失敗があり chat/prompts/agent の成功結果が一つもなければ終了コード `1`、それ以外は `0` です（`tools/strata_bench.py:145-177, 1017-1018, 1034`）。
- `--compare-only` を指定した場合は server 処理に入る前に比較して終了するため、`--url` は使用されません（`tools/strata_bench.py:951-955`）。

## 根拠

- 索引上の tool scope と委譲先: `docs/cli/README.md:14, 1522-1544`（調査対象 checkout ではなく文書リポジトリ）。
- parser 定義と URL/base の分岐: `tools/strata_bench.py:932-948, 957-987`。
- HTTP health / completion 要求、HTTP 失敗の捕捉: `tools/strata_bench.py:117-127, 130-177, 667-669`。
- server 起動と後処理の条件、レポート出力: `tools/strata_bench.py:688-705, 981-999, 1017-1037, 910-918`。
- wrapper の委譲: `bench.sh:6-10`, `BENCH.bat:8-16`。
- quick benchmark と標準比較ベンチマークの区別: `tools/strata_bench.py:23-28`、標準 CLI の索引リンクは `docs/cli/README.md:610-642`（文書リポジトリ）。

調査範囲は上記 revision のソース checkout です。Release 配布物の実体、URL scheme/host/port の個別形式検証、任意の reverse-proxy 配下での動作は確認していません。実装上、URL を正規化・検証する処理は見当たらず、endpoint path を文字列連結しています。
