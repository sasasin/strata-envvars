# `strata tune apply --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune apply` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

適用結果と、処理中に検出したエラーの出力形式を選びます。`human` は人向けの説明、`json` は機械処理向けの JSON を標準出力に出します。このオプションは表示形式だけを変え、適用処理の実行・設定ファイルへの書き込みを抑止しません。

## 使い方

```sh
strata tune apply <job-id> --output json
```

`<job-id>` は完了した sweep の ID です。設定ファイルに推奨値を適用するコマンドなので、`--output json` を付けてもプレビューにはなりません。適用前の確認には `strata tune status <job-id>` を使います（parser と適用処理の定義: `strata_cli/cli.py:461-470, 1708-1712`）。

## 値と既定値

- parser は `human` と `json` のみを受理し、省略時は `human` です（`strata_cli/cli.py:470`）。値は位置引数で一つ指定します。
- 未知の値や値の省略は `argparse` の引数エラーになります。CLI は `parse_known_args` で解析し、残った余分な引数は parser のエラー経路に送ります（`strata_cli/cli.py:2217-2231`）。
- 短縮別名はありません。

## 実行時の動作

正常終了時は終了コード `0` です。`human`（既定）では適用した設定パス、追加・削除された引数、適用前後の SHA-256 の先頭 16 桁、rollback コマンドを表示し、続けて現在の CLI 実装では候補が実モデルに対して未検証であることを表示します（`strata_cli/cli.py:1907-1921`）。`json` では `_success` が `schema_version: 1`、`ok: true` と適用結果を含む JSON オブジェクトを一行で標準出力へ出します（`strata_cli/cli.py:1907-1908, 535-542`）。

処理上のエラーは `human` なら `strata: ...` の形式で標準エラーへ、`json` なら `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON を標準出力へ出します。たとえば job が見つからない、設定ファイルが見つからない、sweep に model digest がない、identity を再導出できない、適用判定が拒否された場合にこの経路を通ります（`strata_cli/cli.py:1859-1866, 1883-1905, 527-533`）。

## 適用条件と副作用

`--output` の値は表示経路の選択に使われ、job・設定の探索や適用可否の判定には使われません。どちらの値でも、処理が成功すれば推奨値を run config に反映し、適用前の設定と候補、適用記録を state directory 配下に保存します。設定ファイルは一時ファイル経由の atomic replace で更新されます（`strata_cli/cli.py:1900-1916`; `strata_control/tune_apply.py:343-370, 62-73`）。以前の bytes は application record に関連付けられ、成功表示に示される ID を `strata tune rollback` に渡して復元できます。

現在の CLI は `apply_recommendation(..., verify=None)` を呼び出します。そのため、`strata_control/tune_apply.py` が提供する任意の実行検証 callback はこの経路では指定されず、設定を書き換える前の実モデル起動・token 生成確認はありません。human 成功表示も「実行中のモデルで検証されていない」と警告します。`--output json` はこの状態やファイル変更を変えません（`strata_cli/cli.py:1900-1920`; callback が指定された場合の検証条件: `strata_control/tune_apply.py:306-337`）。

## 出力とエラー

- `human` 成功: 適用先、差分、rollback ID、未検証の注意を標準出力へ出し、終了コード `0`。
- `json` 成功: `_success` の成功 JSON を標準出力へ出し、終了コード `0`。
- 実行時エラー: `human` は標準エラー、`json` はエラー JSON を標準出力へ出し、各エラーで指定された非ゼロ終了コードを返します。job/config/identity 関連の早期拒否はコード `2`、`ApplyError` は例外の `code`（既定値 `6`）です（`strata_cli/cli.py:1861-1905`; `strata_control/tune_apply.py:50-55`）。
- parser エラーは `argparse` の usage/error 表示経路です。ソースでは `parse_known_args` 後の余分な引数を `ap.error` に渡します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:461-470` — `tune apply` parser と `--output` の選択肢・既定値。
- `strata_cli/cli.py:1850-1921` — apply の job/config/identity 判定、出力分岐、終了コード、CLI から `verify=None` を渡す箇所。
- `strata_cli/cli.py:527-542, 2217-2231` — human/JSON の成功・エラー出力と parser エラー経路。
- `strata_control/tune_apply.py:50-55, 306-370` — 適用拒否、任意検証 callback、設定・記録の書き込み。
- `strata_control/tune_apply.py:62-73` — atomic write。
