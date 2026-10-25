# `strata runtime cleanup`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime cleanup` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/runtime.py`、`strata_control/procs.py` |
| option | `--profile`、`--output`、共通 one-shot option の `--json`、`--quiet`、`--help`（alias: `-h`） |

## 役割

Strata が起動したサーバーや engine のうち、起動元プロセスが終了して残ったものを記録と照合して終了します。親プロセスがまだ同じプロセスとして存在するものは orphan ではないため対象にせず、稼働中の managed instance は終了しません。PID だけを根拠に別プロセスを終了しないよう、記録された PID・開始時刻・command line を照合します。

## 使い方

```sh
# 全 profile の記録済み orphan を調べて終了
strata runtime cleanup

# 一つの profile に絞り、JSON で結果を受け取る
strata runtime cleanup --profile my-service --json

# 全体を走査し、機械可読 JSON を出力
strata runtime cleanup --output json
```

このコマンドは実際に対象プロセスを終了する操作です。確認用の `--plan` はありません。`--profile` を付けない場合は全 profile の process record を走査します。付けた場合は記録をその profile 名で絞り、さらに owner host が失われた場合の stale runtime 状態回収を試みます。

## 実行モードと主な動作

1. `strata runtime cleanup` は `strata_control.runtime.cleanup(profile)` を呼びます。
2. `strata_control.procs` は private process records を列挙し、記録されたプロセスがまだ同じ開始時刻・command line のものか、記録上の親が終了しているかを調べます。生存する親があるプロセスは残します。PID が再利用されていたり記録と command line が異なる場合、そのプロセスには触れず、該当する stale record を削除します。
3. 照合できた leftover は子から順に終了します。POSIX では `SIGTERM` 後に最大8秒待ち、残っていれば `SIGKILL` を送り、最大10秒確認します。Windows では照合後に対象 PID への `taskkill /F` を実行します。
4. `--profile NAME` のとき、同 profile の runtime state が残り owner lease が非アクティブなら、child が終了したことなどを再確認したうえで ready file、socket（POSIX）、rollback snapshot、owner marker、state file の回収を試みます。live owner lease があればこの回収はしません。

## オプションと出力

- `--profile NAME` は対象を一つの profile の leftover に限定します。値の形式は小文字 `a-z` で始まり、小文字英字・数字・`_`・`-` を続ける最大64文字です。profile 設定ファイルの存在自体はこの名前検証では確認しません。
- `--output human|json` は出力形式で、省略時は `human` です。`--json` は one-shot command 共通の alias で、`--output json` と同じ設定になります。
- `--quiet` は one-shot command 共通 option です。人向けの標準出力を抑え、失敗時に捕捉した出力があれば標準エラーへ出します。JSON 出力時は JSON を出す経路が優先されます。
- `--help` / `-h` は argparse が生成するこの command の usage と説明を表示します。

人向け出力は終了した件数と、終了できなかった件数・識別できず放置した件数（該当時）を表示します。JSON 出力には `schema_version: 1` と処理結果（`ok`、`state`、`ended`、`gone`、`stuck`、`unverifiable`、`exit_code` など）が含まれます。

## 注意点と失敗経路

- command line を読み取れずプロセス identity を確定できないものは終了せず、`unverifiable` として報告します。依然として稼働中の対象は `stuck` に入り、いずれかがあれば結果は `ok: false`、終了コードは `6` です。
- `--profile` の値が名前規則に合わない場合は `ProfileError` となります。通常の CLI error handler がエラーを表示し、指定された `exit_code`（名前検証では既定の `2`）で終了します。JSON mode では error handler が JSON error を出します。
- private runtime state が不正・読取不能、失われた owner の child がまだ存在する、または所有を安全に確認できない場合、stale state 回収は `ProfileError` などで失敗し得ます。`cleanup()` は profile-scoped 回収時の `ProfileError` と `FileNotFoundError` を握りつぶすため、回収失敗は必ずしも通常の cleanup 結果に個別フィールドとして現れるわけではありません。
- cleanup が扱うのは Strata の process record で確認できる範囲です。記録されていない旧バージョンの engine orphan をこのコマンドが一括探索するとはソースから確認できません（旧 engine の限定 orphan 検出は engine 起動前の別経路です）。

## 関連文書

- [CLI オプション索引](../../../README.md) — `strata-terminal` の command と option 文書一覧。
- [`strata runtime`](../README.md) — サブコマンド全体の概要。
- [`runtime start`](../start/README.md)、[`runtime stop`](../stop/README.md) — 関連する lifecycle command（索引上の予定パス）。
- Strata [`docs/CLOSING.md`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/docs/CLOSING.md) — foreground/background runtime の停止と leftover の説明。

## 根拠

- Strata `strata_cli/cli.py:202-237,508-515` — runtime command 階層、cleanup parser、`--json` / `--quiet` の共通追加。
- Strata `strata_cli/cli.py:1331-1345,2158-2159,2166-2183,2223-2237` — cleanup の呼び出し、出力・終了コード、例外処理、JSON/quiet の扱い。
- Strata `strata_control/runtime.py:670-685` — profile 検証、leftover 終了、profile 指定時の stale state 回収と結果。
- Strata `strata_control/runtime.py:285-378` — owner lease 確認、失われた owner の child 確認、private runtime state の回収。
- Strata `strata_control/procs.py:253-291,294-342` — process record の絞り込み、親・開始時刻・command line の照合、終了方法と結果分類。
- Strata `strata_control/profiles.py:25,48-51` — profile 名の形式。
- Strata `docs/CLOSING.md:45-60` — leftover 検出経路と実行中 instance を触らないという利用上の説明。
- 索引 `docs/cli/README.md:441-449` — `runtime cleanup` の command 概要リンクと予定される option 文書。

調査範囲は上記 commit の checkout 内の parser と実装、および同 checkout の `docs/CLOSING.md` です。OS ごとの実機動作・Release 配布物はこの調査では検証していません。
