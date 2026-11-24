# `strata serve --port`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--port` |
| 別名 | なし |
| 値 | 整数。`0`〜`65535`。`0` は OS に空きポートを割り当てさせる |

## 役割

推論 API と Web UI を待ち受ける TCP ポートを指定する。`strata serve` はこの値を一時的な起動引数としてサーバーへ渡す。設定ファイルや保存済み profile の値を書き換える操作ではない。

## 使い方

```sh
strata serve --profile /path/to/model.json --port 8081
```

`--profile` にはモデルの run config JSON を指定する。`--port 0` とすると OS が割り当てたポートで起動し、起動後の案内には実際に割り当てられた番号が表示される。

## 値と既定値

- 値は `int` として解析され、`0`〜`65535` の範囲が受理される。範囲外は `--port must be in 0..65535` として拒否される（`terminal/strata_cli/cli.py:73,959-960`、profile / run config 由来の値も `terminal/strata_control/profiles.py:98-105` で検証）。
- `--port` を省略した場合、優先順位はコマンドライン、保存済み profile の override、run config の `port`、既定値 `8095`。コマンドラインに値があれば profile や run config より優先する（`terminal/strata_cli/cli.py:783-803`）。
- 整数でない値は parser の型変換で受理されない（`terminal/strata_cli/cli.py:67-74`）。

## 実行時の動作

有効値はサーバー引数列の `--port <値>` に変換される（`terminal/strata_cli/cli.py:821-835`）。サーバー側も整数として解析し、HTTP server を `(host, port)` で作成して待ち受ける（`terminal/serve/server.py:9174,8779-8785`）。待ち受けるアドレスは `--host` または設定側で別に決まり、`--port` 自体は変更しない（`terminal/serve/server.py:9324,9721`）。

起動前に同じ host と port で一度 bind して使用可能か確かめ、確認用 socket を閉じてから残りの起動処理に進む（`terminal/serve/server.py:9341-9345`）。`--port 0` の場合、確認用 bind と実サーバーの bind はそれぞれ OS に割当を求める。実サーバーの `server_address[1]` を採用し、ready 表示と instance record にその実ポートを使う（`terminal/serve/server.py:9721-9729,9752-9757`）。

## 適用条件と副作用

この値は `strata serve` の起動時に使われ、起動中の待ち受けポートを変更するものではない。指定した port が利用中の場合は起動前確認で拒否される。Windows では Strata の HTTP server が address reuse を無効にして二重起動時の同一 port bind を失敗させる（`terminal/serve/server_parts/http_api.py:37-40`）。

ポートの bind が OS に拒否された場合、エラーには host、port、OS の理由と状況に応じた案内が含まれる。使用中なら別の `--port` を使うよう案内し、権限不足や当該 host がこの PC のアドレスでない場合も区別する（`terminal/serve/server_parts/base.py:42-62`、呼び出し元 `terminal/serve/server.py:9341-9345`）。1024 未満の port は Linux / macOS では管理者権限を要する場合があると案内する。実際に bind できるかは OS とその時点のポート状態に依存する。

## 出力とエラー

- 範囲外の値は `strata` 側でエラーになり、通常形式では終了コード `2`（`terminal/strata_cli/cli.py:868-874,954-960`）。
- bind できない場合は server parser の usage error と `listen_problem` の説明が出る（`terminal/serve/server.py:9341-9345`、文面の分岐 `terminal/serve/server_parts/base.py:42-62`）。
- 起動成功時は `ready: http://...:<実ポート>/v1` などの URL が表示される（`terminal/serve/server.py:9721-9729`）。`--port 0` なら `<実ポート>` は OS が割り当てた番号。

## 根拠

- `terminal/strata_cli/cli.py:62-74` — `strata serve` parser と `--port` の整数型宣言。
- `terminal/strata_cli/cli.py:783-835,954-960` — 値の優先順位、既定値、サーバー引数への転送、範囲検証。
- `terminal/strata_control/profiles.py:98-105` — profile / run config と共有する port 値の検証範囲。
- `terminal/serve/server.py:9174,9324,9341-9345,9721-9757` — server 側 parser、起動前 bind 確認、待ち受けと OS 割当 port の報告。
- `terminal/serve/server_parts/http_api.py:37-55` — HTTP server の bind 設定と IPv6 address family の選択。
- `terminal/serve/server_parts/base.py:42-62` — bind 失敗理由の説明と案内。
