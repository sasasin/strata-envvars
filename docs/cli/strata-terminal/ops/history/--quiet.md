# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops history` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時に真 |

## 役割

成功時の人間向け標準出力を抑制します。`ops history` が列挙する履歴の取得自体は通常どおり行われます。`--output json`（または `--json`）を併用すると機械可読出力を優先するため、JSON は抑制されません。

## 使い方

```sh
strata ops history my-recipe --profile my-profile --quiet
```

JSON 出力を選ぶ場合:

```sh
strata ops history my-recipe --profile my-profile --quiet --output json
```

## 値と既定値

値を取らない `store_true` フラグで、明示しない場合は `argparse.SUPPRESS` により属性自体が省略されます。実行時には `getattr(..., False)` として扱われ、実質的な既定値は無効です。値を後置する形式は定義されていません。別名はありません。

## 実行時の動作

`ops history` の parser は `--profile` を必須とし、`--output` は `human` / `json` を受け付け、既定値は `human` です。共通 one-shot parser 追加処理がこのサブコマンドにも `--quiet` と `--json` を登録します。履歴処理は `recipes.history(profile, name)` を呼び、現在 revision を先頭に、その後に保存済み revision を保存時刻の降順で返します。

quiet はコマンド実行前に標準出力を捕捉し、終了コード 0 の場合は出力を表示しません。human 出力が空でもエラーにはなりません。`--output json` または `--json` では quiet より出力形式が優先され、JSON を通常どおり標準出力へ出します。履歴参照は読み取り処理で、このオプションによるファイル変更はありません。

## 適用条件と副作用

このフラグは one-shot CLI parser 群にのみ追加され、`strata ops history` で利用できます。値検証や履歴取得の条件を変更せず、成功時の human 標準出力だけを隠します。コマンドが非ゼロで終了し、捕捉した標準出力に内容がある場合は、その内容を標準エラーへ出して診断を残します。捕捉内容が上限を超えて切り詰められた場合は、標準エラーに省略を知らせる文言も出します。

## 出力とエラー

quiet なしの human 出力は各履歴行の revision と `current` / `saved` 表示です。履歴がない場合は空文字列となり、成功時は何も出力しません。JSON モードは `schema_version: 1`、`ok: true`、profile、recipe、history を含む JSON を出します。

対象 recipe が見つからない、または読み取れない場合など、実行時例外は CLI の共通処理でエラー化され、human モードでは `strata: ...` を標準エラーへ出して非ゼロ終了します。quiet はこの標準エラーを抑止しません。引数不足・不正な引数は argparse の parser エラーです。

## 根拠

- `strata_cli/cli.py:255-267` — `ops` のサブコマンド parser、`history` に必要な `name`、必須 `--profile`、出力形式と既定値。
- `strata_cli/cli.py:508-515` — one-shot parser 群に `--json` と `--quiet` を追加。quiet の型と既定処理。
- `strata_cli/cli.py:1431-1435` — `ops history` の実処理、human 出力。
- `strata_cli/cli.py:2232-2248` — JSON 選択と quiet の優先関係、標準出力捕捉、失敗時の再出力。
- `strata_cli/cli.py:527-540` — 共通エラーの標準エラー出力と成功時 JSON / human 出力。
- `strata_cli/cli.py:2166-2188` — `ValueError`、`OSError`、`ClientError` 等の失敗を終了コード付きで処理。
- `strata_control/recipes.py:180-196` — recipe 読み込み、欠落・読み取り失敗時のエラー。
- `strata_control/recipes.py:240-250` — 現在 revision と保存済み履歴の構成、並び順。
