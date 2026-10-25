# `strata runtime stop`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/management.py`、`strata_control/runtime.py` |

## 役割

保存済み profile で `strata runtime start` が起動した、ローカル管理対象の Strata server を停止します。server に停止要求を送り、推論中の処理を drain してから終了させます。引数の `--profile` は保存済み profile 名で、ファイルパスではありません。

このコマンドは `strata serve` の foreground server を停止するコマンドではありません。runtime の `start` は owner host が管理するバックグラウンド service を起動し、`stop` がその対応する停止操作です。

## 代表的な使い方

```sh
# 停止対象の owner と instance を確認する。これは停止しない
strata runtime stop --profile office --plan

# profile office の管理対象 server を停止する
strata runtime stop --profile office

# plan で確認した owner/instance に限定して停止する
strata runtime stop --profile office --if-owner-id OWNER_ID --if-instance-id INSTANCE_ID
```

`OWNER_ID` と `INSTANCE_ID` は `--plan` が返す実際の値に置き換えます。索引上、このコマンドには `--profile`、`--plan`、`--wait`、`--if-owner-id`、`--if-instance-id`、`--output` とその alias `--json`、`--quiet`、`--help` が属します。詳細は [runtime stop のオプション一覧](../../../README.md) を参照してください。

## 実行モードと主な動作

- **plan**: 現在の状態を調べ、対象 profile、状態、owner ID、instance ID、profile revision、および `would_drain` / `would_stop` が false の計画を返します。停止要求は送りません。管理対象の ready / starting / failed 状態と owner ID がない場合は `runtime_not_owned` として失敗します。
- **stop**: profile と任意の owner / instance ID を検証し、`runtime.stop` 操作を journal に記録してから owner host に停止 RPC を送ります。owner host は記録した server child を停止し、成功時に ready file を削除して stopped 状態を返します。
- **owner host が既に終了している場合**: 通常 RPC ができないため、Strata が記録した server / engine の残存プロセスを PID、開始時刻、コマンドラインで再確認して終了させ、古い状態を回収する経路があります。照合できない、または終了できないプロセスがあると失敗になります。

通常の停止で待つ秒数は `--wait` で指定します。stop の待機時間は 1〜600 秒として検証され、既定値は 330 秒です。owner host は server をこの時間待った後、終了期限を超えた child を強制終了し、`server_stop_deadline_expired` として失敗を返す場合があります。

人間向け出力では profile 名、状態、利用可能な instance ID / API URL、launch 検証状態、エラーを表示します。`--output json` または `--json` は JSON 結果を stdout に出し、`--quiet` は通常の人間向け出力を抑制します。JSON 出力は quiet より優先されます。

## 注意点

- `--plan` と `--if-owner-id` / `--if-instance-id` は併用できません。plan で確認した対象に限定する場合は、plan と実停止を別々に実行してください。指定 ID が現在の owner / instance と異なれば、変更後の対象を誤って止めないよう停止要求を拒否します。
- `--if-owner-id` と `--if-instance-id` はそれぞれ 32 文字の小文字 hexadecimal ID として検証されます。profile は保存済み profile 名の形式でなければなりません。
- 管理対象外の任意プロセスを探して停止する機能ではありません。owner host の喪失後に残存プロセスを扱う場合も、Strata が記録したプロセスを照合する仕組みです。
- 対象ソースでは POSIX と Windows の停止経路が実装されていますが、この調査では CLI を実行して各 OS の挙動を確認していません。Release 配布物との比較も行っていません。

関連ページ: [`strata runtime`](../README.md)、[`strata runtime start`](../start/README.md)、[CLI 文書索引](../../../README.md)。

## 根拠

- `strata_cli/cli.py:197-205,226-232` — runtime の役割説明と stop parser の引数、必須 profile、plan / wait 既定値。
- `strata_cli/cli.py:508-515` — runtime stop parser 群に `--json` と `--quiet` を追加する共通処理。
- `strata_cli/cli.py:1331-1373` — stop 結果の plan / JSON / human 出力と終了コードの返却。
- `strata_control/management.py:188-198,271-291` — profile / plan / ID / wait の検証、plan 分岐、journal 記録、runtime stop 呼び出し。
- `strata_control/runtime.py:602-611` — plan が確認する状態と、停止を実行しないこと。
- `strata_control/runtime.py:614-667` — stop の待ち時間・ID validation、owner RPC、owner 喪失時の残存プロセス回収と失敗条件。
- `strata_control/runtime.py:990-1012,1209-1224` — owner host が管理する child の停止要求、期限超過時の強制終了、ready file 削除、owner / instance の照合。
