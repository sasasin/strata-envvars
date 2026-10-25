# `--config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--config` |
| 別名 | なし |
| 値 | run configuration JSON ファイルのパス（文字列） |

## 役割

`--mode api` の測定 worker が使う run configuration を指定します。これにより候補ごとに設定のコピーを作り、候補フラグを反映して worker を起動し、HTTP API 経由で計測します。`--mode protocol`（既定）ではこのオプションは計測に使われません。

## 使い方

```sh
strata tune run --engine /path/to/strata-engine --backend cuda --model example-model \
  --mode api --config /path/to/strata-example.json --api-expect 'expected phrase'
```

`--engine`、`--backend`、`--model` は別途必須です。`api` モードでは `--config` と `--api-expect` も必要です。実際のパス、backend、モデル ID、回答に合う正規表現を指定してください。

## 値と既定値

parser は値を文字列として受け取り、既定値は `None` です。拡張子、ファイルの存在、JSON の形式は parser では検証しません。短縮別名やパスの型変換もありません。複数回指定時に専用の重複検査はなく、通常の `argparse` の `store` 動作で最後の値が採用されます（`strata_cli/cli.py:441-442`）。

## 実行時の動作

- `strata tune run` はまず `--engine`、`--backend`、`--model` と各測定条件から tuning plan を作ります。plan はこの run configuration からは作られず、`--engine` の実体や backend、model の指定が基準です（`strata_cli/cli.py:1759-1768`）。API モードでも両方を指定するため、run configuration とこれらの識別情報が一致するかは利用者が確認してください。ソース上、それらの一致を検査する処理は確認できません。
- `--mode api` のとき `--config` がなければ終了コード 2 でエラーになります。さらに `--api-expect` も必須です。期待値なしでは速い誤答を正答扱いできないためです（`strata_cli/cli.py:1771-1779`）。
- 指定ファイルは `make_api_measure` が UTF-8 で読み、JSON としてロードします。計測のたびに候補の args をその設定へ反映した一時 JSON を作り、その一時ファイルを `serve.server --engine strata --config <一時ファイル>` の起動引数に渡します。元の指定ファイルは書き換えません（`strata_control/tune_api.py:259-283`; `strata_control/tune_api.py:73-78`）。
- worker は候補ごとに起動し、health endpoint の準備完了を待って HTTP API リクエストを計測します。候補ごとに再起動するのは、設定変更を稼働中 server に反映したと誤認しないためです（`strata_control/tune_api.py:41-47`; `strata_control/tune_api.py:80-104`）。
- 各計測後に worker を終了し、一時 JSON を削除します。削除に失敗した場合は無視されるため、一時ファイルが残る可能性があります（`strata_control/tune_api.py:284-292`）。
- `--mode protocol` では engine 自身の serve protocol 用計測器を選択し、`--config` は参照されません。既定 mode も `protocol` です（`strata_cli/cli.py:431-434`; `strata_cli/cli.py:1780-1786`）。従って、`protocol` で `--config` を指定しても worker 用設定として作用しません。

## 適用条件と副作用

このオプションが実際に使われるのは `--mode api` のみです。各候補で worker 子プロセスを起動し、`127.0.0.1` の指定 API port（既定 `8123`）へリクエストします。プロセス出力は一時ログに記録されます（`strata_control/tune_api.py:49-64`; `strata_control/tune_api.py:80-89`）。候補 JSON はシステムの一時領域に一時ファイルとして作成されます（`strata_control/tune_api.py:275-283`）。

設定内の `exe`、`args` 等を含む run configuration の実際の妥当性は worker 側の読み込み・起動処理に委ねられます。`strata tune run` 自身は `--config` の内容を CLI parser で検証しません。`protocol` mode では API worker を起動しません。

## 出力とエラー

- `--mode api` で `--config` を省略した場合、stderr に `strata: --mode api needs --config: ...` を出し、終了コード 2 を返します。JSON 出力時はエラー JSON にします（`strata_cli/cli.py:1771-1776`; `strata_cli/cli.py:527-533`）。
- `--api-expect` の省略も同様に終了コード 2 です（`strata_cli/cli.py:1777-1779`）。
- worker が起動できない、準備完了前に終了する、または boot timeout に達する場合は計測エラーになります。API リクエストの拒否・通信エラー・応答が空・期待正規表現に不一致の場合もその候補は有効な計測になりません（`strata_control/tune_api.py:80-104`; `strata_control/tune_api.py:205-226`）。Tuner は計測例外を候補の失敗理由として記録します（`strata_control/tuning.py:486-509`）。
- 指定ファイルが読めない、または JSON として不正な場合、読み込み箇所は `Path.read_text` / `json.loads` で例外になります。CLI 側でこれを `--config` 固有の整形済み validation error に変換する処理は確認できません（`strata_control/tune_api.py:269-274`）。
- 人間向け出力では job 状態、失敗候補、測定 mode が報告されます。JSON 出力では job 結果を返します。tuning の結果適用は別の `strata tune apply` 操作であり、`tune run` は profile を変更しません（`strata_cli/cli.py:1805-1846`）。

## 根拠

- parser、既定値、help、mode 分岐: `strata_cli/cli.py:414-459`, `strata_cli/cli.py:1742-1786`
- API worker 起動引数、ライフサイクル、ログ: `strata_control/tune_api.py:41-141`
- API 測定の候補 JSON コピーと後片付け: `strata_control/tune_api.py:259-294`
- HTTP エラー、空応答、期待値チェック: `strata_control/tune_api.py:146-256`
- 測定エラーの候補への記録: `strata_control/tuning.py:486-509`
- tuning を profile 適用と分離する出力: `strata_cli/cli.py:1839-1846`

調査範囲は上記 checkout のソースです。CLI `--help` の実行、Release 配布物の照合、ビルド、テスト、GPU 実行は行っていません。
