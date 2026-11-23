# `strata serve --host`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--host` |
| 別名 | なし |
| 値 | アドレス文字列。空白を含まない空でない文字列が必要 |

## 役割

推論 API サーバーが待ち受けるローカルアドレスを指定する。`127.0.0.1` ならこの PC だけ、`0.0.0.0` なら IPv4 の全インターフェース、`::` なら IPv6 の全インターフェースで待ち受ける。ネットワークから到達できるアドレスを選ぶ場合は、API キーの設定が推奨される。キーがなくても起動できるが、起動時に警告される（`terminal/serve/server.py:8645-8647, 9191-9201`）。

## 使い方

```sh
# この PC 内だけで待ち受ける（既定値）
strata serve --config /path/to/run.json

# IPv4 の全インターフェースで待ち受ける
strata serve --config /path/to/run.json --host 0.0.0.0
```

## 値と既定値

`strata serve` の parser は値を文字列として受け取り、parser 自体では形式や範囲を制限しない（`terminal/strata_cli/cli.py:67-73`）。実効値はコマンドライン指定、保存済みプロファイルの override、run config の `host`、既定値 `127.0.0.1` の順に選ばれる。指定値は空でなく、空白文字を含まない必要がある。IP アドレス形式に限る追加の文字列検査はなく、OS の bind 処理で解決できるアドレスかどうかが確認される（`terminal/strata_cli/cli.py:783-807`, `terminal/strata_control/profiles.py:98-104`）。

## 実行時の動作

選ばれた値は `--host <値>` としてサーバーに渡され、サーバーはそのアドレスとポートで HTTP サーバーを bind する。値にコロンが含まれる場合は IPv6 ソケットを使う（`terminal/strata_cli/cli.py:821-840`, `terminal/serve/server_parts/http_api.py:37-49`, `terminal/serve/server.py:8263-8269`）。

`--plan` を付けると実効設定を表示して終了するため、host の文字列検査は行うが実際の bind は試さない。通常起動では、モデルの読み込みに進む前に指定アドレスとポートを bind して利用可能か確かめる（`terminal/strata_cli/cli.py:954-980`, `terminal/serve/server.py:8824-8828`）。

## 適用条件と副作用

ネットワーク上の他端末から利用させるには、その端末から到達できるアドレスに bind する必要がある。`0.0.0.0` は IPv4、`::` は IPv6 の全インターフェースを対象にする。ネットワーク公開時に API キーが未設定なら、サーバーは到達可能性に関する警告を標準出力へ出すが、起動を拒否しない（`terminal/serve/server.py:8645-8647, 9191-9201`）。

サーバーは指定アドレスで TCP 待受を開始し、そのアドレスに対応する接続先を起動メッセージに表示する。`--host` が `0.0.0.0` または `::` の場合、表示用 URL はループバックに置き換えられる。`0.0.0.0` では取得できた LAN アドレスも表示し、`::` では IPv6 全体待受であることを示す（`terminal/serve/server.py:9182-9206`）。

## 出力とエラー

空文字列、空白を含む値などは profile override 検証で拒否される。通常の human 出力では `strata: host must be a nonempty address without whitespace` の形式で標準エラーに出て、終了コードは 2（`terminal/strata_control/profiles.py:98-104`, `terminal/strata_cli/cli.py:558-563, 2248-2255`）。

bind に失敗すると、サーバーは `listen_problem()` で OS のエラーを説明に変換して parser error として報告する。使用中ポート、利用できないローカルアドレス、権限不足などを区別する。`--plan` では bind を行わないため、この失敗は検出されない（`terminal/serve/server.py:8824-8828`, `terminal/serve/server_parts/base.py:42-62`）。

## 根拠

- `terminal/strata_cli/cli.py:67-73` — `strata serve` の parser 定義。
- `terminal/strata_cli/cli.py:783-807` — 値の優先順位、既定値、profile override 検証。
- `terminal/strata_control/profiles.py:98-117` — host の受理条件。
- `terminal/strata_cli/cli.py:821-840, 954-980` — 有効値のサーバー引き渡しと計画表示経路。
- `terminal/serve/server.py:8641-8647, 8824-8828, 9182-9206` — standalone server 側の説明、bind 事前確認、待受と起動出力。
- `terminal/serve/server_parts/http_api.py:37-55` — IPv4/IPv6 socket family の選択と bind。
- `terminal/serve/server_parts/base.py:42-62` — bind 失敗理由の分類。

調査範囲は Strata の `strata serve` と、同コマンドが起動する `terminal/serve/server.py` の host 処理。ネットワーク到達性そのものは OS・ファイアウォール・ネットワーク構成に依存するため、この文書では断定しない。
