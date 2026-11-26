# `strata components rollback --wait`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数。Python の `float` として解析 |

## 役割

rollback の前に Strata エンジンが使用中なら、指定秒数を上限としてアイドルになるまで待つ。待機中は、以前のエンジンへの切り替えを行わない。rollback の対象は `engine` 状態に記録された前のエンジンで、ダウンロードは行わない。

## 使い方

```sh
# 使用中のエンジンが止まるまで最大30秒待ってから rollback
strata components rollback --wait 30
```

## 値と既定値

- 値は必須で、`float` に変換できない文字列や値の省略は `argparse` の引数エラーになる（終了コード 2）。
- 省略時は parser の値が `None`、実行時の待ち時間は `0` 秒。
- parser は浮動小数点数の有限性・正値・上限を validation しない。待機処理では `wait <= 0` の場合、エンジンが使用中なら直ちに Busy として失敗する。正の値では、アイドルになるか指定時間を過ぎるまで最大3秒間隔で確認する。
- `--wait 0` も指定なしと同様に扱われる。エンジン使用中で対話端末なら確認が表示され、`y` / `yes` で最大6時間待つ設定になる。その他の回答では待たずに Busy となる。

## 実行時の動作

`--wait` は `strata components update` などと共通の parser helper で登録されるが、この文書の対象は `components rollback` スコープである。rollback 分岐は引数値を `Context.wait` に渡し、対話時の確認を経て `rollback_engine` を呼び出す。正の秒数が指定されていると確認プロンプトは省略され、下位処理が `serving_now` を確認する。待機中は `waiting` イベントを出し、3秒間隔で再確認する。

エンジンが使用中でない場合、待機時間は実質的に使われない。停止までに指定時間を超える、または待機時間が0以下の状態で使用中なら Busy 例外となり、終了コード7で切り替えを行わない。Strata 自身の `launch-*` プロファイルが使用中の場合は、対話確認で待つ選択肢を出さず、停止を促す Busy エラーになる。

## 適用条件と副作用

- 使用中エンジンの検出後、rollback 側でも idle gate が実行されるため、確認と実際の切り替えの直前に状態を再確認する。
- 使用中状態の確認では、停止済みホストの stale な記録を回復・除去する経路がある。共有 activity lease も一時取得して状態を確認する。
- 正の `--wait` は待機時間だけを制御し、停止中のモデルを停止させるオプションではない。
- 成功時には以前のエンジンを検証してから切り替える。変更処理ではエンジン選択状態や履歴を保存し、チューニング preset を再確認対象としてマークする場合がある。`--wait` 自体はファイルやエンジンを変更しない。

## 出力とエラー

- 人間向け出力では待機中に進捗メッセージが出る。`--output jsonl` では待機イベントが JSONL で出力される。
- 待ち時間の超過または即時拒否では Busy エラー（終了コード7）。人間向けでは stderr に `strata: ...` が出て、`json` / `jsonl` では stdout にエラー JSON が出力される。
- parser が値を `float` に変換できない場合は引数エラー（終了コード2）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser での `--wait` 定義、型、既定値、metavar。
- `terminal/strata_cli/update_cmd.py:80-81` — rollback parser への共通オプション登録。
- `terminal/strata_cli/update_cmd.py:307-329` — `Context.wait` の設定、rollback 時の対話判定と実行。
- `terminal/strata_cli/update_cmd.py:504-519` — 端末・machine output・`launch-*` による確認条件と、肯定時の6時間待機設定。
- `terminal/strata_control/updater.py:383-403` — 秒数を使った idle polling、3秒周期、Busy 判定。
- `terminal/strata_control/updater.py:354-379` — serving 状態確認時の stale 記録回復と activity lease の確認。
- `terminal/strata_control/updater.py:72-83` — Busy エラーの内容と終了コード7。
- `terminal/strata_control/updater.py:1776-1798` — rollback の前状態取得、待機、前エンジン検証、切り替え。
- `terminal/strata_control/updater.py:1723-1773` — エンジン状態・履歴の保存と preset mark の処理。
- `terminal/strata_cli/update_cmd.py:311-316` — human と machine-readable 出力での失敗表示。
