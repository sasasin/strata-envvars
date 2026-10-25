# `--load-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--load-timeout` |
| 別名 | なし |
| 値 | 秒数（浮動小数点数）。1 以上 86400 以下 |

## 役割

標準ベンチマークスイートで profile のエンジンを起動した場合、モデルが ready になるまで待つ上限時間を指定します。モデルのロード時間はベンチマーク計測時間に含まれません（`strata_cli/bench_standard.py:673-686`）。

## 使い方

```sh
strata bench run --suite standard-v1 --profile <profile> --load-timeout 3600
```

`--load-timeout` は標準スイート用の引数グループに定義されています（`strata_cli/cli.py:315-321`）。

## 値と既定値

- `SECONDS` は `float` として解析され、既定値は `1800` 秒（30 分）です。短縮別名はありません（`strata_cli/cli.py:320-321`）。
- 標準スイートでは 1〜86400 秒の範囲のみ有効です。範囲外はエラー終了します（`strata_cli/cli.py:1251-1252`）。数値として解釈できない値は `argparse` が拒否します。
- 同じオプションを複数回指定した場合の専用処理はありません。parser は通常の `add_argument`（`store`）を使うため、最後に指定した値が使われます（`strata_cli/cli.py:320`）。

## 実行時の動作

標準スイートでは、`--profile` の指定先に 5 秒の health check を行います。すでに応答するサーバーがある場合はそれを使い、そのサーバーを停止しません。この経路では `--load-timeout` は ready 待ちには使われません（`strata_cli/cli.py:1292-1302`）。

profile のサーバーが応答せず、かつ `--no-start` が指定されていない場合、CLI は一時ログ領域を作り、子プロセスとして `strata.py serve --profile <profile> --quiet` を起動します。`--load-timeout` は `/health` が Strata サービスかつ `loaded` 状態になるまでの待ち時間に適用されます。待機中は最大 5 秒の health request を行い、2 秒間隔で再確認します（`strata_cli/cli.py:1292-1299`、`strata_cli/bench_standard.py:658-670`、`673-686`）。

`--url` で接続する経路では profile 起動処理を通らないため、この値は待ち時間として使用されません。ただし範囲検証は標準スイートで常に実行されます（`strata_cli/cli.py:1251-1253`、`1256-1269`、`1292-1300`）。また serving 系スイートではこの標準スイート専用の設定経路に入らず、`--load-timeout` は適用されません（`strata_cli/cli.py:1187-1200`、`1237-1248`）。

## 適用条件と副作用

- `--no-start` を指定し、profile のアドレスに応答するサーバーがない場合は、エンジンを起動せずエラーになります。サーバーが既に応答していれば、既存サーバーを使います（`strata_cli/cli.py:1292-1302`）。
- 新規起動経路では子エンジンプロセスと一時ログ領域が作られます。ベンチマーク処理を抜ける際に、この実行が起動したプロセスを停止し、一時領域を削除します（`strata_cli/cli.py:1285-1287`、`1303-1310`、`strata_cli/bench_standard.py:673-695`、`706-768`）。既に稼働中のサーバーは停止対象になりません（`strata_cli/cli.py:1300-1301`）。
- 指定時間内に ready にならない場合、または起動プロセスが先に終了した場合は待機失敗となり、停止を試みます。health request 自体は最大 5 秒、再確認間隔は 2 秒なので、実際の復帰時刻は指定秒数を超えることがあります（`strata_cli/bench_standard.py:658-670`）。

## 出力とエラー

- 1〜86400 秒の範囲外は `--load-timeout must be 1..86400 seconds` を出し、終了コード 2 になります（`strata_cli/cli.py:1251-1252`、`527-532`）。
- `--no-start` で応答中のサーバーがない場合は `no server is answering at the profile's address and --no-start was given`、終了コード 5 です（`strata_cli/cli.py:1292-1294`）。
- 新規起動したエンジンが ready にならない場合、エンジンログ末尾（最大 600 文字）を含む `the engine did not become ready` エラーとなり、終了コード 6 です。エンジンを停止できなかった場合はポートを保持している可能性もエラーに加わります（`strata_cli/bench_standard.py:686-694`）。この `ProfileError` は `ValueError` として捕捉され、通常は stderr、`--output json` では JSON エラーとして出力されます（`strata_control/profiles.py:30`、`strata_cli/cli.py:2165-2176`、`527-532`）。

## 根拠

- parser 定義と既定値: `strata_cli/cli.py:315-321`
- 範囲検証と profile/URL 分岐: `strata_cli/cli.py:1246-1269`
- 待機・起動・`--no-start` の適用: `strata_cli/cli.py:1292-1302`
- health 待機条件、子プロセス起動、失敗処理: `strata_cli/bench_standard.py:658-695`
- 停止処理: `strata_cli/bench_standard.py:706-768`
- エラーの捕捉と出力: `strata_cli/cli.py:527-532`、`2165-2176`
