# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection list` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | なし。指定すると真になるフラグ。既定値は `false`。 |

## 役割

接続一覧を人向け形式で標準出力に表示しないためのフラグです。コマンドの読み取り処理や終了コードには影響しません。

## 使い方

```sh
strata connection list --quiet
```

JSON を出力する場合は `--quiet` を付けても JSON は抑制されません。

```sh
strata connection list --json --quiet
```

## 値と既定値

値や別名はありません。parser は `action="store_true"` で定義しており、未指定なら `false`、指定時は `true` です。値の validation はありません。`--output` は `human` または `json` を受け取り既定値は `human`、`--json` は JSON 出力の alias です。これらは同じ list parser に追加されています（`strata_cli/monitor_commands.py:85-95`）。

## 実行時の動作

list は接続レコードを読み出し、成功時は `connections` 配列を含む payload を組み立てます。通常の人向け出力では `schema_version` と `ok` を除いた payload を整形して stdout に出します（`strata_cli/monitor_commands.py:140-144,162-164`）。

`run()` は `--quiet` が指定され、かつ machine output でない場合に限り、connection/config の `_local_command()` が書く stdout を `StringIO` にリダイレクトします。このため人向け一覧の表示は抑制されます（`strata_cli/monitor_commands.py:167-175`）。一覧取得自体は通常どおり実行されます。接続ディレクトリがない場合は空配列を返し、JSON/JSONL 出力では通常どおり結果を標準出力へ出すため、`--quiet` は機械可読出力を隠しません（`strata_cli/connections.py:149-164`、`strata_cli/monitor_commands.py:167-175`）。

## 適用条件と副作用

このオプションは `strata connection` の create、show、list、set の parser に共通して追加されていますが、本書の対象は list です（`strata_cli/monitor_commands.py:75-95`）。list は接続ディレクトリ内の `*.json` のうち名前規則に一致するファイルをソートして読み取ります。接続設定の作成・変更・削除やネットワーク接続は行いません（`strata_cli/connections.py:149-164`）。

## 出力とエラー

人向け出力の stdout は抑制されます。`--output json` または `--json` と併用した場合は machine mode となり、quiet 抑制の対象外です（`strata_cli/monitor_commands.py:167-175`）。

失敗時の `_error()` は人向けエラーを stderr に書くため、quiet でも通常の例外診断は残ります。`ConnectionError` は保持された exit code で返され、`OSError` は code 6、`ValueError` は code 2 になります（`strata_cli/monitor_commands.py:124-129,231-240`）。100件を超える候補レコードがある場合は `connections.list_connections()` が code 5 の `ConnectionError` を発生させます（`strata_cli/connections.py:149-156`）。個々の不正レコードは一覧中の `error` 項目に変換され、コマンド全体の失敗にはなりません。その項目は人向け stdout の一部なので、quiet では表示されません（`strata_cli/connections.py:157-164`）。

## 根拠

- `strata_cli/monitor_commands.py:75-95` — connection サブコマンドと list 向けの option 定義。
- `strata_cli/monitor_commands.py:140-164` — 一覧 payload と出力。
- `strata_cli/monitor_commands.py:167-175` — machine mode 判定と quiet 時の stdout 抑制。
- `strata_cli/monitor_commands.py:124-129,231-240` — stderr エラーと終了コードの経路。
- `strata_cli/connections.py:149-164` — ディレクトリ未作成時、候補の列挙、100件上限、個別レコードエラーの扱い。
