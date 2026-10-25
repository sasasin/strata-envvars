# `--output`（`strata presets off`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets off` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

チューニング preset を指定対象の選択枠で無効化する操作について、成功時・失敗時の表示形式を選びます。`human` は人向けの短いメッセージ、`json` は `schema_version` と `ok` を含む JSON を標準出力に出します。無効化の対象や保存処理は変えません。

## 使い方

```sh
# 既定の人向け表示
strata presets off "Office profile"

# JSON で結果を受け取る
strata presets off "Office profile" --output json
```

位置引数 `target` は保存済み profile 名、または run configuration の JSON パスです。コマンドの説明と parser は `strata_cli/tune_commands.py:80-81`、共通 `--output` の定義は同ファイル `:53-55` にあります。

## 値と既定値

- `human`: 省略時の既定値です。成功時に `Back to the standard settings. Your tuning is kept and can be switched on again.` を表示します。
- `json`: 成功時は `{"schema_version":1,"ok":true,"active":null}` 形式の JSON を出力します。
- それ以外の値は `argparse` の選択肢検証で拒否されます。値は必須で、`--output` だけを指定して引数を省くこともできません。
- `--json` はこの parser の alias ではありません。`--output` だけが定義されています。

定義と出力形式の分岐は `strata_cli/tune_commands.py:53-55,95-100`、成功時の payload と人向け文言は同ファイル `:381-388` を参照してください。

## 実行時の動作

`--output` の値から `machine` を決め、成功・エラーの出力形式を切り替えます。実際の無効化処理では `target` から run configuration を読み、モデル・context・KV 形式・vision・goal などから選択枠を特定し、その枠の active preset を解除します。同じ設定の開始時に保存済みチューニング値が適用されなくなり、標準設定に戻ります。対象の preset データ自体は削除されず、再度有効化できます。

選択枠は run configuration 由来の選択値とモデルファイルの digest から作られます。従って、同じ profile 名を使う場合でも、別の設定やモデル digest に対応する枠の active 状態には作用しません（`strata_cli/tune_commands.py:381-388`; `strata_control/presets.py:89-117,128-131,329-337`）。通常の起動時には active preset がその枠で参照されます（同 `:441-479`）。

## 適用条件と副作用

- `target` を解決して対応する run configuration を読み込めることが必要です。profile 名は保存 profile の source config に解決され、JSON パス等の path-like な値は直接の設定ファイルとして扱われます（`strata_control/profiles.py:382-388`）。
- 選択枠に active preset がある場合、active ID を `active.json` の履歴へ追加し、active を `null` にして index を保存します。無効化を繰り返し、すでに active がない場合は index を変更しません（`strata_control/presets.py:329-337`）。index は preset store の `active.json` に保存されます。同 `:45-50,202-208`。
- preset store の場所は `STRATA_PRESET_DIR` が設定されていればその値、未設定なら profile directory の隣の `presets` です（`strata_control/presets.py:45-50`）。
- この操作は再測定、preset 削除、profile の書き換えを行いません。`--output` は表示だけを切り替え、無効化の対象・副作用を変えません。

## 出力とエラー

成功時は終了コード `0` です。`human` は標準出力に一行のメッセージ、`json` は成功オブジェクトを出力します（`strata_cli/tune_commands.py:95-100,381-388`）。

PresetError は `strata: <message>` を標準エラー（human）または `{"schema_version":1,"ok":false,"error":{"code":5,"message":"..."}}`（JSON）に出し、終了コード `5` になります。その他の `OSError` / `ValueError` も同じ分岐で報告され、例外の `exit_code` があればそれを、なければ `2` を使います（同 `:103-108,344-347`）。profile/run config の読込失敗は `ProfileError` となり、run config の読込時には code `5` が設定されます（`strata_control/profiles.py:135-147`）。

値が `human` / `json` 以外、または必須位置引数が不足している場合は、コマンド本体に入る前に argparse が usage とエラーを標準エラーへ出して終了コード `2` で終了します。parser の choices は `strata_cli/tune_commands.py:53-55`、トップレベル parser は `strata_cli/cli.py:40-45` で確認しました。

## 根拠

- `strata_cli/tune_commands.py:49-55,80-81` — `presets off` と `target`、共通 `--output` の parser 定義。
- `strata_cli/tune_commands.py:95-108,289-306,344-347,381-388` — JSON / human の成功・失敗形式、`off` の dispatch と動作。
- `strata_control/profiles.py:135-147,382-388` — target から run configuration への解決と読込検証。
- `strata_control/presets.py:45-50,89-117,128-131,202-208,329-337,441-479` — store location、選択枠の識別、active index の保存と preset 適用。

調査は上記 commit の checkout に含まれるソースで行いました。別 platform の実行環境や Release 配布物での help 表示は確認していません。
