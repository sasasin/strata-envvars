# `strata runtime stop --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--output` |
| 別名 | `--json`（`--output json` と同じ出力を選択） |
| 値 | `human` または `json` |

## 役割

停止操作の結果を人向けの短い表示にするか、機械処理向け JSON にするかを選びます。出力形式の指定自体は停止対象や停止方法を変えません。停止操作は、指定 profile の Strata 管理下の server を drain して停止します。

## 使い方

停止対象を確認する plan を JSON で表示する例です。`--plan` は plan の確認だけを行い、停止しません。

```sh
strata runtime stop --profile my-profile --plan --output json
```

実際の停止を行う呼び出しでは、必要に応じて plan で確認した owner / instance ID を `--if-owner-id` と `--if-instance-id` で渡し、確認後に対象が変わっていないことを条件にできます。

## 値と既定値

- 省略時は `human` です。
- `human` と `json` のみ受理します。`argparse` の `choices` による検証なので、他の値は parser が拒否し、usage とエラーを stderr に出して終了コード 2 になります。
- 同じオプションを複数回指定した場合は、通常の `argparse` の値設定により最後の値が残ります。
- `--json` は `runtime stop` を含む one-shot parser 群に追加されるフラグです。指定すると `main()` が `a.output` を `json` に設定します。`--json` と `--output human` を同時に指定した場合も、この正規化により JSON になります。

## 実行時の動作

CLI は `a.output == "json"` を機械出力の判定に使い、`management.runtime_action("stop", ...)` の結果を表示します。成功した `--plan` は `{"schema_version":1,"ok":true,"plan":...}` 形式です。それ以外の plan 結果や通常の停止結果は、結果辞書に `schema_version: 1` を加えた JSON です。JSON は標準出力に1行で出力されます。

`human` の場合は profile 名と状態を標準出力に表示し、結果に instance ID、API URL、launch 検証状態、readiness、error が含まれる場合はそれらも付加します。通常の stop 結果では主に profile と状態が表示されます。

相互作用:

- `--plan` は現在の owner と instance を照会し、停止予定を返します。管理下の稼働状態でない場合など plan が失敗したときは、成功 plan 専用の形式ではなく通常の結果形式になります。
- `--wait` の既定値は 330 秒で、stop の実行時に 1〜600 秒の範囲で検証されます。plan でも management 層ではこの値の範囲検証を通ります。
- `--if-owner-id` または `--if-instance-id` は実行前の対象確認に使います。指定した ID が現在値と異なれば停止せず、変更を示す失敗結果になります。plan ではこれらの実行前提条件を併用できません。確認時は両方の ID を渡してください。
- `--quiet` も one-shot parser から追加されます。`--output json` は quiet 時にも通常どおり JSON を出します。人向け出力と `--quiet` の組み合わせでは成功時の標準出力が抑止され、失敗時には捕捉された表示が標準エラーへ出されます。

## 適用条件と副作用

`--output` の適用範囲は `strata runtime stop` だけです。同じ名前の `--output` が他の runtime サブコマンドにもありますが、それぞれ別 parser の設定です。

このオプションに副作用はありません。一方、`--plan` を付けない `runtime stop` 自体は停止要求を owner host に送り、server が止まるまで待ちます。通常経路では OS に応じて子 server に停止シグナルを送り、Windows では owner pipe を閉じて drain を要求します。停止期限を超えると、その子プロセスツリーを終了し、失敗結果を返します。live owner host がない場合は記録された残存 process を識別し直して終了・回復を試みます。これらは stop 操作の効果であり、出力形式による差ではありません。

## 出力とエラー

- 停止結果が `ok: true` なら CLI 終了コードは 0、失敗なら結果内の `exit_code`（未設定時は 6）です。JSON モードでは失敗結果も JSON として標準出力に出ます。
- 例外経路では `_run()` がエラーを JSON モードなら `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` として標準出力に出し、human モードなら `strata: ...` を標準エラーに出します。終了コードは例外に付いた `exit_code`（なければ 2、OS エラーは 6、割り込みは 130）です。
- stop 内部の ID 不一致は通常の失敗結果として扱われ、JSON モードでは結果 JSON に、human モードでは状態行に反映されます。

## 根拠

- parser の選択肢・既定値・stop 固有引数: `strata_cli/cli.py:226-232`。
- one-shot parser への `--json` / `--quiet` 追加: `strata_cli/cli.py:508-515`。
- `--json` の `output=json` 正規化、quiet の分岐: `strata_cli/cli.py:2232-2247`。
- `--output` による JSON / human の描画、plan 出力、終了コード: `strata_cli/cli.py:1331-1373`。
- 例外時の JSON / human エラーと終了コード: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2193`。
- stop の wait 範囲、ID 条件、plan、journal 記録、runtime 呼び出し: `strata_control/management.py:271-291`。
- plan の対象状態確認: `strata_control/runtime.py:602-611`。
- stop の timeout / ID 検証、RPC、owner host 不在時の残存 process 処理: `strata_control/runtime.py:614-667`。
- owner host 側の ID 再確認と stop 処理: `strata_control/runtime.py:1209-1224`。
- 子 server の停止方法、期限超過時の process tree 終了、結果: `strata_control/runtime.py:990-1012`, `strata_control/runtime.py:1025-1035`。

調査範囲は上記 commit の Python Terminal CLI と同梱 `strata_control` 実装です。別の配布物・OS 上での実動作や、外部 server の内部 drain 実装は実行して確認していません。
