# `strata components update --force`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `false`、指定時は `true` |

## 役割

通常は再試行を抑止するエンジン版を、更新候補として再度試すためのフラグです。対象は、以前テスト起動に失敗した版、またはロールバックで戻した版です。新しい版を強制的に選ぶ、署名・互換性検証を省略する、あるいはテスト起動を省略するフラグではありません。

## 使い方

```sh
strata components update --force
```

更新前の状態確認だけを行う場合は、次のように併用できます。この場合、候補表示は変わりますが、ダウンロードやインストールは行われません。

```sh
strata components update --force --check
```

## 値と既定値

`argparse` の `store_true` フラグで、引数値はありません。未指定時の値は `false` です。`--force yes` のように値を続ける形式はこの parser の指定形式ではなく、余分な引数として拒否されます（usage error）。

## 実行時の動作

`strata components update` の parser は共通オプション定義 `_common()` を使い、`--force` を登録します。コマンド実行時には値が `updater.Context.force` に渡されます（`strata_cli/update_cmd.py:30-39, 50-55, 163-184`、`strata_control/updater.py:316-335`）。

エンジン候補がインストール済み版より新しい場合、通常は状態ファイルの `engine.failed` に同じ version と manifest hash のテスト起動失敗記録があると `failed-before` になり、また `engine.skipped` にある版はロールバック済みとして `skipped` になります。`--force` はこの抑止判定を通過させ、これらの状態も `update_engine()` が処理できるようにします（`strata_control/updater.py:591-614, 926-937`）。

失敗記録は24時間を過ぎると古いものとして無視されます。その場合は `--force` がなくても、同じ manifest の候補が通常の `available` として扱われ再試行可能です（`strata_control/updater.py:603-614, 1135-1142`）。

`--check` は同じ候補選択を使うため `--force` により結果の状態・注記が変わり得ますが、`check()` は feed の確認のみを行います。通常更新ではエンジン更新の判断にだけ `ctx.force` が参照され、Control や `--app` の更新可否には使われません（`strata_control/updater.py:624-635, 931-937, 1145-1151, 1274-1297`）。

強制再試行後も、署名済み feed の選択、GPU make guard、パッケージ検証、テスト起動、切替直前の serving 確認は通常どおりです。テスト起動を通過してから live engine を切り替え、成功時には失敗・skip 記録を消します。テスト起動に失敗した場合は新エンジンを有効化せず、失敗理由を状態と履歴に保存します（`strata_control/updater.py:8-21, 938-976, 992-1027`）。

## 適用条件と副作用

- feed が選んだ候補が `available`（または `--force` により再試行対象となった `failed-before` / `skipped`）である場合に、エンジン更新経路へ進みます。候補が現行版以下、該当 hardware 向け候補がない、または make guard に拒否された場合に `--force` でそれらを覆す処理はありません（`strata_control/updater.py:566-614, 926-943`）。
- 更新経路はネットワークからアーカイブを取得し、ステージング領域へ展開・検査し、テスト起動します。成功するとエンジンの切替、更新状態・履歴の保存、旧版の保持とそれ以外の旧エンジンの整理が行われます（`strata_control/updater.py:8-21, 943-976, 979-1027`）。
- エンジンが serving 中なら、`--wait` による待機など通常の busy 処理が適用されます。`--force` は待機条件を変更しません（`strata_cli/update_cmd.py:34-36, 182-184`; `strata_control/updater.py:300-311, 945-947`）。
- `strata components rollback --force` も共通 parser 上は受理されますが、rollback の処理は `ctx.force` を参照しません。この文書の対象である update の効果とは別です（`strata_cli/update_cmd.py:57-59, 185-196`; `strata_control/updater.py:1033-1078`）。

## 出力とエラー

通常の人間向け出力では、更新前に停止したエンジン更新の失敗は stderr に `strata: <理由>` と表示され、その `UpdateError` の exit code が返ります。機械出力ではエラー情報を JSON で出力します。テスト起動失敗はコード6で、既存エンジンは変更されません。serving 中はコード7、署名・ハッシュ・make guard などの拒否はコード5、割り込みはコード130です。`--force` はこれらの失敗条件や終了コードを変更しません（`strata_cli/update_cmd.py:163-172, 225-234`; `strata_control/updater.py:54-75, 967-976, 1274-1297`）。

`--check` の人間向け出力は候補状態と注記を表示します。`--output json` / `jsonl` ではそれぞれ JSON / JSON Lines の出力経路を使います（`strata_cli/update_cmd.py:62-84, 203-209`）。

## 根拠

- parser とコマンド登録: `strata_cli/update_cmd.py:30-59`
- `Context.force` への受け渡し、check / update の分岐と失敗出力: `strata_cli/update_cmd.py:163-234`
- 再試行抑止と `--force` の判定: `strata_control/updater.py:591-614, 926-937`
- 失敗記録の保存、検査後の切替と記録の解除: `strata_control/updater.py:953-976, 992-1027`
- 失敗記録の有効期間: `strata_control/updater.py:1135-1142`
- 対象 revision と作業状態: 調査開始時に `git rev-parse HEAD` は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main`（変更表示なし）。

同一 revision の CLI `--help` は実行せず、parser 定義と実装を確認しました。Release artifact の実行時確認は本調査に含めていません。
