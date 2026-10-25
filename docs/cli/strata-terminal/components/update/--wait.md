# `--wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | `SECONDS`。`float` として解釈される秒数。parser に範囲 validation はない |

## 役割

エンジンが稼働中の場合に、停止するまで指定秒数を目安に待ってから更新・rollback を続けます。待機時間を過ぎても稼働中なら Busy エラーになります。3 秒間隔で再確認するため、終了判定が指定時間を最大で polling 間隔分ほど過ぎる場合があります。`strata components update` では更新時のエンジン交換前、`strata components rollback` では rollback 処理中に同じ設定が使われます。

## 使い方

```sh
strata components update --wait 900
```

この例は更新処理で稼働中エンジンが停止するのを最大 900 秒待つ指定です。実際の更新では署名済み feed からの取得等も行われます。

## 値と既定値

`--wait` は `argparse` の `type=float` で値を変換し、既定値は `None` です。`update_cmd.run` は `a.wait or 0.0` を `updater.Context.wait` に渡すため、未指定または `0` は待機時間 0 秒として扱われます（`strata_control/updater.py:317-327`、`strata_cli/update_cmd.py:34-35, 182-184`）。負数も parser では拒否されず、待機処理では `wait <= 0` として直ちに Busy になります（`strata_control/updater.py:300-307`）。上限・有限値の validation は確認できませんでした。

未指定または `--wait 0` の場合、通常の対話端末では、別の Strata engine/server が稼働していれば「待って更新するか」を尋ねます。`y` / `yes` なら `ctx.wait` を 6 時間に設定します。`--wait` に正の値を指定するとこの確認は行わず、その秒数を処理へ渡します（`strata_cli/update_cmd.py:237-252`）。

## 実行時の動作

`strata components update` の parser は `--wait` を共通 option として登録し、`strata update` と `strata components rollback` にも同じ定義を使います（`strata_cli/update_cmd.py:30-39, 42-59`）。`strata components update` は `strata_cli/update_cmd.run` に振り分けられます（`strata_cli/cli.py:139-140, 2135-2137`）。

更新では engine パッケージを取得した後、交換前に稼働状態を確認します。稼働中なら「更新前に停止するまで待つ」イベントを出し、3 秒間隔で再確認します。指定秒数経過後も稼働中なら `Busy` を送出します。engine のテスト起動後にも交換直前の再確認があります（`strata_control/updater.py:300-311, 938-978`）。このため、engine 更新時の待機時間計測は、更新コマンド開始時ではなく、この確認箇所に到達した時点からです。

通常の `components update` では、未指定かつ対話端末の場合、一般の稼働 engine/server に対して更新前に確認を促します。JSON/JSONL 出力または非対話 stdin では確認せず、稼働中なら更新処理が Busy で終了します。Strata 自身の `launch-` profile が稼働中の場合は対話確認を出さず、停止方法を案内する Busy エラーになります（`strata_cli/update_cmd.py:237-252`、`strata_control/updater.py:65-76`）。`--check` は feed の確認結果を返して終了し、`_maybe_wait` を呼ばないため、待機しません。結果に稼働状態が含まれる場合、人間向け出力には稼働中である旨が表示されます（`strata_cli/update_cmd.py:203-209, 132-160`）。

`strata components rollback` も同じ `--wait` 値を使い、rollback 前に稼働状態を確認します（`strata_cli/update_cmd.py:185-196`、`strata_control/updater.py:1033-1044`）。

## 適用条件と副作用

待機判定は管理対象 runtime の active instances と共有 activity lease を使う Strata server を対象にします（`strata_control/updater.py:275-297`）。この option は停止を要求・強制するものではなく、稼働が終わるのをポーリングします。timeout 時の Busy は exit code `7` で、稼働中に engine を置換・テストしない旨を示します（`strata_control/updater.py:65-76, 300-311`）。

Human 出力では待機イベントのメッセージを stdout に表示します。JSONL では待機イベントが JSON 行になり、JSON 出力では進捗イベントは表示されません。timeout 等の失敗は human mode で stderr、JSON/JSONL mode で JSON error object に出力されます（`strata_cli/update_cmd.py:62-84, 163-172, 225-232`）。`--quiet` は one-shot parser 群に追加される共通 flag で、JSON/JSONL 以外の stdout を抑制しますが、失敗時に捕捉した出力を stderr に戻す処理があります（`strata_cli/cli.py:508-515, 2232-2248`）。

## 出力とエラー

- 稼働中の待機中は `An engine is serving; waiting for it to stop before updating.` のイベントが出ます。human ではメッセージ、JSONL ではイベント JSON として扱われます（`strata_control/updater.py:305-311`、`strata_cli/update_cmd.py:62-84`）。
- 指定時間内に停止しなければ `Busy`（exit code `7`）です。人間向けでは `strata: ...` を stderr に出し、JSON/JSONL では `ok: false` と error code/message を含む JSON を stdout に出します（`strata_control/updater.py:65-76`、`strata_cli/update_cmd.py:167-172, 225-232`）。
- Ctrl-C は `stopped; a partial download is kept and the next update resumes it` として exit code `130` になります（`strata_cli/update_cmd.py:233-234`）。

## 根拠

- Parser と値変換: `strata_cli/update_cmd.py:30-39, 42-59`
- update/rollback への値の適用、`--check` と対話時の分岐: `strata_cli/update_cmd.py:163-215, 237-252`
- 共通フラグの追加と dispatch: `strata_cli/cli.py:139-140, 508-515, 2135-2137, 2232-2248`
- 稼働中判定、待機・timeout、Busy の出力コード: `strata_control/updater.py:65-76, 275-311, 317-327`
- 更新前・テスト起動後の待機、rollback 前の待機: `strata_control/updater.py:938-978, 1033-1044`
