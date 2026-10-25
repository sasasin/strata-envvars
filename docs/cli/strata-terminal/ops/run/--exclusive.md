# `--exclusive`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--exclusive` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `false`、指定時は `true`。 |

## 役割

校正測定 (`engine.calibrate.measure`) の recipe を実行するとき、測定対象デバイスを使う他の model instance が停止済みであることを operator が確認した、という実行ごとの確認です。ハードウェアの独占を単独で保証するフラグではありません。

## 使い方

校正 recipe `calibrate` を、保存 profile `four-gpu` に対して実行する例です。対象デバイスを使う他の処理を停止したことを確認してから実行します。

```sh
strata ops run calibrate --profile four-gpu --exclusive
```

`--output json` を付けると one-shot の結果を JSON で出力できます。recipe の種類と実行による影響は [`ops` コマンド概要](../README.md)を参照してください。

## 値と既定値

- `argparse` の `store_true` フラグであり、引数値は指定しません。既定値は `false` です（`strata_cli/cli.py:278-280`）。
- `ops run` に属するオプションです。他の `ops` action の parser には追加されていません（`strata_cli/cli.py:255-290`）。
- recipe が `engine.calibrate.measure` の場合、指定は毎回必須です。省略すると「calibration recipe requires --exclusive for each run」として拒否されます（`strata_control/recipes.py:363-396`）。
- calibration 以外の recipe に指定すると、実行前にエラーコード `2` で拒否されます。省略すれば、通常どおりその recipe を実行します（`strata_cli/cli.py:1448-1457`）。したがって restart や components verify を排他実行する指定ではありません。
- 同じフラグを複数回指定しても、`store_true` の値は `true` のままです。値を伴う形式は parser の定義にありません。

## 実行時の動作

CLI は recipe を読み、`--exclusive` を recipe の種類と照合してから `recipes.run()` に真偽値を渡します。校正 recipe で指定が欠けていれば journal record の作成より前に失敗します。指定されていれば recipe の実行記録を開始し、保存済みの絶対 `report_dir` を用意して、その配下に新しい `calibration-<UUID>.json` を作る測定を呼び出します。recipe は設定値を適用せず、生成された report は別途 review してから適用します（`strata_cli/cli.py:1448-1457`; `strata_control/recipes.py:395-423`; `strata_control/recipes.py:107-111`）。

測定処理は profile lock と managed activity の排他 lease を取り、managed Strata runtime instance が動作中なら拒否します。また、profile の設定 port（override があればその endpoint も）で server が応答する場合は拒否します。report の出力先は既存ファイルを上書きせず、存在すれば拒否します（`strata_control/calibration.py:192-229,270-296`; `strata_control/runtime.py:173-188`）。

## 適用条件と副作用

- 対象 recipe は校正測定だけです。recipe が要求する `report_dir` は絶対パスでなければならず、実行時にディレクトリを作成し、symlink でない directory であることを検査します（`strata_control/recipes.py:107-111,413-423`）。
- 測定にはフル Strata folder の `setup.py` と `tools/calibrate.py` が必要です。import できず `STRATA_INSTALL_DIR` にも該当 folder がない場合、エラーコード `5` で拒否されます（`strata_control/calibration.py:41-64`）。
- recipe run は開始・終了状態と結果をローカル operation journal に記録します。測定 report は新規作成され、run config は変更されません（`strata_control/recipes.py:397-423`; `strata_control/journal.py:326-340,359-373`; `strata_control/calibration.py:270-276,322-336`）。
- `--exclusive` は利用者による停止確認です。コード上の port 検査と managed activity lease は Strata が管理する経路を対象とします。直接起動された旧式 server、無関係な GPU process、Windows 上の排他制御を保証しないため、それらも利用者が確認する必要があります（`strata_control/calibration.py:205-229`; `docs/TERMINAL.md:160`）。

## 出力とエラー

- 成功時は human mode で operation JSON、`--output json` では `ok` と operation を含む JSON を標準出力に返し、終了コード `0` です（`strata_cli/cli.py:1458-1464`）。測定中の progress message は標準エラーへ送られます（`strata_control/recipes.py:419-421`）。
- calibration 以外への指定は `strata: --exclusive applies only to calibration recipes` を標準エラーへ出し、終了コード `2` を返します。JSON mode では `ok: false` の error object を標準出力へ返します（`strata_cli/cli.py:1448-1450`; `strata_cli/cli.py:527-532`）。
- calibration recipe での指定漏れ、runtime lease の競合、稼働 server、report directory の不備、測定失敗はそれぞれ拒否されます。`ProfileError` は指定された exit code（未指定時 `2`）で CLI error として返され、通常の実行失敗後は operation journal に failed state と error code が記録されます（`strata_control/profiles.py:30-35`; `strata_control/recipes.py:395-396,429-437`; `strata_control/calibration.py:205-229,292-315`）。
- 他の `ops` action に `--exclusive` を付けると、その action の parser が未認識引数として usage error を出し、終了コード `2` になります（`strata_cli/cli.py:255-290,2223-2231`）。

## 根拠

- parser と scope: `strata_cli/cli.py:255-290`
- option の recipe 種別チェック、実行呼び出し、結果コード: `strata_cli/cli.py:1391-1464`
- acknowledgement 必須条件、journal、測定と report 作成: `strata_control/recipes.py:363-438`
- report directory の validation: `strata_control/recipes.py:93-114`
- calibration の port 検査、managed lease、出力と失敗経路: `strata_control/calibration.py:192-336`; lease の実装: `strata_control/runtime.py:173-188`
- CLI error 表示と parser usage error: `strata_cli/cli.py:527-532,2217-2231`
- lease の適用範囲に関する利用者向け記述: `docs/TERMINAL.md:160`
