# `--plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops set` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `false` |

## 役割

recipe の `KEY=VALUE` 変更案を型変換・検証し、保存せずに結果を表示します。recipe の種類に応じて受け付けるキーが異なります。`strata ops set` の parser は位置引数 `name`、必須の `--profile`、位置引数 `KEY=VALUE` を要求し、`--plan` を `store_true` で定義しています（`strata_cli/cli.py:255-275`）。

## 使い方

```sh
strata ops set restart startup_wait_s=180 --profile my-profile --plan
```

`--profile` は必須です。`--plan` を付けない呼び出しでは、検証済みの変更案を保存します（`strata_cli/cli.py:264-275, 1423-1430`）。

## 値と既定値

- `--plan` 自体に値はありません。未指定時は保存経路、指定時は提案表示経路を選びます（`strata_cli/cli.py:273-275, 1423-1430`）。
- `KEY=VALUE` は `=` で分割され、区切りがない値または空の値は拒否されます（`strata_control/recipes.py:278-282`）。
- `runtime.restart` は `startup_wait_s` を整数として読み、1〜600 の範囲で検証します（`strata_control/recipes.py:103-106, 278-288`）。
- `engine.calibrate.measure` は `report_dir` を受け付け、空でない絶対パスであること（NUL 文字を含まないこと）を検証します（`strata_control/recipes.py:107-111, 289-290`）。
- `components.verify` は `live=true` または `live=false` だけを受け付けます。値は小文字の文字列と完全一致し、JSON 真偽値に変換されます（`strata_control/recipes.py:112-113, 291-292`）。
- recipe の種類で許可されないキー、または上記以外の値は拒否されます。値を省略した場合の recipe パラメータ既定値は `ops create` が設定します（restart は `300`、calibration は profile ディレクトリ内の `.reports`、component verification は空の params。`strata_control/recipes.py:117-127`）。

## 実行時の動作

CLI はまず既存 recipe を読み込み、assignment を recipe 種別に応じて変換し、更新後の recipe 全体を検証します。その後 `--plan` が指定されていれば、元の recipe と提案を比較し、recipe、現在の revision、`would_save`（内容が変わるか）を成功結果として返します。この経路では `recipes.save` を呼びません（`strata_cli/cli.py:1423-1428`; `strata_control/recipes.py:278-296`）。

対象 profile と recipe が存在して読み取り・検証できる必要があります。recipe は profile ディレクトリ配下の `.ops/<profile>/<name>.json` に置かれ、profile と recipe 名は小文字英字・数字・`_`・`-` に制限されます（`strata_control/recipes.py:32-64, 180-196`）。

`--plan` を外すと、revision を照合してから保存します。変更がある場合は旧内容を履歴に退避し、新 recipe を atomic に書き換えます。同じ値を提案した場合は保存内容が同一のため revision は変わりません（`strata_control/recipes.py:214-237`）。したがって、`--plan` は recipe ファイルや履歴を更新しませんが、recipe/profile の読み取りと検証は行います。

`--output human` が既定値です。このコマンドは `human` 用の短い文面を渡さないため、既定では提案 payload を整形 JSON として標準出力へ表示します。`--output json` または同じ one-shot parser に追加される `--json` では、`schema_version` と `ok` を含む1行 JSON を出力します（`strata_cli/cli.py:508-515, 1423-1428, 535-542`）。`--quiet` は成功時の人間向け標準出力を抑え、失敗時は捕捉した出力を標準エラーへ出しますが、JSON 出力には適用されません（`strata_cli/cli.py:2232-2248`）。

## 適用条件と副作用

`--plan` は `_ops` の `set` 分岐だけに作用します。他の `strata ops` サブコマンドにこのフラグは登録されません（`strata_cli/cli.py:255-290`）。recipe を実行したり、サーバーを起動したり、recipe を書き換えたりする処理はこの分岐にありません（`strata_cli/cli.py:1423-1430`）。

`--plan` の指定有無にかかわらず `recipes.propose_value` までは実行されるため、recipe がない、JSON が壊れている、ファイル属性や権限が不適切、profile/name が不正、assignment が無効、といった場合は成功しません（`strata_control/recipes.py:32-64, 180-196, 278-296`）。

## 出力とエラー

成功時の終了コードは `0` です。失敗時は通常 `strata: <理由>` を標準エラーに出し、`ProfileError` の終了コードを返します。JSON 出力では `{ "schema_version": 1, "ok": false, "error": { "code", "message" } }` 形式です（`strata_cli/cli.py:527-542, 2166-2173`）。例えば assignment の形式・キー・値の問題や検証エラーは通常コード `2`、recipe が見つからない場合や読み取り拒否の一部はコード `5`、保存時の revision 競合はコード `6` ですが、`--plan` 経路では保存時競合チェックは行われません（`strata_control/recipes.py:180-196, 278-296`; `strata_cli/cli.py:1423-1430`）。

## 根拠

- parser、必須引数、フラグ定義: `strata_cli/cli.py:255-275`
- `--json` / `--quiet` の追加と出力形式: `strata_cli/cli.py:508-515, 527-542, 2232-2248`
- `--plan` と通常保存の分岐: `strata_cli/cli.py:1391-1430`
- assignment の型変換と validation: `strata_control/recipes.py:93-127, 278-296`
- recipe の配置、読み込み、revision、保存・履歴副作用: `strata_control/recipes.py:32-64, 180-196, 214-237`
