# `strata serve --host`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--host` |
| 別名 | なし |
| 値 | listen するアドレス文字列。値を1つ取る |

## 役割

推論 API サーバーが bind するアドレスを指定します。既定値 `127.0.0.1` はこの PC からの接続に限られます。`0.0.0.0` などを指定すると他のネットワーク機器から到達可能なインターフェースにも listen します。サーバーの起動自体はフォアグラウンドで行われます。

## 使い方

```sh
strata serve --profile /path/to/model.json --host 127.0.0.1
```

LAN の別端末から接続させる場合の指定例:

```sh
strata serve --profile /path/to/model.json --host 0.0.0.0
```

後者では、到達できる相手が推論 API を利用できる状態になるため、API キーを設定してから利用してください。コード上はキーなしでも起動を拒否せず、起動時に警告します。

## 値と既定値

- `--host` は値を文字列として受け取ります。alias はありません（`strata_cli/cli.py:46-52`）。
- 選択順は CLI の明示値、保存 profile の `host` override、run config の `host`、既定値 `127.0.0.1` です。環境変数による host の上書きはこの選択処理にありません（`strata_cli/cli.py:745-765`）。
- host 値は空でなく、空白文字を含まない文字列である必要があります。IP アドレスやホスト名の形式・到達可能性はこの段階では検査しません（`strata_control/profiles.py:98-104`）。
- CLI から空文字または空白を含む値を渡すと profile override の検証で `ProfileError` になります。通常のエラー出力は stderr、終了コード 2 です（`strata_cli/cli.py:766-769`, `strata_cli/cli.py:527-532`, `strata_control/profiles.py:30-35,98-104`）。

## 実行時の動作

有効 host と port は `serve.server` に渡す argv に `--host <host>` として組み込まれます（`strata_cli/cli.py:782-795`）。サーバーは `Server((host, port), ...)` で bind し、同じ host から host 名の許可リストも構成します。非 loopback bind の場合は PC 名、LAN アドレスなどもその集合に含めます（`serve/server.py:7605-7622,7718-7724`）。

`--plan` を付けると有効値と起動 argv を含む計画を表示して終了し、サーバーを起動しません。そのため、実際の socket bind 可否は `--plan` では確認されません（`strata_cli/cli.py:935-942`）。通常起動ではサーバーがモデル読み込み前にアドレスとポートを bind できるか試します（`serve/server.py:8304-8308`）。

## 適用条件と副作用

- `127.0.0.1`、`localhost`、`::1` 以外の host は、コード上でネットワーク向けとして扱われます。起動出力に接続 URL を表示し、LAN アドレスが見つかれば別端末用 URL も表示します（`serve/server.py:8615-8630`）。
- ネットワーク向け bind でも API キーは必須ではありません。キーがない場合は、到達可能な人がモデルを使える旨の警告を stdout に出します（`strata_cli/cli.py:785-795`, `serve/server.py:7650-7662,8624-8633`）。このオプション自体は API キーや firewall ルールを設定しません。
- bind address は起動時に使われます。無効なアドレスやこの PC に割り当てられていないアドレスでは listen に失敗します。OS や firewall の制約でも失敗し得ます（`serve/server.py:144-160,8304-8308`）。

## 出力とエラー

起動成功時は `ready: http://<host>:<port>/v1` などの URL を stdout に表示します。非 loopback bind では LAN 接続先と、キー未設定時には警告も表示します（`serve/server.py:8615-8633`）。

bind できない場合、サーバー parser は `cannot listen on <host>:<port>...` と原因別の案内を含めてエラーにします。使用中のポート、未割り当てアドレス、その他の OS エラーは別の説明になります（`serve/server.py:144-160,8304-8308`）。

## 根拠

- Terminal CLI の parser と有効値の優先順位・サーバー argv 生成: `strata_cli/cli.py:40-67,745-805`
- profile override の host validation: `strata_control/profiles.py:98-117`
- サーバー側の bind address parser、fallback、bind preflight: `serve/server.py:8143-8145,8288-8308`
- bind 後の host 名構成、listen、接続 URL とネットワーク警告: `serve/server.py:7605-7622,7718-7724,8615-8638`

この文書は同一 revision のソースを調査したものです。異なる OS の socket エラー文面や firewall の実際のネットワーク到達性は実機で確認していません。
