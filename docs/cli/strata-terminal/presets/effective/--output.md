# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets effective` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

`strata presets effective` の結果を人向けの短い表示か、機械処理向け JSON に切り替えます。保存済み tuning を現在の設定に重ねた場合の effective 値を調べるコマンドです。`--output` は出力形式を選ぶもので、ファイル出力先を指定しません。

## 使い方

```sh
strata presets effective <profile-name> --output json
```

`<profile-name>` の代わりに run configuration（JSON）のパスも指定できます。`target` は必須です。

## 値と既定値

- 省略時は `human`。
- 指定できる値は `human` と `json` のみ。`argparse` の `choices` による検証で、別の値は受け付けません。
- `--output` に短縮別名はありません。`--json` alias もこの parser には定義されていません。
- `presets` 配下の共通 parser helper がこの指定を各 presets サブコマンドへ追加します。effective では `target` とともに使います。

## 実行時の動作

`human` は成功時に `Using your tuning '<名前>'` または `No saved tuning is applied; the standard settings run.` を標準出力へ出します。`json` は `schema_version: 1` と `ok: true` を含む JSON を標準出力へ出します。effective の JSON payload には適用有無、preset/state/reasons、`args`・`env`・`sampling`・`per_request` と、元設定から変わった引数の `changed` 一覧が含まれます。

この出力選択後、コマンドは target の run configuration を読み、現在の選択に対応する active preset の overlay を計算します。preset が適用可能なら引数・環境変数・sampling の値を in-memory の設定に重ねて表示します。設定を書き戻したり、tuning の計測や preset の保存を行う処理はこの経路から呼ばれません。preset がない場合、または identity が hard stale／設定が安全規則に合わない場合は適用せず、effective の標準設定を返します。store の読み出し等で overlay 内に例外が起きた場合も、overlay は元設定を返し `info.error` を記録します（現行 payload はこの `error` を出力項目に含めません）。

## 適用条件と副作用

このオプションは表示形式だけを変え、preset の適用可否や effective 値の計算方法は変えません。`--output` 自体はファイルを作成・上書きしません。処理は target の解決・設定読み込みと preset store／identity の参照を伴います。store が存在しない、active preset がない場合は適用なしの結果になります。

## 出力とエラー

- 正常終了は終了コード `0`。JSON モードでは成功 JSON を標準出力に出します。
- target の解決・読み込み等が `PresetError`、`OSError`、`ValueError` になると、JSON モードは `schema_version: 1`、`ok: false`、`error`（code/message）を標準出力へ出し、human モードは `strata: <message>` を標準エラーへ出します。`PresetError` の終了コードは `5`、その他は例外の `exit_code` 属性（なければ `2`）です。
- `--output` に未対応の値を指定すると parser の選択肢検証で拒否され、argparse の usage/error 経路になります（終了コード `2`）。

## 根拠

- `strata_cli/tune_commands.py:53-55` — presets 共通 parser が `--output {human,json}`、既定値 `human` を定義。
- `strata_cli/tune_commands.py:78-79` — `effective` parser と必須位置引数 `target`。
- `strata_cli/cli.py:487`, `strata_cli/cli.py:2151-2152` — presets parser 登録と `presets_command` への dispatch。
- `strata_cli/tune_commands.py:95-108` — human/JSON 成功出力、エラー出力と終了コード。
- `strata_cli/tune_commands.py:289-304`, `strata_cli/tune_commands.py:361-378` — `--output` による形式選択、effective payload と表示文。
- `strata_cli/tune_commands.py:344-347` — presets 経路で捕捉する例外と終了コード。
- `strata_control/presets.py:441-482` — preset overlay、stale/安全規則による適用条件、元設定への fallback。

調査範囲は上記 checkout の Terminal CLI ソースです。CLI の実行や `--help` 表示、Release artifact の照合は行っていません。
