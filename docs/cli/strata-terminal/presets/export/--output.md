# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets export` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

ファイル出力を指定した場合の完了メッセージ形式を選びます。プリセットを書き出すファイル名を指定するオプションではありません。出力先ファイルは `--file` で指定します。

## 使い方

```sh
strata presets export PRESET_ID --file ./preset.json --output json
```

`PRESET_ID` にはプリセット ID、4文字以上の一意な ID 接頭辞、または大文字小文字を区別しない名前を指定できます。

## 値と既定値

- 値は `human` または `json` に限られます。既定値は `human` です。
- 値を省略すると argparse がエラーにし、候補外の値も受理しません。`--output` は値を1つ取ります。同じオプションを複数回指定したときは、argparse の通常の `store` 動作により最後の値が使われます。
- `--output` に短縮別名はありません。

## 実行時の動作

- `--file PATH` を指定すると、まず `presets.export_preset(PRESET_ID)` でプリセットを解決し、JSON を UTF-8 で `PATH` に書き込みます。JSON はインデント付きで非 ASCII 文字をエスケープせずに出力します。その後 `--output human` なら `Wrote PATH`、`--output json` なら `{"schema_version":1,"ok":true,"file":"PATH"}` 形式の完了情報を stdout に出します。
- `--file` を省略すると、プリセット本体をインデント付き JSON として stdout に出して終了します。この経路は `--output human` / `json` のどちらでも同じで、`--output json` の成功 envelope には包まれません。
- `--file` の書き込みは `Path.write_text` によるため、同名ファイルがあれば上書きし、親ディレクトリは自動作成しません。`--output` 自体はファイルの有無や書き込み方法を変えません。
- エクスポートされたプリセットは保存済みプリセットを検索したデータから `active` 情報を除いた辞書です。エクスポート処理はプリセットストアを更新しません。

## 適用条件と副作用

プリセットの解決は、ID 完全一致、4文字以上の ID 接頭辞、または完全一致する名前で行います。該当なし、接頭辞の曖昧一致、名前の曖昧一致は拒否されます。保存先は相対パスなら現在の作業ディレクトリを基準にします。既存ファイルを指定すると上書きされるため、必要なファイルを誤って置き換えない出力先を選んでください。

## 出力とエラー

- `--file` ありの成功時は、前述の human メッセージまたは JSON envelope を stdout に出し、終了コード `0` を返します。`--file` なしの成功時はプリセット JSON を stdout に出して `0` を返します。
- プリセットが存在しない、ID/名前が曖昧など `PresetError` となる場合、human 出力では `strata: <理由>` を stderr に出して終了コード `5`、JSON 出力では `{"schema_version":1,"ok":false,"error":{"code":5,"message":"<理由>"}}` を stdout に出します。
- ファイル書き込みなどで `OSError` または `ValueError` が起きる場合、human 出力では理由を stderr に出し、JSON 出力ではエラー envelope を stdout に出します。通常の `OSError` / `ValueError` の終了コードは `2` です。
- `--output` の値が不正、または値が欠落している場合は argparse が usage とエラーを stderr に表示し、終了コード `2` になります。

## 根拠

- `strata_cli/tune_commands.py:49-55` は `presets` の各サブコマンド共通 parser に `--output` の選択肢と既定値を定義し、`strata_cli/tune_commands.py:73-76` は `export` に `--file` を別途定義します。
- `strata_cli/tune_commands.py:95-108` は human / JSON 成功出力と失敗出力の形式・終了コード返却を定義します。
- `strata_cli/tune_commands.py:331-347` は export のファイル有無による処理分岐、JSON 直出力、`PresetError` / `OSError` / `ValueError` の捕捉を定義します。
- `strata_control/presets.py:218-231` はプリセット検索方法と未検出・曖昧一致のエラーを定義し、`strata_control/presets.py:390-393` はエクスポート時に `active` 情報を除去します。
- `strata_cli/cli.py:487-489` は `presets` parser をトップレベル CLI に登録し、`strata_cli/cli.py:2151-2152` は `presets` コマンドを `presets_command` へ委譲します。
