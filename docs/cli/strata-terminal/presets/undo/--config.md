# `strata presets undo --config`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets undo` |
| オプション | `--config` |
| 別名 | なし |
| 値 | プロファイル名、または run configuration のパス。値は1つの文字列。 |

## 役割

undo の対象を preset ID/name から直接選ぶ代わりに、指定した profile または run configuration から preset slot を特定します。その slot の undo 履歴を1段戻し、以前の preset を有効化します。現在の preset が有効で履歴が尽きている場合は標準設定に戻し、undo するものがない場合はエラーになります。位置引数 `preset` は parser 上必須ですが、`--config` が空でない場合の処理では使われません。

## 使い方

```sh
# 保存済み profile が属する slot を1段 undo する
strata presets undo ignored --config coding

# run configuration のパスから slot を特定して undo する
strata presets undo ignored --config ./strata-model.json
```

`ignored` は必須位置引数を満たす例示値です。`--config` 分岐ではこの値は参照されません。変更内容を表示するだけの dry-run はありません。

## 値と既定値

`--config` は `default=None` で、省略時は従来どおり位置引数 `preset` を slot または preset 参照として undo に渡します。parser に `choices`、型変換、独自 validation はありません（`terminal/strata_cli/tune_commands.py:76-78`）。値が空文字列の場合も `if a.config` が偽となるため、省略時と同じく位置引数側の分岐になります（同 `:504-510`）。

`--config` に値を与えると `_load_target` が対象を解決します。`.json` 拡張子、絶対パス、既存パスは run configuration として読み込みます。プロファイル名は保存 profile の source configuration を読み込みます（`terminal/strata_cli/tune_commands.py:117-140`、`terminal/strata_control/profiles.py:400-406`）。説明上は profile 名または run configuration ですが、現行 `_load_target` はそれらに該当しない名前をインストール済みモデル名としても解決します（`terminal/strata_cli/tune_commands.py:125-140`）。

## 実行時の動作

1. 設定を読み、`presets.current_identity` と `presets.choices_from_config` から現在のモデル識別子と設定上の選択値を得ます（`terminal/strata_cli/tune_commands.py:504-508`）。run configuration は JSON として読み、`args` が文字列配列、`exe` と `tokenizer` が空でない文字列であることを検証します（`terminal/strata_control/profiles.py:135-150`）。
2. slot key はモデルファイルの `sha256_shard1` と context、KV 形式、vision の有無、goal から計算されます（`terminal/strata_control/presets.py:89-117,128-131`）。これにより、`--config` はその設定と同じ slot の undo 履歴を選びます。
3. `presets.undo(slot)` が履歴の末尾を取り出し、有効 preset を以前の ID に戻します。履歴がなくても現在の preset が有効なら `active` を `None` にして標準設定へ戻します。一方、履歴も有効 preset もない場合は「there is nothing to undo」エラーです。以前の preset ファイルが存在しない場合も `active` は `None` になります（`terminal/strata_control/presets.py:366-385`）。
4. undo は preset 適用値を run configuration/profile に書き込まず、モデルや engine も起動しません。preset store の `active.json` を更新します。store は `STRATA_PRESET_DIR` があればそのディレクトリ、なければ profile directory の親にある `presets/` です（`terminal/strata_control/presets.py:45-50,232-234,378-385`）。

同じ `strata presets undo` の `--output` は `human` / `json` を選び、既定は `human` です（`terminal/strata_cli/tune_commands.py:59-61,475-476`）。

## 適用条件と副作用

`--config` は profile/run configuration の内容から slot を決めるため、ファイルの読み込みと profile の解決が必要です。設定に由来する slot がアクティブ履歴に存在しない場合は undo 失敗になります。指定した config や profile 自体は変更せず、preset store の `active.json` のみを書き換えます。履歴中の preset ファイルが欠落しているときは、その ID を有効化せず標準設定へ戻します（`terminal/strata_control/presets.py:373-385`）。

## 出力とエラー

成功時は人向け出力で `Back to '<preset name>'.` または `Back to the standard settings.` を表示します。`--output json` では `active` に復帰した preset の概要、または `null` を含む JSON を stdout に出します（`terminal/strata_cli/tune_commands.py:101-106,504-513`）。

undo できる履歴がない場合は `PresetError("there is nothing to undo")` です。通常出力では `strata: ...` を stderr に出して終了コード 5、JSON 出力では `ok:false` と error を stdout に出します（`terminal/strata_control/presets.py:373-375`、`terminal/strata_cli/tune_commands.py:109-114,527-530`）。設定の読み込み失敗や無効な run configuration もエラーになります。`ProfileError` は既定の終了コード 2（読み込み失敗時は 5）を持ち、handler はそのコードを使います（`terminal/strata_control/profiles.py:30-35,135-150`、`terminal/strata_cli/tune_commands.py:529-530`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-78` — `presets undo` parser と `--config` の既定値・ヘルプ。
- `terminal/strata_cli/tune_commands.py:117-140,472-475,504-530` — config 解決、undo 分岐、出力と例外処理。
- `terminal/strata_control/profiles.py:30-35,135-150,400-406` — profile error の終了コード、run configuration 検証、profile/path 解決。
- `terminal/strata_control/presets.py:45-50,89-117,128-131,162-182,232-239,366-385` — store の場所、slot の構成、identity、履歴の復元と永続化。
