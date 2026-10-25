# `strata presets export`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets export` |
| 位置引数 | `preset` — 保存済み tuning preset の名前、ID、または一意な ID prefix |
| 主なオプション | `--file`、`--output`。値と既定値は各オプション文書を参照 |

## 役割

保存済み tuning preset を JSON として標準出力へ表示するか、指定したファイルへ書き出します。preset を別環境へ移す用途では、出力を `strata presets import FILE` に渡せます。export 自体はエンジンを起動せず、preset の設定を有効化もしません。

## 使い方

```sh
# JSON を標準出力へ表示
strata presets export "Office preset"

# 新しいファイルへ書き出す（既存ファイルを指定すると上書き）
strata presets export "Office preset" --file ./office-preset.json

# 書き出したファイルを取り込む
strata presets import ./office-preset.json
```

`preset` は名前、完全な ID、または4文字以上の一意な ID prefix で検索されます。同じ名前が複数ある場合は名前検索が優先され、該当する preset が複数なら ID を使うようエラーになります。ID prefix も複数に一致するとエラーです。

## 主な動作と副作用

- preset を検索して、その内容を JSON 化します。標準出力へ表示する場合、整形済み JSON をそのまま出力して正常終了します。
- `--file PATH` を指定すると、UTF-8・インデント付き JSON を `PATH` に書き込みます。親ディレクトリは自動作成されません。`Path.write_text` による書き込みなので、同名ファイルがあれば置き換わります。
- 書き出すデータから `active` 状態のフィールドを除きます。preset の保存ファイルや active preset の index は export 処理では更新しません。
- `--file` を付けず `--output json` を指定した場合も、preset JSON を直接 stdout に出力します。ファイル指定時の `--output json` は、JSON 本文ではなく書き込み先を示す CLI 応答（`file` フィールド）を出力します。

## 注意点

preset が見つからない場合、または名前・ID prefix が複数の preset に一致する場合は失敗します。ファイル書き込みに失敗した場合もエラーになります。出力ファイルに既存データがあると上書きするため、未使用のパスを選んでください。

このコマンドは tuning preset の JSON を扱います。`strata launch --preset` の launch preset とは別のストアです。

## 関連文書

- [`strata presets` の概要](../README.md)
- [`strata presets import`](../import/README.md)
- [`strata tune auto`](../../tune/auto/README.md)
- [`--file`](--file.md)、[`--output`](--output.md)、[`--help` / `-h`](--help.md)
- [CLI 文書索引](../../../README.md)

## 根拠

- `strata_cli/tune_commands.py:49-55,73-76` — `presets` と `export` の parser 階層、必須位置引数 `preset`、`--file`、各 `presets` サブコマンド共通の `--output`。
- `strata_cli/cli.py:486-489,2151-2152` — `presets` parser の登録と実行時の dispatch。
- `strata_cli/tune_commands.py:331-347` — preset の取得、stdout/file の分岐、ファイル書き込み形式、エラー処理。
- `strata_cli/tune_commands.py:95-108` — human/JSON 応答とエラー時の表示・終了コード。
- `strata_control/presets.py:218-231` — 名前、ID、ID prefix の検索と未検出・複数一致時のエラー。
- `strata_control/presets.py:390-393` — export 対象から `active` を除く処理。
- `docs/cli/README.md:883-889` — `strata presets export` の階層と索引上の `--file`、`--output`、`--help`。
