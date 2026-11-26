# `setup.py` / `setup.sh` / `START-HERE.bat` `--port`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（Linux/macOS: `./setup.sh`、Windows: `START-HERE.bat` 経由） |
| オプション | `--port` |
| 別名 | なし |
| 値 | 整数。明示的な範囲チェックはなく、最終的な TCP bind が OS の値域・使用状況を検査する |

## 役割

モデルのセットアップ時または起動時に、Strata HTTP サーバーが listen する TCP ポートを指定します。セットアップでモデルを構成するときはポートをモデル設定に保存し、その後の起動で省略すれば保存値を使います。すでに構成済みのモデルを通常起動するときに指定した場合は、その起動で使うポートを上書きします。

## 使い方

```sh
# Linux: 新規セットアップ／設定変更時にポートを保存
./setup.sh --setup --port 8081

# Linux: 保存済み設定を変えず、この起動だけポートを上書き
./setup.sh --port 8081
```

Windows では同じ引数を `START-HERE.bat --setup --port 8081` または `START-HERE.bat --port 8081` として渡します。ラッパーは引数を `terminal/setup.py` に渡します（`setup.sh:7-17, 80-81`、`START-HERE.bat:8-13, 49-65`）。

## 値と既定値

- `terminal/setup.py:11488` で `argparse` の `type=int` として登録されています。値を省略した場合は `None` です。整数にできない値は `argparse` が拒否します。独自のポート範囲 validation はありません。
- `terminal/setup.py:11729` は `a.port or 8080` をセットアップ時のポートに使います。そのため未指定時は 8080、明示値 0 も falsy として 8080 になります。負数などの非ゼロ整数はこの箇所では拒否されず、サーバーの bind まで渡ります。
- 新しい設定の作成では `port` を設定オブジェクトに渡し、`terminal/strata_control/setup_config.py:140, 433-435` で run config の `port` として保持します。既存の設定を引き継ぐ場合は、明示値がなければ以前の `port` を採用します（`terminal/setup.py:11700-11713`）。

## 実行時の動作

- `--setup` 等でモデル設定を作成・変更する経路では、確定した `port` が設定ファイルへ書かれます（`terminal/setup.py:11729, 12521-12527`）。`--no-start` もこの設定書き込み後に終了するため、ポートを保存し、サーバーは起動しません（`terminal/setup.py:12525-12527, 12555-12556`）。
- 既存モデルの通常起動では `a.port` を `start()` に渡し、`terminal/setup.py:8601-8602` が明示値を優先して serve プロセスの `--port` に渡します。未指定なら run config の `port`、それもなければ 8080 です。この通常起動経路では、`--port` 自体を run config に書き戻しません。
- Intel Arc の設定作成経路では、値が truthy の場合に限り `cfg["port"]` を更新して設定を保存します（`terminal/setup.py:9439-9448`）。
- `--update`、`--rollback-engine`、`--prepare-pack`、`--inspect` などの早期終了経路は通常サーバーを起動せず、`--port` はその処理に使われません（`terminal/setup.py:11622-11638, 11692-11697`）。
- サーバーは起動前に指定 host/port で一度 bind して、モデルの読み込みに時間をかける前に使用可否を確認します。失敗時は server parser の `error` 経路に入り、実際の起動時にも同じ host/port で待ち受けます（`terminal/serve/server.py:9340-9344, 8779-8784`）。
- サーバーが起動すると ready 行と API URL に bind したポートを表示します。セットアップ経路では OpenAI/Anthropic API URL も表示します（`terminal/serve/server.py:9721-9729`、`terminal/setup.py:12536-12543`）。

## 適用条件と副作用

- ポートの作用は HTTP サーバーの listen 先に限られます。外部端末から到達できるかは別設定の host に依存し、通常の既定 host は `127.0.0.1` です。host を全インターフェースにした場合はネットワークからの到達性が変わります（`terminal/setup.py:11501-11504`、`terminal/serve/server.py:9161-9163, 9721-9739`）。
- ポートが使用中、または OS が bind を拒否する値の場合、server 側の起動前確認が失敗します。`--port` による独立した数値範囲チェックやポート自動探索は確認できません。
- macOS の通常セットアップは root parser に入る前に専用エントリへ引数を委譲します（`terminal/setup.py:9290-9294, 11436-11437`）。この分岐のオプション文書は索引上の [`source-setup/mac --port`](../mac/--port.md) です。Hy4-Flash / Inkling-2-Mini の分岐は root parser 側で処理され、`a.port or 8080` をインストール関数へ渡します（`terminal/setup.py:11389, 11413`）。
- `strata serve --port` は別の tool/command scope のオプションであり、この文書の `source-setup/root --port` と同一の parser ではありません。

## 出力とエラー

- 整数として解釈できない引数は setup の `argparse` で拒否されます（`terminal/setup.py:11444, 11488, 11606`）。
- bind の失敗は serve 側で `ap.error(...)` に渡されます（`terminal/serve/server.py:9341-9344`）。具体的な OS ごとのエラー文言は実行環境に依存するため、ここでは固定しません。
- Setup の処理が失敗した場合、共通 `fail()` は説明を表示して終了コード 1 で停止します（`terminal/setup.py:1049-1056`）。server 起動時の終了コードは setup が子プロセスから返されたコードを返します（`terminal/setup.py:8702-8704, 12562, 12565-12571`）。

## 根拠

- `terminal/setup.py:11488` — root setup parser の `--port` 定義、整数変換、help の既定値説明。
- `terminal/setup.py:11700-11713, 11729` — 以前の設定からの継承と、新規セットアップ用の既定値選択。
- `terminal/setup.py:8558-8563, 8601-8602, 8702-8704` — 起動関数から serve subprocess へのポート転送と終了コード伝播。
- `terminal/setup.py:12521-12527, 12536-12543, 12555-12562` — run config 書き込み、URL 表示、`--no-start` と起動の分岐。
- `terminal/strata_control/setup_config.py:140, 433-435` — run config の `port` 保存。
- `terminal/serve/server.py:8779-8784, 9340-9344, 9721-9729` — listen、起動前 bind 確認、ready URL 表示。
- `setup.sh:7-17, 80-81`、`START-HERE.bat:8-13, 49-65` — POSIX/Windows wrapper から setup parser への引数転送。
- `docs/cli/README.md:1659-1707` — `source-setup` の階層と、対象リンクが `source-setup/root/--port.md` であること。
