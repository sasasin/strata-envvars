# `strata update --force`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。未指定時は `false`、指定時は `true`。 |

## 役割

前回 test-start に失敗した engine、または `strata components rollback` で戻した engine バージョンを、更新候補として再試行できるようにします。失敗記録があっても engine の更新処理へ進め、package の検証と test-start を行います。インストール済み engine の検証を省略するフラグではありません。

## 使い方

```sh
strata update --force
```

更新前に候補だけを確認する場合は `strata update --force --check` を使えます。この場合、force により抑止されていた engine 候補も報告に現れますが、engine のダウンロードや切り替えは行いません。

## 値と既定値

値は不要です。parser は `action="store_true"` を使い、既定値は `false` です。値を後置する形式は定義されていません（`strata_cli/update_cmd.py:30-39`）。

## 実行時の動作

- CLI はこの値を updater の `Context.force` に渡します（`strata_cli/update_cmd.py:174-184`）。
- engine 候補が現在より新しい場合、force が未指定だと、同じ manifest の候補が過去に test-start で失敗していると `failed-before` に、rollback 済みの候補なら `skipped` にして通常更新の対象から外します。force を指定すると、この抑止判定を通らず通常の `available` 候補として扱います（`strata_control/updater.py:595-614`）。失敗記録は24時間経過すると通常判定でも古いものとして無視されます（`strata_control/updater.py:1135-1142`）。
- 実際の更新では、force により `failed-before` / `skipped` の候補も engine 更新処理へ進めます（`strata_control/updater.py:926-937`）。候補が古い、同じ、適合する package がない、または GPU make guard に拒否された場合などを強制的に更新するものではありません（`strata_control/updater.py:539-563,581-614`）。
- force を指定しても、feed の署名・sequence 検査、取得物の hash と manifest の検証、engine の署名・全ファイル検査、staging 上での test-start は通常どおり行われます。test-start が成功した後にのみ live engine を切り替えます（`strata_control/updater.py:355-366,656-690,926-1009`）。
- `--check` は決定結果を表示して終了し、更新処理には進みません（`strata_cli/update_cmd.py:203-209`）。check の実装は feed と候補状態を調べ、`last_check` を state に保存します（`strata_control/updater.py:624-640`）。
- `strata components update` も同じ `_common` parser と updater を使うため、force の意味は同じです（`strata_cli/update_cmd.py:42-56,163-184`）。一方 `strata components rollback --force` も共通 parser によって受理されますが、rollback の処理は `Context.force` を参照せず、直前に戻す操作を行います（`strata_cli/update_cmd.py:57-59,185-196`、`strata_control/updater.py:1033-1078`）。

## 適用条件と副作用

force が解除するのは engine 更新候補の `failed-before` / `skipped` 抑止だけです。前者は busy 判定ではない test-start 失敗の記録があり、その manifest SHA-256 が今回の候補と一致する場合に限り適用されます（`strata_control/updater.py:967-975`）。後者は rollback で記録された version が今回の候補と一致する場合に適用されます（`strata_control/updater.py:603-614,1067-1070`）。

再試行時には通常の更新副作用が発生します。feed・engine archive のネットワーク取得、component folder 内の staging と update state の書き込み、test-start 用の隔離 runtime とログの作成、成功時の engine 切り替えがあり得ます。既存 engine は test-start 成功まで切り替えられず、以前の version は rollback 用に保持されます（`strata_control/updater.py:6-21,470-493,842-895,926-1030`）。force は serving 中の拒否・待機条件、署名・hash 検証、package 適合性検査を回避しません（`strata_control/updater.py:300-310,355-366,656-690,926-947`）。

Control 更新と desktop app installer の判定には `Context.force` を使う箇所がなく、このフラグによる再試行解除の対象ではありません（`strata_control/updater.py:1145-1152,1210-1240,1274-1295`）。

## 出力とエラー

候補が force で再試行され、test-start が失敗した場合も更新は拒否され、現行 engine は切り替わりません。通常の human 出力では失敗理由を stderr に `strata: ...` として出し、JSON/JSONL mode ではエラー object を stdout に出力します。終了コードは test-start / network 等の失敗で `6`、serving 中などの Busy で `7`、署名・hash 等の拒否で `5` です（`strata_cli/update_cmd.py:163-172,225-234`、`strata_control/updater.py:54-59,65-76,79-123,470-493`）。

## 根拠

- `strata_cli/update_cmd.py:30-39,42-59` — 共通 parser の宣言、値を取らない設定、`update` / `components update` / `components rollback` への登録。
- `strata_cli/update_cmd.py:163-184,203-224` — CLI 値から `Context.force` への受け渡し、check と更新の分岐、結果出力。
- `strata_control/updater.py:522-524,566-614,926-937,967-975` — engine 候補の保留判定、force 時に再試行処理へ進む条件、test-start 失敗記録。
- `strata_control/updater.py:355-366,656-690,926-1030` — feed・package 検証、test-start、切り替えと失敗時の扱い。
- `strata_control/updater.py:1033-1078` — rollback 処理が force を使わないこと、および rollback 済み version の記録。
- `strata_control/updater.py:1135-1142,1145-1152,1274-1297` — 失敗記録の有効期間、Control 更新、全更新処理。

## 調査範囲

ソース checkout の parser と実装を調査しました。別途インストールされた CLI や Release artifact の動作確認は行っていません。記載内容は上記 commit のソースに基づきます。
