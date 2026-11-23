# `--output`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune report` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json`。既定値は `human` |

## 役割

最後に `strata tune auto` が保存した調査レポートを、人向けテキストまたは JSON で標準出力へ表示します。このオプションは保存済みレポートの表示形式だけを選び、チューニングや再計測は実行しません。

## 使い方

```sh
# レポートを人向けのテキストで表示する（既定）
strata tune report

# 機械処理向けの JSON で表示する
strata tune report --output json
```

## 値と既定値

- `human` と `json` のみを受理します。省略時は `human` です。
- 空文字列やその他の値は `argparse` の選択肢検証で拒否されます。`--output` の値自体を省略した場合も引数エラーになります。
- 同じオプションを複数回指定した場合の最終値は標準の `argparse` に委ねられます。独自の重複指定検証はありません。

## 実行時の動作

`strata tune report` は `strata_control.tune_report.read()` から最後のレポートを読みます。既定の `human` では本文をそのまま標準出力へ出し、読み取れるレポートがない場合は `No tune has been run yet.` を出します。`json` では `{"schema_version":1,"ok":true,"report":...}` 形式の JSON を1行出力します。レポートが読めない場合、JSON の `report` は `null` になります。

レポートファイル名は `last-tune-report.txt` です。保存先は preset ディレクトリで、`STRATA_PRESET_DIR` が設定されていればそのディレクトリを使い、未設定なら profile ディレクトリの親にある `presets` ディレクトリを使います。レポートは `tune auto` の完了時に生成され、次回の保存で置き換えられます。`--output` による表示ではファイルを書き換えません。

## 適用条件と副作用

保存済みレポートを読むだけの処理です。`tune auto` が作成するレポートには基準測定、試した設定の判定、除外した設定の理由、次の案内が含まれます。レポートは保存時に atomic 書き込みを行い、現在の利用者だけがアクセスできるよう制限されます。レポート保存に失敗した場合、`tune auto` は保存失敗を無視し、テキスト出力時のレポート参照案内も表示しません。

## 出力とエラー

- 不正な値は parser が拒否します。`argparse` の標準エラー表示と終了コード 2 になります。
- レポートの読み込みで `OSError` が起きた場合、読取 helper は `None` を返します。そのため human 出力は未実行メッセージ、JSON 出力は `report: null` となり、読込失敗とレポート未作成は区別されません。
- 正常な report 表示は終了コード 0 です。出力先が閉じられて `BrokenPipeError` になった場合、CLI の共通処理は終了コード 0 を返します。

## 根拠

- `terminal/strata_cli/cli.py:423-424` は `tune` のサブコマンド parser を定義し、`terminal/strata_cli/cli.py:514` から report parser を登録します。
- `terminal/strata_cli/tune_commands.py:51-52` は `report` の `--output` 値、選択肢、既定値を定義します。
- `terminal/strata_cli/cli.py:1725-1726` は `tune report` を `tune_commands.report()` へ振り分けます。
- `terminal/strata_cli/tune_commands.py:101-106` は JSON 成功時の envelope と標準出力への出力を定義し、`terminal/strata_cli/tune_commands.py:230-237` は report 読込後の human / JSON 分岐、未作成時の文言、終了コードを定義します。
- `terminal/strata_control/tune_report.py:12-15` は保存ファイル名と未実行時の文言を定義し、`terminal/strata_control/tune_report.py:87-109` は保存先解決、保存、読込時の `OSError` 処理を定義します。
- `terminal/strata_control/presets.py:45-50` は `STRATA_PRESET_DIR` と既定の preset ディレクトリを解決し、`terminal/strata_control/presets.py:53-57` は保存時のディレクトリ作成と一時ファイル書き込みを行います。
- `terminal/strata_cli/tune_commands.py:417-424` は `tune auto` 完了時のレポート生成・保存、および保存成功時の案内表示を行います。
- `terminal/strata_cli/cli.py:2256-2257` は CLI 共通の `BrokenPipeError` 処理を定義します。
