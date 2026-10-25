# `--api-port`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--api-port` |
| 別名 | なし |
| 値 | 整数。既定値は `8123` |

## 役割

`strata tune run --mode api` が候補ごとの計測 worker を起動するとき、その HTTP 待受ポートを指定します。worker は `127.0.0.1` に bind されます。このオプションは既存の Strata server のポート変更や、`strata tune run` の保存先ポート指定ではありません。

## 使い方

```sh
strata tune run --engine /path/to/strata --backend metal --model example \
  --mode api --config ./strata-example.json --api-expect 'hash table' --api-port 8124
```

`api` モードでは `--config` と `--api-expect` も必要です。計測する worker が実際に起動できる環境・設定を用意してください。

## 値と既定値

- `argparse` の `type=int` で整数へ変換され、未指定時は `8123` です。整数でない値は parser に拒否されます。
- CLI 側にはポート範囲の明示的な validation、重複指定の独自処理、利用可能ポートの事前確認がありません。通常の `argparse` の値格納により、同じオプションを複数回指定すると最後の値が使われます。
- 指定値は worker の `serve.server --port` 引数へそのまま渡されます。範囲外の値や bind できない値の扱いは worker / OS 側に委ねられます。

## 実行時の動作

- `--mode api` の場合、CLI は `--api-port` を API 計測 harness に渡します。harness は各候補の設定を一時 JSON ファイルへ書き、`python -m serve.server` を `--host 127.0.0.1 --port <指定値>` で起動し、そのポートの `/health` が応答するまで確認します。
- 基準計測や候補計測のたびに worker を起動して測定し、終了時に worker を停止します。候補設定の一時 JSON は削除を試みます。ポートは API モードの計測 worker にだけ用いられ、`--mode protocol`（既定モード）では参照されません。
- `--mode api` では `--config` がない場合、または `--api-expect` がない場合、計測開始前にエラーとなります。これらは `--api-port` 自体の validation ではありません。
- worker は `127.0.0.1` に bind するため、この harness のポートはローカル接続用です。同じポートを別プロセスが使用している場合、worker の起動・health check に失敗し計測が成立しません。

## 適用条件と副作用

- `--mode api` を選んだ場合のみ効果があります。既定の `protocol` モードでは、値を指定してもポートを開きません。
- `--api-port 0` は整数として受理され worker へ渡されますが、worker が OS 割当ポートを使っても harness は指定値 `0` の URL を `/health` 確認先にするため、動的ポート割当としては機能しません。
- API 計測では worker 子プロセスを起動し、server がそのポートを bind します。harness はログを一時ファイルに取り、worker 終了後もログファイル自体を削除しません。API harness は入力の設定ファイルではなく候補設定の一時コピーを worker に渡します。

## 出力とエラー

- 人間向け出力では API モード開始時に `measuring through the HTTP API at port <port>` を表示します。JSON 出力ではこの開始メッセージは出しません。
- worker が起動前に終了した場合は終了コードを含む計測失敗、起動期限内に `/health` が応答しない場合は timeout 系の計測失敗になります。tuning runner は計測例外を候補の失敗状態・理由として記録し、レポートに失敗候補を表示します。worker が起動できない状態は通常、候補の推薦対象になりません。
- `--mode api` の前提である `--config` または `--api-expect` がないと、CLI はエラーを返します（終了コード `2`）。不正な整数値も `argparse` が拒否します。

## 根拠

- `strata_cli/cli.py:414-459` — `tune run` parser、`--mode` の既定値、`--api-port` の整数型・既定値、関連オプション。
- `strata_cli/cli.py:1771-1786` — API モードの前提条件と `a.api_port` の harness への受け渡し。
- `strata_cli/cli.py:1788-1795,1822-1824` — 人間向けポート表示と失敗候補の表示。
- `strata_control/tune_api.py:49-79,91-104` — host/port の保持、worker 起動引数、health check と起動失敗。
- `strata_control/tune_api.py:123-142,259-292` — worker 停止、候補設定一時ファイルと cleanup。
- `serve/server.py:8153-8157,8615-8622` — worker の `--port` parser と server bind。`--port 0` では server が実際の割当ポートを取得・表示する。
- `serve/server.py:7718-7724` — server が指定 host/port に bind する箇所。
- `strata_control/tuning.py:486-509` — 計測例外を候補の失敗 status / reason にする処理。
