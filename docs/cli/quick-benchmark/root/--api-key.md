# `--api-key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（委譲先: `python tools/strata_bench.py`） |
| オプション | `--api-key` |
| 別名 | なし |
| 値 | 文字列。parser による形式検証なし |

## 役割

ベンチマークが Strata HTTP API に送る認証キーを指定します。起動済みサーバーを使う場合も、このキーが問い合わせとベンチマーク要求に使われます。省略時は環境変数または読み込んだモデル設定からキーを選びます。

## 使い方

起動済みのローカルサーバーに環境変数のキーで接続する例です。

```sh
./bench.sh --url http://127.0.0.1:8080 --api-key "$STRATA_KEY"
```

`BENCH.bat` も引数を `tools/strata_bench.py` にそのまま渡します。Windows では同じオプションを `BENCH.bat --api-key <キー>` の形で指定できます。

## 値と既定値

- 値は任意の文字列として受理され、空文字を含む値の形式・長さ検査はありません。値なしでは `argparse` がエラーにします（`tools/strata_bench.py:932-948`）。
- parser の既定値は `STRATA_KEY` 環境変数で、未設定なら空文字です。その後、選択した設定 JSON の `api_key` が次の候補になります。実効優先順位は、空でない `--api-key` 値、空でない `STRATA_KEY`、空でない設定の `api_key`、キーなし、の順です。空文字を明示しても後続候補へフォールバックします（`tools/strata_bench.py:938,957-974`）。
- `--url` を使い `--config` を省略した場合は設定 JSON を読まないため、キーは `--api-key` または `STRATA_KEY` から得ます。`--url` と `--config` を併用した場合は設定 JSON のキーもフォールバック候補になります（`tools/strata_bench.py:957-974`）。

## 実行時の動作

選ばれたキーは Strata の `/health` 判定、起動待ち、状態・メトリクス等の取得、および benchmark の chat request に渡されます。HTTP request ではキーが空でない場合に `Authorization: Bearer <key>` ヘッダーを付け、空ならヘッダーを付けません（`tools/strata_bench.py:117-128,130-141,601-605,667-670,708-715,974-1002`）。同時リクエスト測定も同じキーを `serve_load.one` に渡します（`tools/strata_bench.py:372-385`）。

このオプションはクライアント側の認証値です。新しくサーバーを起動する場合、サーバーにはモデル設定ファイルを `--config` で渡し、`--api-key` の値を起動引数として渡していません（`tools/strata_bench.py:688-705,988-996`）。そのため、サーバー側で必要なキーと異なる値を指定すると、HTTP API の認証が通らないことがあります。

## 適用条件と副作用

- `--api-key` 単独では接続先を決めず、サーバー設定や起動方法も変更しません。接続先は `--url`、または設定の host/port から決まります（`tools/strata_bench.py:975-979`）。
- 設定ファイル経由で起動する通常経路では、設定ファイルが必須です。見つからない場合は stderr に案内を出して終了コード `2` で戻ります。`--url` を指定すれば設定ファイルなしでも実行できます（ただし `--config` を併用すればそのファイルを読みます）（`tools/strata_bench.py:957-973`）。
- キーは結果オブジェクトに直接追加されず、レポートを書き出す前に文字列の秘匿処理へ渡されます。秘匿処理はキーを `<key>` に置換対象として登録しますが、4文字未満の値は登録しない実装です。また、通常の表示は `--quiet` で抑制できますが、認証エラー等の stderr 出力は別経路です（`tools/strata_bench.py:68-105,910-918,947-949,985-999`）。短いキーを使う場合は、生成レポートやエラー出力にキーが現れないか確認してください。

## 出力とエラー

- 指定した URL に Strata が応答しない場合、`No Strata server answers at <address>.` を stderr に出し、終了コード `2` で戻ります（`tools/strata_bench.py:983-987`）。認証失敗もこの判定に入る場合があります。HTTP エラーは `try_json` が捕捉して `None` を返すため、認証拒否と接続不能をこのメッセージだけで区別できない経路があります（`tools/strata_bench.py:123-128,667-670`）。
- ローカル起動経路でサーバーが ready にならなければ、ログ末尾を stderr に表示して終了コード `1` で戻ります（`tools/strata_bench.py:992-999`）。
- benchmark の chat request が HTTP エラーになった場合は応答本文の先頭 200 bytes をエラー文字列に含め、失敗として記録・表示します（`tools/strata_bench.py:139-177,238-240`）。

## 根拠

- `tools/strata_bench.py:932-948` — `--api-key` の parser 定義と `STRATA_KEY` 既定値。
- `tools/strata_bench.py:957-980` — 設定の読込条件、キーの優先順位、接続先と redactor の初期化。
- `tools/strata_bench.py:117-141,601-605,667-715,983-1002` — HTTP Authorization header、Strata 確認・ready 待ち、API 呼び出し。
- `tools/strata_bench.py:68-105,910-918` — キーを含む文字列の秘匿処理とレポート書き出し。
- `bench.sh:6-10`、`BENCH.bat:8-16` — wrapper が引数を `tools/strata_bench.py` へ委譲。
- `docs/cli/README.md:1522-1544` — `quick-benchmark` のツール境界とオプション文書の配置。
