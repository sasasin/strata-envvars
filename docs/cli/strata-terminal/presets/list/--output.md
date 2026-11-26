# `strata presets list --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets list` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

保存済み tuning preset の一覧を、人向けの行表示か機械処理向け JSON で標準出力へ出します。出力形式を選ぶだけで、preset の検索・保存状態は変更しません。

## 使い方

```sh
strata presets list --output human
strata presets list --model IQ3_S --output json
```

`--output` は `list` のサブコマンド parser に登録されているため、`strata presets list` の後に指定します。モデル・量子化名の部分一致フィルター `--model` と併用できます（`terminal/strata_cli/tune_commands.py:63-64`）。

## 値と既定値

- `human`: 人向け表示。省略時の既定値です。
- `json`: `schema_version: 1` と `ok: true`、`presets` 配列を含む1つの JSON オブジェクトを出します。
- parser は `choices=("human", "json")` で検証します。別の値は argparse の引数エラーとなり、コマンド処理には進みません（`terminal/strata_cli/tune_commands.py:59-64`）。
- このオプションは値を1つ取ります。短縮別名はありません。

## 実行時の動作

`--output json` のときだけ machine 出力モードとなり、一覧各要素を `_summary` で整形して JSON の `presets` 配列にします。各要素には ID、名前、active 状態、作成時刻、choices、settings、answers、notice、測定値、tuner、recheck、slot などが含まれます。`human` では各 preset を「active 印・ID の先頭8文字・名前・測定 gain・クラス」の行にし、該当がなければ案内文を表示します（`terminal/strata_cli/tune_commands.py:472-483, 534-541`）。

一覧は preset 保存ディレクトリの JSON ファイルから読み取られます。`--model` が空でなければ、choices の JSON 表現に対する大文字小文字を区別しない部分一致で絞り込みます。active 状態を `active.json` の索引と照合し、作成時刻の降順で並べます。preset ディレクトリが存在しない場合は空一覧です（`terminal/strata_control/presets.py:45-50, 227-229, 259-277`）。

## 適用条件と副作用

このコマンドは一覧ファイルと active 索引を読み取ります。preset ディレクトリは `STRATA_PRESET_DIR` が設定されていればその値（`~` 展開後）、未設定なら profile ディレクトリの隣の `presets` です（`terminal/strata_control/presets.py:45-50`）。一覧処理では `active.json` を読むほか、schema が一致しない JSON や読み込めない JSON は一覧から除外します。ファイルの変更、engine の起動、ネットワークアクセスはこの一覧経路では行いません（`terminal/strata_control/presets.py:71-75, 259-277`）。

## 出力とエラー

成功時の出力は標準出力です。`json` 成功時は `ensure_ascii=False` で1行の JSON を出し、終了コード `0` を返します。`human` も終了コード `0` です（`terminal/strata_cli/tune_commands.py:101-106`）。

preset 処理中の `PresetError` は終了コード `5`、`OSError` / `ValueError` は例外の `exit_code` 属性があればその値、なければ `2` になります。`json` 指定時は標準出力に `ok: false` と error オブジェクトを出し、`human` 指定時は `strata: <message>` を標準エラーへ出します（`terminal/strata_cli/tune_commands.py:109-114, 527-530`）。無効な `--output` 値など parser 段階の引数エラーは argparse が拒否します。調査したコード範囲では、その場合の stderr 文面・usage 表示の詳細は個別に固定されていません。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-64` — `presets list` parser と `--output` の選択肢・既定値、および `--model`。
- `terminal/strata_cli/tune_commands.py:472-483, 534-541` — 出力モード判定、人向け一覧、JSON payload の生成。
- `terminal/strata_cli/tune_commands.py:101-114, 527-530` — 成功・失敗の出力先と終了コード。
- `terminal/strata_control/presets.py:45-50, 71-75, 227-229, 259-277` — 保存先、JSON 読み込み、無効データの除外、絞り込み・active 判定・並び順。
