# `--plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False`、指定時は `True` |

## 役割

指定した profile の現在の owner と instance を確認し、stop の対象をレビューするためのフラグです。成功した計画には profile、state、owner ID、instance ID、profile revision と `would_drain: false` / `would_stop: false` が含まれます。このフラグ自体は drain や stop を実行しません。

## 使い方

```sh
strata runtime stop --profile local --plan
```

必要な `--profile` は保存済み profile 名です。計画結果に表示される owner ID と instance ID は、実際に停止する呼び出しへ `--if-owner-id` と `--if-instance-id` で渡して、レビュー後に対象が変わっていないことを確認できます。

## 値と既定値

`argparse` の `store_true` で、値は不要です。未指定なら通常の停止処理、指定時は plan 分岐へ進みます。重複して指定しても真偽値のままです。`--wait` は既定値 330 秒で、1〜600 秒の有限値に制限されます。plan 分岐でもこの値の validation は先に行われますが、待機時間自体は計画に使われません。

## 実行時の動作

`strata_cli/cli.py` は `--plan` を management 層へ渡します。stop 処理は `--if-owner-id` / `--if-instance-id` が一つでもある plan を拒否し、両方なしの場合に現在の runtime status を取得して計画を返します。現在 state が `ready`、`starting`、`failed` のいずれでも owner ID があれば計画可能です。owner がない、または状態がそれ以外なら `runtime_not_owned`、終了コード 6 になります。

成功時、CLI は plan 結果を `--output human` では整形 JSON、`--output json` では `schema_version` と `ok` を含む JSON で出力し、終了コード 0 を返します。`--json` は parser で `--output json` の alias として追加されます。

plan の取得は stop 用の実行 journal や stop RPC には進みません。ただし計画作成が `runtime.status` を呼び、その status が owner host に問い合わせます。ready file が見つかった直後で readiness probe がまだ始まっていない場合、owner host の status 処理はバックグラウンド probe を開始します。この probe は localhost telemetry を照合し、モデルが loaded と報告されると1 token の generation request も行います。したがって、計画は対象を停止しない一方、状態確認に伴う probe の通信・generation まで常に無作用とは限りません。

## 適用条件と副作用

- `--profile` は必須で、`runtime` の対象は owner host が管理するローカル Strata server instance です。
- `--if-owner-id` または `--if-instance-id` を `--plan` と併用すると `stop plan cannot include execution preconditions` で拒否されます。ID の値形式は32文字の小文字16進数です。
- plan 成功は後続 stop の成功を保証しません。計画後に owner / instance が変わってから実行時 ID を照合すると、`owner_changed_after_stop_plan` または `instance_changed_after_stop_plan` で拒否されます。
- 外部 Release の配布状態や Windows を含む実機挙動は、この checkout のソース調査では確認していません。

## 出力とエラー

owner がない場合や plan 対象 state でない場合は `runtime_not_owned` と終了コード 6 を返します。JSON 出力では失敗 payload を出し、human 出力では stop status 形式の行に state と error を表示します。profile 名不正、stop wait の範囲外、plan と実行前提 ID の併用など validation error は、通常 human では stderr の `strata: ...`、JSON では `error` object で返ります。必須 `--profile` の欠落や不正な引数構文は argparse が拒否します。

## 根拠

- parser、`--profile` 必須、`--plan` の型、`--wait` 既定値・関連 ID / 出力: `strata_cli/cli.py:226-232`
- plan 引数の management 呼び出し、plan 成功時の出力・終了コード: `strata_cli/cli.py:1331-1360`
- 秒数 validation と範囲: `strata_control/management.py:113-117`
- stop の plan 分岐、ID 併用拒否、実行前 ID の照合、journal と実 stop 呼び出し: `strata_control/management.py:271-291`
- ID validation: `strata_control/management.py:142-147`
- 現在状態の取得、plan 対象 state と返却 fields: `strata_control/runtime.py:602-611`
- status が owner host に問い合わせる経路: `strata_control/runtime.py:444-455`
- ready file の status 確認が readiness probe を開始する条件: `strata_control/runtime.py:933-957`
- probe による localhost telemetry と generation request: `strata_control/readiness.py:84-127`
- 実際の stop が owner host に SIGTERM（POSIX）または owner pipe EOF（Windows）を送り、期限切れ時に子プロセス tree を終了する経路: `strata_control/runtime.py:990-1012`
- human / JSON 成功出力と error 出力: `strata_cli/cli.py:527-542`
