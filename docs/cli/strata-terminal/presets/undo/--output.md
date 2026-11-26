# `--output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets undo` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

undo の結果を人向けの短い文、または機械処理しやすい JSON で標準出力へ出します。出力形式の選択だけを行い、どのプリセットスロットを undo するか、その状態を戻す処理自体は変えません。

## 使い方

```sh
# 人向けの既定出力で、指定プリセットが属するスロットを戻す
strata presets undo 1a2b3c4d

# 同じ操作の結果を JSON で受け取る
strata presets undo 1a2b3c4d --output json

# JSON の run configuration に対応するスロットを戻す
strata presets undo ignored --config ./run.json --output json
```

`--config` を指定した場合、位置引数 `preset` は parser 上必須ですが、undo 対象の特定には使われません。代わりに設定ファイルから選択値とモデル識別情報を読み、対応するスロットを計算します。

## 値と既定値

- `human` と `json` のみ受理し、省略時は `human` です。各 `presets` サブコマンドに共通する parser helper がこの値を登録します（`terminal/strata_cli/tune_commands.py:55-61,76-78`）。
- 値は `choices` で検証されます。別の値は argparse の引数エラーとなり、コマンド処理には進みません（parser は `terminal/strata_cli/cli.py:514-515` で登録され、`main` が引数を解析します: `terminal/strata_cli/cli.py:2325-2334`）。
- オプションの重複指定時にどの値が残るかは、独自の重複処理を確認できませんでした。標準 argparse の挙動に依存します。

## 実行時の動作

`--output json` のとき `presets_command` は `machine=True` とし、undo 成功時に `{"schema_version":1,"ok":true,"active":...}` の1行 JSON を出します。`active` は戻ったプリセットの要約で、標準設定へ戻った場合は `null` です。`human` では `Back to '<名前>'.` または `Back to the standard settings.` を出します。いずれの形式も標準出力を使います（`terminal/strata_cli/tune_commands.py:101-106,472-476,504-513`）。

このオプションは永続状態を変更する undo と併用できます。対象プリセットを位置引数で指定すると、そのプリセットの属するスロットを使います。`--config` があれば設定を読み、現在の構成から選択値とモデルの SHA-256 を得てスロットを作ります（`terminal/strata_cli/tune_commands.py:504-511`）。プリセット undo は履歴の直前の ID を active に戻し、履歴が空なら active を解除して標準設定に戻します。対象プリセットの JSON ファイルが既にない場合も active は解除されます。状態は `active.json` に保存されます（`terminal/strata_control/presets.py:366-385`）。

## 適用条件と副作用

`--output` の違いによる undo の適用条件・副作用の差はありません。Undo はプリセット保管ディレクトリ内の `active.json` を更新します。ディレクトリは `STRATA_PRESET_DIR` が設定されていればその値、未設定なら profiles ディレクトリの隣の `presets` です（`terminal/strata_control/presets.py:45-50,227-233,366-385`）。コマンド自身はエンジンを起動しません（`terminal/strata_control/presets.py:16-17`）。

## 出力とエラー

- 存在しない・曖昧なプリセット参照や undo 履歴がない場合、JSON モードでは `ok:false` と `error.code` / `error.message` を含む JSON を標準出力へ出し、human モードでは `strata: ...` を標準エラーへ出します。プリセットエラーの終了コードは `5` です（`terminal/strata_cli/tune_commands.py:109-114,527-530`; `terminal/strata_control/presets.py:243-256,366-375`）。
- 設定の読み込みなどで発生した `OSError` / `ValueError` も同じ形式で失敗を報告し、`exit_code` 属性があればその値、なければ `2` を返します（`terminal/strata_cli/tune_commands.py:505-508,527-530`）。
- `--output` の不正値はコマンド本体のエラー形式ではなく、引数解析エラーです（`terminal/strata_cli/tune_commands.py:59-61`; `terminal/strata_cli/cli.py:2325-2334`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-61,76-78` — presets の parser と undo の引数、共通 `--output` の choices / 既定値。
- `terminal/strata_cli/cli.py:514-515,2229-2230,2325-2334` — parser 登録、`presets_command` への dispatch、引数エラー経路。
- `terminal/strata_cli/tune_commands.py:101-114,472-476,504-530` — 成功・失敗の出力形式、undo 処理、エラーコード。
- `terminal/strata_control/presets.py:45-50,227-256,366-385` — 保存先、参照解決、undo 履歴と状態更新。
