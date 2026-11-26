# `strata presets import --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets import` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

import の結果を人向けの短いメッセージか、機械処理向け JSON で標準出力に表示します。読み込むファイルの指定やインポート内容は変更せず、出力形式だけを選びます。

## 使い方

```sh
# JSON プリセットを読み込み、結果を JSON で受け取る
strata presets import ./preset.json --output json
```

## 値と既定値

`human` / `json` の二択で、省略時は `human` です。値は `argparse` の `choices` で制限されており、それ以外は引数エラーになります。別名や `--json` はこのサブコマンドの parser には登録されていません。共通登録関数が `presets` の各子コマンドにこの引数を追加します（`terminal/strata_cli/tune_commands.py:59-61,82-83`）。

## 実行時の動作

オプションを省略するか `human` を指定すると、インポート成功時に `Imported '<名前>'. Apply it with: strata presets apply <ID>` を標準出力へ表示します。`json` では `schema_version: 1` と `ok: true` に、インポートしたプリセットの要約を含めた JSON を標準出力へ出します（`terminal/strata_cli/tune_commands.py:101-106,521-524`）。

出力形式にかかわらず、位置引数のファイルを UTF-8-SIG として読み、JSON を解析して `import_preset` に渡します。ルートは `strata.preset/1` schema のオブジェクトである必要があり、設定値は tuner の安全規則で検査されます。安全規則に該当する値があれば拒否しますが、測定範囲外というだけの値は保持されます（`terminal/strata_cli/tune_commands.py:521-524`、`terminal/strata_control/presets.py:423-438`、`terminal/strata_control/tune_knobs.py:275-279,333-347`）。

受理されたプリセットは新しい UUID と一意な名前を割り当てられ、プリセット保存先に JSON として書かれます。名前が既存名と重なる場合は ` (2)` などの番号が付きます。保存処理は一時ファイルを経由して置き換えます。import 自体はプリセットを有効化せず、成功メッセージも別途 `strata presets apply` を案内します（`terminal/strata_control/presets.py:45-50,53-68,284-290,423-438`）。

## 適用条件と副作用

このオプションは `presets import` に限らず、`presets` の各子コマンドに共通して登録されています。ファイルの読み込み・検証・保存は import の処理によるもので、`--output` 自体はそれらを切り替えません。保存先は `STRATA_PRESET_DIR` があればその値（`~` を展開）、なければ profile ディレクトリの隣の `presets` です（`terminal/strata_control/presets.py:45-50`）。

## 出力とエラー

成功時は前述の人向けテキストまたは JSON を標準出力に出し、終了コード `0` を返します。プリセットの schema 不一致や安全規則違反など `PresetError` は、human では `strata: <説明>` を標準エラーへ出し終了コード `5`、JSON では `schema_version: 1, ok: false, error: {code, message}` を標準出力へ出し終了コード `5` です。ファイル読み込み時の `OSError`、JSON 解析時の `ValueError` は同じ出力形式で終了コード `2` になります（`terminal/strata_cli/tune_commands.py:109-114,521-530`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-61,82-83` — `--output` の値・既定値と、import parser への適用。
- `terminal/strata_cli/tune_commands.py:101-114,472-476,521-530` — 成功・エラー出力形式、import 実行、失敗時の終了コード。
- `terminal/strata_control/presets.py:45-68,284-290,423-438` — 保存先、ファイル書き込み、名前の重複処理、schema・設定検証と新規プリセット保存。
- `terminal/strata_control/tune_knobs.py:275-279,333-347` — 拒否される安全規則と、測定範囲外値の扱い。
