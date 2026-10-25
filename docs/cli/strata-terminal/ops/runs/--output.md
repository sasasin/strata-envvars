# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops runs` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力を選ぶ同一スコープの shortcut） |
| 値 | `human` または `json` |

## 役割

プロフィールに記録された operation run の一覧を、人向けの行表示または機械処理向けの JSON として出力します。このコマンドは journal を読み取るだけで、operation を実行しません（`strata_cli/cli.py:1404-1408`、`strata_control/journal.py:254-273`）。

## 使い方

```sh
strata ops runs --profile four-gpu --limit 20 --output json
```

人向け表示が必要なら `--output human` を指定するか、`--output` を省略します。`--json` は `--output json` と同じ出力モードです（`strata_cli/cli.py:266-269, 512-515, 2232-2235`）。

## 値と既定値

- `--output` は `human` または `json` のみを受け付け、既定値は `human` です。値の省略、選択肢外の値は `argparse` が拒否します（`strata_cli/cli.py:266-267`）。
- `--json` は共通 one-shot parser 群へ追加される真偽値 option です。指定時、メイン dispatch が `a.output` を `json` にします（`strata_cli/cli.py:510-515, 2232-2235`）。
- 同じ `--output` を複数回指定した場合の専用規則はありません。`argparse` の通常の単一値 option として解析されます。
- `--profile` は必須です。併設される `--limit` は整数で既定値 `20`、実際に受理される範囲は `1..100` です（`strata_cli/cli.py:266-269`、`strata_control/journal.py:254-256`）。

## 実行時の動作

- handler は `--output json` を machine mode として扱い、`journal.list_runs(profile, limit=...)` の結果を `profile` と `runs` のフィールドに載せます（`strata_cli/cli.py:1391-1394, 1404-1408`）。
- JSON 成功時は stdout に `schema_version: 1` と `ok: true` を含む object を1つ出力します。`runs` は新しい更新時刻の記録から最大 `--limit` 件で、各項目には operation ID、recipe、origin、kind、state、開始・終了時刻、実行完了未確認フラグが含まれます。壊れた記録は一覧全体を止めず、該当 ID と `error` を持つ項目になります（`strata_cli/cli.py:535-542, 1404-1408`、`strata_control/journal.py:260-273`）。
- human mode は各記録について `operation_id` と `state`（なければ `error`）を1行に表示し、空の場合は `No operation runs recorded` と表示します（`strata_cli/cli.py:1406-1408`）。
- `completion_unverified: true` は記録状態が `running` の場合に付与されます。呼び出し元の異常終了後などに実際の処理が完了したか分からないことを示し、処理が現在も実行中である証明ではありません（`strata_control/journal.py:1-5, 263-270`）。

## 適用条件と副作用

- 一覧対象は指定 profile の `.runs` journal directory にある、32桁小文字16進 ID の `*.json` ファイルです。ファイルの更新時刻の降順で上限件数まで読み込みます（`strata_control/journal.py:47-63, 254-273`）。
- `--output` は表示形式だけを切り替えます。`ops runs` handler は journal の一覧取得と出力を行い、実行・記録の作成や削除はしません（`strata_cli/cli.py:1404-1408`、`strata_control/journal.py:254-273`）。
- journal directory が symlink である場合は拒否されます。POSIX では directory が owner-only でない場合も拒否されます（`strata_control/journal.py:47-57`）。

## 出力とエラー

- `--output json` または `--json` の成功結果は stdout の JSON object です。エラー時も対応する処理例外は `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON を stdout に出し、エラーコードを終了コードとして返します（`strata_cli/cli.py:527-542, 2166-2188`）。
- `--limit` が `1..100` の範囲外なら `ProfileError` となり、メッセージは `operation list limit must be 1..100` です（`strata_control/journal.py:254-256`）。`--profile` の解決、directory の検査やファイル読み込みで起きる `ValueError` / `OSError` も `_run` の例外経路でエラーになります（`strata_cli/cli.py:2119-2125, 2166-2188`）。
- 必須値不足、値の型違い・選択肢外、未知 option など parser 段階の引数エラーは `argparse` が usage とエラーを stderr に表示して終了コード `2` を返します（parser 定義 `strata_cli/cli.py:266-269`、呼び出し `strata_cli/cli.py:2223-2231`）。
- `--output json` のエラー JSON を受け取るには、parser を通過して dispatch される引数が必要です。parser 自身の引数エラーは machine envelope にはなりません。

## 根拠

- `strata_cli/cli.py:255-269` — `ops runs` parser、必須 profile、output の選択肢と既定値、limit。
- `strata_cli/cli.py:510-515, 2232-2237` — `--json` / `--quiet` の共通追加と `--json` から output mode への変換。
- `strata_cli/cli.py:527-542, 1391-1408` — human / JSON envelope と `runs` の dispatch・表示。
- `strata_cli/cli.py:2119-2125, 2166-2188, 2223-2231` — dispatch、処理例外と parser エラー経路。
- `strata_control/journal.py:47-63, 254-273` — journal directory 検査、limit 検証、一覧取得と項目構造。
