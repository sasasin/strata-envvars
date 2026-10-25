# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |
| 既定値 | `human` |

## 役割

調整結果の表示形式を選びます。`human` は人向けの結果表示、`json` は結果・エラーを機械処理向けの JSON として標準出力へ出します。JSON モードは Desktop 側からも利用されており、呼び出し側は進捗を `--status-file` で受け取れます。

## 使い方

```sh
strata tune auto default --output json
```

`default` は調整対象の保存済み profile 名または run configuration を表す位置引数です。`--output` は `strata tune auto` parser に属し、他の `tune` サブコマンドや `presets` コマンドの同名オプションとは別スコープです（`strata_cli/tune_commands.py:20-46,49-55`）。

## 値と既定値

- parser は `choices=("human", "json")`、`default="human"` として定義しています。値の省略時は `human` です（`strata_cli/tune_commands.py:45-46`）。
- `json` と `human` 以外の値は `argparse` が受け付けません。これは `auto()` の処理に入る前の parser エラーであり、通常の usage / error 表示経路になります（parser 定義: `strata_cli/tune_commands.py:45-46`、parser の呼び出し: `strata_cli/cli.py:2217-2231`）。
- この parser は同じオプションの繰り返し指定を特別扱いしていません。`argparse` の通常動作により最後の値が `a.output` になります。

## 実行時の動作

- `a.output == "json"` を `machine` として使い、JSON の場合は進捗 callback の `say()` が何も出力しません。`human` の場合、進捗メッセージは stderr に flush 付きで出ます（`strata_cli/tune_commands.py:174-179,202-215`）。
- 調整完了時、`json` は stdout に `{"schema_version":1,"ok":true,"result":...}` を1行で出します。`human` は `_human_result()` の整形結果を stdout に出します（`strata_cli/tune_commands.py:257-260`）。
- `--output` は tuner の選択肢・測定・preset 保存条件を変更しません。たとえば改善結果または既定値確認結果は、`--no-save` がない限りどちらの形式でも保存対象になります（`strata_cli/tune_commands.py:194-197,246-254`）。
- JSON でも `--status-file` を指定すると、進捗ごと、および完了時に JSON 状態ファイルを書き換えます。書き込みは一時ファイルから atomic replace で行い、`OSError` は無視されるため、状態ファイル更新失敗はこの helper 内では報告されません（`strata_cli/tune_commands.py:149-157,209-215,255-256`）。Desktop 呼び出し側も `--output json` と status file を渡しています（`strata_cli/launch/runner.py:1356`）。

## 適用条件と副作用

- このオプションは `strata tune auto` の表示経路だけに適用されます。`strata tune` の他のサブコマンドでは、それぞれ個別の parser 定義があり、同じ値でもここで説明する挙動を共有するとは限りません（`strata_cli/cli.py:400-486`）。
- JSON は stdout に出力されます。tuning 中に発生する human 進捗メッセージは JSON モードでは抑制されますが、tuner が行う測定や試行記録、条件を満たした preset 保存は別の処理です（`strata_cli/tune_commands.py:205-215,230-260`）。
- `--output` 自体はファイルを作りません。ファイル出力がある場合は、別指定の `--status-file` による進捗状態の書き込みです（`strata_cli/tune_commands.py:42-46,149-157`）。

## 出力とエラー

- コマンド処理内で `_fail()` に到達した場合、`human` は `strata: <message>` を stderr に出し、JSON は stdout に `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を出します。返却終了コードは `_fail()` に渡された値です（`strata_cli/tune_commands.py:95-108,178-190`）。
- JSON の最終結果は、tuning outcome が `improved` / `default_confirmed` でない場合も `ok: true` の result envelope で出力されます。終了コードは `improved` / `default_confirmed` が `0`、`cancelled` が `130`、その他が `6` です（`strata_cli/tune_commands.py:230-261`）。したがって `ok` はこの JSON envelope の生成を示し、終了コードや `result.outcome` と併せて結果を判定してください。
- 選択肢外の値など parser 段階の失敗は `_fail()` を通らず、CLI parser の usage / error 経路になります（`strata_cli/cli.py:2217-2231`）。

## 根拠

- 索引上の配置とコマンド scope: `docs/cli/README.md:804-823`。
- `auto` parser と `--output` の choices / default: `strata_cli/tune_commands.py:20-46`。
- JSON・human の進捗と最終出力、エラー形式: `strata_cli/tune_commands.py:95-108,174-215,257-261`。
- tuner 結果・保存条件および status file 更新: `strata_cli/tune_commands.py:149-157,230-256`。
- コマンド dispatch と parser 実行: `strata_cli/cli.py:486-486,1652-1653,2217-2237`。
- Desktop 側の JSON 呼び出し: `strata_cli/launch/runner.py:1356`。
