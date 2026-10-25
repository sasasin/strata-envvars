# `strata tune run --request-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--request-timeout` |
| 別名 | なし |
| 値 | 秒数を表す浮動小数点数 |
| 既定値 | `600.0` 秒 |

## 役割

`--mode api` で候補を測定するとき、worker の HTTP API に送る各 completion request の待ち時間として使われます。候補 worker の起動待ち時間は別の `--boot-timeout` が制御します。既定の `--mode protocol` ではこの値は測定関数へ渡されません。

## 使い方

```sh
strata tune run --engine ./strata --backend cpu --model my-model \
  --mode api --config ./strata-my-model.json --api-expect 'hash table' \
  --request-timeout 900
```

`api` モードには `--config` と `--api-expect` も必要です。この例では HTTP request の timeout 引数を 900 秒にします。

## 値と既定値

- parser は `float` で値を変換し、省略時は `600.0` です。値なしや浮動小数点数に変換できない文字列は `argparse` が拒否します。
- CLI 側に正数・有限値・上限の明示的な validation はありません。重複指定時に独自の処理もなく、通常の `argparse` の格納規則で最後に指定した値が使われます。
- API harness はこの値を `urllib` の `urlopen(..., timeout=...)` に渡します。ゼロ・負数・非有限値を指定した場合の挙動は CLI で定義されておらず、下位の Python networking 実装での扱いに委ねられます。

## 実行時の動作

- `strata tune run` の既定モードは `protocol` です。`--mode api` のときだけ `_tune_run` が `a.request_timeout` を `make_api_measure` の `request_timeout_s` に渡し、各 `ApiHarness` が HTTP request の `urlopen` timeout 引数として使います。
- API harness は `/v1/chat/completions` に streaming completion を要求します。応答が終わるまで読み取り、answer と token usage を使って測定値を作ります。worker がエラーを返す、出力がない、期待 regex に合わない、completion token 数がない場合も測定エラーです。
- 一つの測定呼び出しごとに候補設定の worker を起動して一 request を測り、終了します。チューナーは候補ごとに warmup と指定回数の repeat を行うため、この timeout はそれぞれの request に適用されます。
- `protocol` モードでは `tune_engine.make_measure` が `EngineHarness` を作りますが、CLI の `a.request_timeout` を渡しません。したがって `--request-timeout` の指定値は protocol 測定には影響せず、`EngineHarness` の内部既定値 `600.0` 秒が使われます。

## 適用条件と副作用

- `--mode api` のみで有効です。API モードは候補ごとの worker 子プロセスを起動し、loopback HTTP 接続を行います。worker は completion 測定後に停止されます。
- `--mode api` で `--config` または `--api-expect` がない場合、CLI は worker を起動する前にエラー（終了コード 2）を返します。これは timeout 値自体の validation ではありません。
- API の設定ファイルは候補用の一時コピーとして作られ、測定終了時に削除が試みられます。timeout 値は worker の boot deadline やチューニング全体の `--time` 上限を変更しません。

## 出力とエラー

- `urlopen` が `HTTPError` を返すと HTTP status と応答本文の一部を含む測定エラーになります。`URLError` または `OSError` は request failure として測定エラーになり、worker log の末尾が付く場合があります。
- チューナーは測定例外を候補の status と reason に記録します。例外文に `timeout` / `timed out` が含まれる warmup では `TIMEOUT`、repeat 中に `timeout` が含まれる場合も `TIMEOUT`、それ以外は `UNMEASURED` になります。reason は最大 400 文字です。基準測定が失敗すると探索を行わず、その理由を job 記録へ残します。
- CLI は完了後に job の状態と失敗候補を human 出力へ表示します。JSON 出力では job object を返します。個別 request timeout を設定したこと自体を示す専用メッセージはありません。

## 根拠

- `strata_cli/cli.py:414-459` — `tune run` parser、`--mode` の既定値、`--request-timeout` の `float` 型・既定値。
- `strata_cli/cli.py:1742-1786` — `--mode api` の前提条件、API harness への timeout 引き渡し、および protocol モードへの分岐。
- `strata_control/tune_api.py:41-64,146-177` — API harness が受け取る timeout と HTTP request への適用。
- `strata_control/tune_api.py:205-232,259-292` — HTTP/network 失敗と測定エラー、候補 worker・一時設定ファイルの lifecycle。
- `strata_control/tune_engine.py:396-409,501-550,596-610` — protocol harness の独立した `600.0` 秒既定値と CLI 指定値が `make_measure` に渡らない経路。
- `strata_control/tuning.py:423-482,486-523` — baseline・候補の warmup/repeat、例外の記録と status 分類。
- `strata_cli/cli.py:1802-1845` — job 実行後の human / JSON 出力。

## 調査範囲

調査は記載した checkout のソースに基づきます。CLI help や Release 配布物は別途照合していません。数値の境界値に対する挙動は CLI の明示 validation までを確認し、下位 Python networking 実装の詳細には踏み込みません。
