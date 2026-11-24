# `strata serve --offline`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--offline` |
| 別名 | なし |
| 値 | なし。`store_true` のフラグ |

## 役割

既存の run config で推論サーバーを起動するとき、サーバーによるリモート画像の取得を止め、MCP サーバーや `before_load` コマンドなどネットワークを使い得る設定を拒否します。エンジンなどサーバーが起動する子プロセスにもオフライン用の環境変数を渡します。これは OS のネットワークサンドボックスではなく、環境変数を無視して直接通信する子プロセスや、独自の通信手段を持つライブラリを遮断しません。DNS 問い合わせも遮断しないとポリシー実装に記されています。(`terminal/strata_cli/cli.py:67-80`, `terminal/serve/server.py:9372-9394`, `terminal/strata_control/offline.py:15-32,167-174`)

## 使い方

```sh
# run config を指定して、オフライン条件を満たすか確認する
strata serve --profile ./run.json --offline --plan

# 条件を満たす run config でサーバーをフォアグラウンド起動する
strata serve --profile ./run.json --offline
```

`--profile` は `--config` の別表記です。`--offline` 自体は値を取りません。(`terminal/strata_cli/cli.py:67-80`)

## 値と既定値

値、別名、数値範囲の指定はありません。Terminal CLI では未指定時は run config の `offline`、保存済み serving profile の `overrides.offline`、どちらもなければ `false` が使われます。優先順はコマンドラインでの指定、保存済み profile、run config、既定値です。CLI の `store_true` は明示的な `false` を渡せない形に処理され、profile 側の `offline: true` を無効にするには `strata profile set <name> offline=false` のように profile を変更します。(`terminal/strata_cli/cli.py:783-807`, `terminal/strata_control/profiles.py:26,88-95,98-117`)

## 実行時の動作

Terminal CLI は有効値が真なら、起動するサーバーの引数に `--offline` を追加します。サーバーは MCP 設定または `before_load` コマンドがある場合、起動前にエラーにします。また、プロファイルが MCP サーバー、`before_load`、リモート画像を許す `images` / `vision` の `remote_sources`・`allowed_hosts`・`url` を宣言している場合も、strict offline にできない理由を付けて拒否します。CLI 側の計画作成段階でも run config の `mcp_servers` または `before_load` を検出して拒否します。(`terminal/strata_cli/cli.py:816-817,833-842`, `terminal/serve/server.py:9372-9384`, `terminal/strata_control/offline.py:137-164`)

エンジンを起動するときは、通常の設定で組み立てた子プロセス環境へオフライン用の値を最後に適用します。`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`PIP_NO_INDEX=1`、`STRATA_OFFLINE=1` などを設定し、proxy 環境変数を空にして `NO_PROXY=*` とします。設定ファイルの `env` に同じキーがあっても、このポリシー値が優先されます。単一エンジン、replica、split の各起動経路にこの値が渡されます。(`terminal/strata_control/offline.py:42-59`, `terminal/serve/server.py:4007-4049,8788-8919,9391-9394,9472-9477`)

推論リクエストに HTTP(S) 画像 URL が含まれると、サーバーはダウンロードせず `ValueError` とします。画像を含むリクエストの通常のエラー経路では、`400 invalid_request_error` を返し、ログにも `400 invalid request` として記録します。ローカル画像や `data:` 画像はこの URL 拒否条件には該当しません。(`terminal/serve/server.py:5501-5504,5562-5584,7877-7882`, `terminal/strata_control/offline.py:61-65,88-110`)

## 適用条件と副作用

このオプションは `strata serve` の起動時に評価されます。MCP サーバー、`before_load`、ネットワーク画像ソースを含む構成は、サーバー起動や最初の推論リクエストに進む前に拒否されます。`--mcp-config` で MCP を渡す場合も、生成された hub が存在すれば同様に拒否されます。エンジン起動経路では子プロセス環境が変わりますが、オプション自体がファイルを書き換える処理は確認できません。(`terminal/serve/server.py:9372-9394`, `terminal/strata_control/offline.py:137-164`)

この制約はネットワーク遮断を保証するものではありません。子プロセスがオフライン用環境変数を無視して直接 socket を開く場合や、読み込み済みライブラリが独自のネットワーク処理をする場合は止められず、DNS 問い合わせも遮断されません。(`terminal/strata_control/offline.py:167-174`)

## 出力とエラー

設定に MCP サーバーまたは `before_load` がある場合は `--offline requires MCP servers and before_load commands to be disabled in this profile`、ネットワークソースを許す場合は `--offline cannot be strict for this profile: ...` を渡して parser のエラー経路に入ります。画像 URL を使う推論は `400 invalid_request_error` になります。(`terminal/serve/server.py:9372-9384,7877-7882`)

## 根拠

- `terminal/strata_cli/cli.py:67-80` — `strata serve` parser、必須 profile/config と `--offline` の定義。
- `terminal/strata_cli/cli.py:783-818,833-842` — 値の優先順位、profile/config 検証、サーバー引数への転送。
- `terminal/strata_control/profiles.py:26,88-117` — profile の `offline` 値の受理と Boolean validation。
- `terminal/serve/server.py:9189-9190,9372-9394,9472-9477,9492-9498` — サーバー parser、起動前拒否、子プロセスへの適用、Service への設定。
- `terminal/serve/server.py:4007-4049,5501-5504,5562-5584,7877-7882` — 子プロセス環境とリモート画像拒否・HTTP エラー経路。
- `terminal/strata_control/offline.py:42-59,88-117,137-174` — 環境変数、URL 判定、profile 要件、適用範囲の制約。
