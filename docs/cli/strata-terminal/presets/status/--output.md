# `strata presets status --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets status` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

status の結果を人向けテキストか JSON で標準出力へ出します。保存済み設定に対応する tuning preset の有効状態を調べるコマンドで、`--output` 自体は調査対象を変えません。

## 使い方

```sh
strata presets status my-profile --output json
```

`my-profile` は保存済み profile 名、または JSON run config のパスに置き換えます。位置引数 `target` は必須です（`strata_cli/tune_commands.py:59-60`）。

## 値と既定値

- `human`: 人向けの一行表示です。省略時の既定値です。
- `json`: JSON オブジェクトを一行で標準出力へ出します。`schema_version: 1` と `ok: true` に加え、slot、推奨名、choices、有効 preset、state、reasons、同じ slot の presets、undo 可否、無効化状態、直前の active preset を含みます。
- parser は `choices=("human", "json")` で受理値を制限します。別名や出力ファイル指定はありません（`strata_cli/tune_commands.py:53-60`）。

例:

```sh
strata presets status my-profile
strata presets status ./run-config.json --output json
```

## 実行時の動作

`--output json` のとき `machine` が真になり、`_print` が `{"schema_version":1,"ok":true,...}` の形式を標準出力へ出します。`human` の場合は、有効 preset があれば `Active: '<name>' (<state>)`、なければ `No saved tuning for these choices yet.` と表示します（`strata_cli/tune_commands.py:95-100,289-303,391-408`）。

出力形式以外の処理は共通です。`target` を profile 名または JSON パスとして解決し、現在の hardware / engine / model identity と choices から slot を求めます。active index と preset 一覧を読み、active preset の staleness (`fresh` / `soft` / `hard`) と理由を計算して出力します（`strata_cli/tune_commands.py:391-408`、`strata_control/profiles.py:382-388`、`strata_control/presets.py:136-155,158-197`）。

`--output` は `presets/status` の subparser に登録されており、`strata presets` の全階層に共通するグローバルオプションではありません（`strata_cli/tune_commands.py:49-60`）。他の `presets` サブコマンドにも同名オプションがありますが、それぞれの subparser に登録されています。

## 適用条件と副作用

この status 分岐は preset の active 状態を変更せず、GPU 上で推論や tuning を実行しません。現在状態の照合に hardware 情報、engine manifest、model file identity を読み取ります。GPU 情報取得には環境により `nvidia-smi` の照会または Linux の sysfs 読み取りが使われます（`strata_control/tune_machine.py:70-117,264-309`）。

対象が profile 名の場合、profile 解決時に profile を読み込みます。権限エラー等で読み込みに失敗した場合の既知ルート修復が行われ得るため、呼び出し全体をファイル非変更とは断定できません。JSON パスは run config として読み込まれます（`strata_control/profiles.py:150-166,382-388`）。

## 出力とエラー

- 有効 preset がない場合も通常結果として終了コード `0` で、human 表示では「まだ保存 tuning がない」旨を返します（`strata_cli/tune_commands.py:391-408,95-100`）。
- `--output` に `human` / `json` 以外を指定すると argparse の選択肢検証で拒否され、status 処理には進みません。CLI は parser で引数を解析してから dispatch します（`strata_cli/tune_commands.py:53-60`、`strata_cli/cli.py:2223-2231`）。
- 対象 profile / config の解決・読み込みに失敗した場合、`ProfileError` は `ValueError` の派生として捕捉され、既定の exit code（通常 `2`、読み込み不能など明示指定時は `5`）で返されます。`PresetError` は `5` です。JSON 形式では `ok: false` と `error` を標準出力に出し、human 形式では `strata: ...` を標準エラーに出します（`strata_cli/tune_commands.py:103-108,344-347`、`strata_control/profiles.py:30-35,135-147`）。

## 根拠

- `strata_cli/tune_commands.py:49-60` — `presets status` parser、必須 target、`--output` の値と既定値。
- `strata_cli/tune_commands.py:95-108,289-303,391-408` — 成功・失敗時の出力、status の処理と返却項目。
- `strata_control/profiles.py:30-35,135-147,150-166,382-388` — profile/config の読込、解決、エラー。
- `strata_control/presets.py:136-155,158-197,202-215` — identity、staleness、active index / preset の読み込み。
- `strata_control/tune_machine.py:70-117,264-309` — hardware 情報と engine/model identity の取得。
- `strata_cli/cli.py:2223-2231` — parser 実行と未知・不正引数の拒否。
