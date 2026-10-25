# `strata tune run --trials`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。checkout は `main...origin/main` で、調査時点の `git status --short --branch` に未コミット変更はありませんでした。

## 概要

`strata tune run` が評価する候補設定の最大数を指定します。候補グリッドの先頭から決定的な順序で評価し、上限までで探索を止めます。省略時は `16` です。

```sh
strata tune run --engine /path/to/strata --backend metal --model q2_0 --trials 4
```

このコマンドは実際にエンジンを起動して測定します。例のパスや backend、model は利用環境に合わせてください。

## 値と検証

- 値は整数です。parser は `type=int` で読み取り、既定値は `16` です。整数でない値は argparse が引数エラーとして扱います。
- 0 や負数も parser 自体では拒否されません。計画作成時に `max(0, int(max_trials))` で 0 へ丸められます。その場合、候補設定は測定しませんが、正常なベースライン測定は行われ、成功時には最後のベースライン再測定も行われます。
- 上限は候補設定数に対するものです。ベースラインと最後の再測定は `trials_run` に数えられず、候補数の上限にも含まれません。

## 動作と相互作用

`--trials` は `plan_tuning()` に渡され、利用可能な backend/engine の次元から作る候補数に上限を設けます。グリッド全体より小さい場合は列挙順の先頭部分だけを測定します。`--hold` で次元を固定する、または engine に対応する探索次元がない場合はグリッド自体が小さくなるため、指定上限まで実行されるとは限りません。

`--time` も探索を止める境界です。ベースラインの後、候補を開始する前に経過時間を確認するため、時間切れなら候補数が `--trials` より少なくなります。ベースラインや候補1件の測定時間そのものを強制終了する指定ではありません。`--repeats` は各候補の測定回数を決める別の指定で、`--trials` が上限となるのは候補設定の数です。

測定結果には実測した候補数とグリッド全体の組み合わせ数が記録されます。探索が全グリッド未満なら human 出力は「prefix（列挙の先頭部分）」と明示します。測定不能・起動失敗・タイムアウト・トークン未生成・正当性チェック失敗の候補も失敗として記録され、選定対象から外れます。ベースラインが失敗すると候補探索を行いません。

## 副作用、出力、失敗

- 実行は engine のベースラインおよび候補設定を起動・測定します。job ごとの状態・イベント・候補・レポートを `job.json` に保存し、測定履歴も記録します。通常の状態保存先は `--state-dir`、環境変数 `STRATA_TUNE_DIR`、または既定の tuning ディレクトリから決まります。
- `--trials` 自体は設定ファイルを変更しません。測定で得た推奨設定を適用する操作は別コマンド `strata tune apply <job>` です。
- 既定の human 出力は job の状態、ベースライン、実施候補数、失敗、推奨を表示します。`--output json` では job 結果を JSON で返します。job の実行エラーも状態記録に残して返されます。
- engine ファイルが見つからない場合は `strata_cli/cli.py` の事前確認でエラー（終了コード 2）になります。実行中に測定や排他 lease の取得で例外が起きた場合は、Tuner が job を `failed` として保存し、lease を解放します。候補の測定失敗は個々の候補に記録され、job 全体を直ちに失敗扱いにはしません。

## 根拠

- `strata_cli/cli.py:414-423` — `tune run` parser、`--trials` の整数型と既定値。
- `strata_cli/cli.py:1708-1709, 1742-1768` — `run` 分岐、engine の存在確認、値を計画へ渡す箇所。
- `strata_control/tuning.py:723-768` — 次元・held dimension の計画化、0 以上への丸め、時間・repeats の計画値。
- `strata_control/tuning.py:423-484` — ベースライン、候補数・時間境界、ベースライン再測定、状態保存、例外時の failed 記録と lease 解放。
- `strata_control/tuning.py:486-555` — 候補の失敗分類と決定的なグリッド列挙。
- `strata_control/tuning.py:640-670` — レポートの候補数・全組み合わせ数・prefix 表示用データ。
- `strata_cli/cli.py:1813-1847` — CLI の測定数、失敗、推奨、出力と別途 apply する旨。
- `strata_cli/cli.py:1643-1650` — tuning job の保存先選択。
- `strata_control/tuning.py:304-362, 389-419` — job ディレクトリ・`job.json`・排他 lease の作成と保存。

`strata_cli/cli.py:1637-1638` の `_tune` docstring には run が未公開であるかのような古い記述がありますが、同ファイルの parser 定義（414-423 行）と `run` の dispatch（1708-1709 行）が現行実装を示しています。索引の `strata tune run` とも一致します。

調査は上記 revision のソースコードに限定しました。実機測定、GPU 実行、build、テスト、および Release 配布バイナリとの比較は行っていません。
