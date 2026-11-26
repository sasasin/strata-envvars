# `strata presets off --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets off` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

切り替え対象の出力形式を指定します。`strata presets off` は対象設定に対応する tuning preset を無効化して標準設定に戻しますが、`--output` はその処理結果の表示形式だけを選び、無効化の対象や状態変更は変えません。

## 使い方

```sh
# 人が読むメッセージを表示（既定値）
strata presets off my-profile

# スクリプトから扱える JSON を出力
strata presets off ./run-config.json --output json
```

`target` には保存済み profile 名、run configuration の JSON パス、または一致するインストール済みモデル名を指定できます。

## 値と既定値

- `human`: 既定値です。成功時は `Back to the standard settings. Your tuning is kept and can be switched on again.` を標準出力に表示します。
- `json`: 成功時は `{"schema_version": 1, "ok": true, "active": null}` を標準出力に出します。
- 値は必須です。`choices=("human", "json")` にない値は parser が受け付けません。短縮別名はありません。

## 実行時の動作

`--output` は `strata presets` の各サブコマンドに共通登録されます。`off` の parser にも同じ `human` / `json` と既定値 `human` が適用されます。コマンド実行時は `--output json` かを判定し、対象を読み込んで現在の hardware/model identity と設定から choices を求め、その組み合わせに対応する slot を無効化します。無効化後の成功応答は常に `active: null` です。

有効な preset がその slot で現在 active の場合、active ID を履歴に積み、active を null にして preset index を保存します。preset 本体は削除されないため、後から再び有効化できます。slot に active preset がなければ index は変更されませんが、成功メッセージ／JSON は同様に返ります。したがって `--output` の指定による保存先や副作用の差はありません。

## 適用条件と副作用

`--output` は `presets off` に限らず `presets` の `list`、`status`、`show`、`apply`、`rename`、`delete`、`undo`、`export`、`import`、`effective`、`recheck` に共通です。この文書ではそのうち `off` 実行時の形式だけを扱います。

`off` はモデル起動を行いません。対象の解決と identity 計算では設定ファイル、engine manifest、モデルファイルの一部、hardware 情報を読み取ります。保存変更が発生する場合は preset データではなく preset フォルダーの `active.json` のみで、atomic write により更新されます。既定の preset フォルダーは profile フォルダーの隣で、`STRATA_PRESET_DIR` が設定されていればそのパスが使われます。

## 出力とエラー

- 成功時は選択した形式で標準出力に出し、終了コード `0` を返します。
- `PresetError` は `presets_command` で捕捉され、human 形式では `strata: <message>` を標準エラーに、JSON 形式では `{"schema_version": 1, "ok": false, "error": {"code": 5, "message": "..."}}` 形式を標準出力に出します。
- `PresetError` 以外の `ValueError` / `OSError` は `presets_command` 側で捕捉され、形式に応じて human / JSON error envelope で報告されます。run config の読込失敗は `ProfileError` の code `5`、例外側に `exit_code` がないファイル操作エラーは code `2` です。
- 不正な `--output` 値や `target` の欠落は parser の入力検証で拒否され、コマンド処理には進みません。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-61` — presets 各 subcommand に共通の `--output` parser 定義、選択肢と既定値。
- `terminal/strata_cli/tune_commands.py:86-87` — `off` の登録と必須 `target`。
- `terminal/strata_cli/cli.py:515`、`terminal/strata_cli/cli.py:2229-2230` — presets parser の登録と処理関数への dispatch。
- `terminal/strata_cli/tune_commands.py:472-477`、`terminal/strata_cli/tune_commands.py:585-592` — JSON 形式の選択、target identity/slot の算出、deactivate 呼び出しと成功応答。
- `terminal/strata_control/presets.py:89-117`、`terminal/strata_control/presets.py:128-131` — 設定から choices を作り slot key を求める規則。
- `terminal/strata_control/presets.py:162-182`、`terminal/strata_control/tune_machine.py:264-277`、`terminal/strata_control/tune_machine.py:299-309` — 対象 identity の読み取り元（hardware、engine、model）。
- `terminal/strata_control/presets.py:356-364`、`terminal/strata_control/presets.py:227-233`、`terminal/strata_control/presets.py:45-50` — active preset を履歴に保持して無効化する処理、index の保存先。
- `terminal/strata_control/presets.py:53-68` — preset index の atomic write。
- `terminal/strata_cli/tune_commands.py:101-114`、`terminal/strata_cli/tune_commands.py:527-530`、`terminal/strata_cli/cli.py:2248-2265` — 成功出力と失敗時の human / JSON 出力、終了コード処理。
- `terminal/strata_cli/tune_commands.py:117-140`、`terminal/strata_control/profiles.py:135-150` — target の解決と run config の読込・形式検証。
