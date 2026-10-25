# `--file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets export` |
| オプション | `--file` |
| 別名 | なし |
| 値 | 出力先ファイルのパス（文字列） |

## 役割

指定した保存済み preset を JSON ファイルへ書き出します。`--file` を省略すると、同じ JSON を標準出力へ表示します。

## 使い方

```sh
strata presets export "Office" --file ./office-preset.json
```

`Office` は preset の名前、ID、または4文字以上の一意な ID prefix です。指定先に同名ファイルがすでにある場合は上書きされるため、必要なファイルを誤って置き換えないパスを指定してください。

## 値と既定値

- 値は1つのパス文字列です。parser は型変換や存在確認、拡張子の検査をしません。未指定時の値は `None` です。
- 空文字列 `""` は argparse で値として渡せますが、実行側は値を真偽判定するため、空文字列ならファイルへ書かず標準出力へ出します。
- 同じ `--file` を複数回指定した場合の独自処理はありません。argparse の通常動作により最後に指定した値が使われます。
- パスは `Path(a.file)` にそのまま渡されます。相対パスはプロセスの作業ディレクトリ基準で解決され、`~` のホームディレクトリ展開は行われません。

## 実行時の動作

1. 引数の位置にある preset 名または ID から preset を検索します。検索は名前の大文字小文字を区別せず、完全一致名、完全一致 ID、4文字以上の ID prefix を扱います。一致しない場合と複数一致する場合は失敗します。
2. export 用データから実行時だけ付与された `active` 項目を取り除きます。
3. `--file` に空でない値があれば、整形した JSON を UTF-8 でそのパスへ書き込み、完了メッセージを表示します。出力先が既存ファイルなら内容を切り詰めて置き換えます。親ディレクトリは作成しません。
4. `--file` が省略または空文字列なら、整形した JSON を標準出力へ表示します。

この処理は preset の読み取りと指定先への書き込みです。preset の適用・削除・保存状態の更新は行いません。`--output human|json` は `presets export` にもあります。ファイル指定時は human なら `Wrote <path>`、json なら成功結果 `{"schema_version":1,"ok":true,"file":"<path>"}` を標準出力へ出します。ファイルを指定しない場合は `--output` の値にかかわらず preset JSON 本体を標準出力に出します。

## 適用条件と副作用

- `--file` は `strata presets export` の parser にだけ定義されており、他の `presets` サブコマンドの option ではありません。
- ファイル出力は一時ファイル経由ではなく、`Path.write_text` による直接書き込みです。既存ファイルの上書き、親ディレクトリが存在しない場合の失敗、OS の書き込み権限やパスに依存する失敗があり得ます。
- preset の検索元は preset store です。`STRATA_PRESET_DIR` が設定されていればそのディレクトリ（`~` 展開あり）が使われ、未設定時は profile directory の親にある `presets` が使われます。この環境変数は出力先 `--file` の解釈には使われません。

## 出力とエラー

- 成功時、出力ファイルへの書き込み後に human メッセージまたは JSON 成功オブジェクトを標準出力へ出し、終了コード `0` を返します。
- preset がない場合や ID prefix / 名前が曖昧な場合は `PresetError` となり、human 出力では `strata: ...` を標準エラーへ、`--output json` ではエラーオブジェクトを標準出力へ出して終了コード `5` を返します。
- 書き込み時の `OSError` などはサブコマンド内で捕捉されます。human 出力は `strata: <例外メッセージ>` を標準エラーへ、JSON 出力は `ok:false` のエラーオブジェクトを標準出力へ出し、通常は終了コード `2` を返します。

## 根拠

- `strata_cli/tune_commands.py:49-55,73-76` — `presets` の parser 構成、`export` の位置引数と `--file`（既定値 `None`）、共通 `--output`。
- `strata_cli/tune_commands.py:289-294,331-348` — `--output` による human/JSON の選択、preset export、ファイル書き込みと標準出力への分岐、例外と終了コード。
- `strata_control/presets.py:218-231,390-393` — preset の参照解決と export データからの `active` 除去。
- `strata_control/presets.py:45-50` — preset store のディレクトリ決定。出力先とは別の設定。
- `strata_cli/cli.py:487-488,2151-2152` — Terminal CLI への parser 登録と `presets` handler への委譲。
