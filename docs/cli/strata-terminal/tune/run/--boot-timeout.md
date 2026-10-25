# `strata tune run --boot-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--boot-timeout` |
| 別名 | なし |
| 値 | 秒数を表す浮動小数点数 |
| 既定値 | `600.0` 秒 |

## 役割

`--mode api` でチューニング候補の設定を使った worker を起動するとき、worker が準備完了になるまで待つ上限時間を指定します。既定の `--mode protocol` はエンジン独自の serve protocol を測定し、この値を API 測定関数へ渡しません。

## 使い方

```sh
strata tune run --engine ./strata --backend cpu --model my-model \
  --mode api --config ./strata-my-model.json --api-expect 'hash table' \
  --boot-timeout 900
```

`api` モードでは `--config` と `--api-expect` も必要です。例では worker の起動待ち上限を 900 秒にします。

## 値と既定値

- parser は Python の `float` で値を変換し、省略時は `600.0` を使います。明示値に対する正の値・有限値などの範囲 validation はありません。
- `0` や負数も parser では受理されますが、期限が直ちに到来するため、health 応答を待たず起動失敗になります。
- 値は秒単位で、API モードで起動する各 worker の準備待ちに個別に使われます。チューニング全体の所要時間上限ではありません。

## 実行時の動作

`strata tune run` の parser は `--boot-timeout` を `a.boot_timeout` に格納します。`_tune_run` は `--mode api` の場合に `--config` と `--api-expect` の有無を確認し、値を `make_api_measure` の `boot_timeout_s` に渡します。`protocol` モードでは `make_measure` を使うため、この引数は使われません。

API 測定では候補ごとの設定ファイル一時コピーから worker を子プロセスとして起動し、loopback の `/health` が HTTP 200 を返すまでポーリングします。期限内に応答がなければ測定エラーになります。チューナーは測定例外を候補の失敗状態・理由として記録し、その候補を測定値・推薦の対象から外します。基準測定が失敗した場合は候補探索をせず、基準測定失敗として記録します。

## 適用条件と副作用

- `--mode api` のときだけ適用されます。`--mode` の既定値は `protocol` です。
- `--mode api` では `--config` と `--api-expect` がないと、worker を起動する前に CLI エラー（終了コード 2）になります。
- API 測定ごとに worker プロセスが起動・終了します。候補設定の JSON は一時ファイルに書かれ、測定終了時に削除が試みられます。worker の標準出力と標準エラーは削除指定なしの一時ログへまとめられ、harness はファイルを閉じますが削除しません。
- `ApiHarness.close()` は worker が動作中なら terminate し、20 秒で終了しない場合 kill します。起動失敗時も `make_api_measure` の `finally` で close と設定一時ファイル削除を試みます。

## 出力とエラー

- worker が準備完了前に終了すると、終了コードとログ末尾を含む測定エラーになります。期限内に `/health` が応答しない場合は、指定秒数とログ末尾を含む測定エラーになります。
- チューナーは測定例外の理由を最大 400 文字まで候補に記録します。`/health` の期限切れメッセージには `timeout` という語が含まれないため、この経路は `TIMEOUT` ではなく `UNMEASURED` として記録されます。タイムアウトや起動失敗で候補の探索全体を直ちに中断するとは限らず、基準測定の成功後に発生した候補失敗はその候補の結果として扱われます。
- CLI の出力形式は `--output human`（既定）または `--output json` です。API モードの `--config` / `--api-expect` 不足は human では標準エラー、JSON 出力では JSON エラーとして出力されます。

## 根拠

- `strata_cli/cli.py:414-459` — `tune run` parser、`--mode` の既定値、API 関連引数と `--boot-timeout` の型・既定値。
- `strata_cli/cli.py:1742-1787` — engine の存在確認、API モードの必須引数検査、`boot_timeout_s` の引き渡しと protocol モードとの分岐。
- `strata_cli/cli.py:527-532` — CLI エラーの標準エラー/JSON 出力と終了コード。
- `strata_control/tune_api.py:41-64,80-104` — API harness の保持値、worker 起動、`/health` readiness 待ちと失敗経路。
- `strata_control/tune_api.py:123-135,259-292` — worker の停止・kill、候補設定一時ファイルとログの扱い。
- `strata_control/tuning.py:423-482,486-523,640-663` — baseline・候補ごとの測定、例外の候補状態への記録、失敗候補の報告。
