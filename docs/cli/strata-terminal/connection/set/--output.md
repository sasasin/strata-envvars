# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection set` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力） |
| 値 | `human` または `json` |

## 役割

接続設定を表示する形式を選びます。`human` は整形した JSON オブジェクト、`json` は `schema_version` と `ok` を含む機械可読 JSON を標準出力に出します。名前、代入値、保存処理の意味は変えません。

## 使い方

```sh
strata connection set local prefix=/strata --output json --plan
strata connection set local prefix=/strata --output human
```

1つ目は変更案を表示し、保存しません。2つ目は設定を保存します。既存の接続名 `local` が必要です。

## 値と既定値

`--output` は `human` / `json` のみを受理し、省略時は `human` です。別名 `--json` は `--output json` と同じ出力形式を選びます。無効な値は `argparse` が引数エラーとして拒否します。複数回指定した場合の parser の動作は通常の `argparse` の単一値引数に従い、最後に指定した `--output` の値になります（`--json` は独立した真偽値で、指定されると JSON 出力になります）。

## 実行時の動作

`strata connection set` は `KEY=VALUE` 形式の代入を一つ受け取ります。`--output` の値が `json`、または `--json` が指定されていると machine 出力になります。変更案は `strata_cli.connections.propose()` で読み込み・検証されます。`--plan` がなければ `save()` が設定ファイルを更新します。出力選択はこの処理分岐や保存結果に影響しません。

併用する `--quiet` は人間向け出力を抑制します。machine 出力のときは `quiet` が無効扱いになるため、`--quiet --output json` でも JSON が出力されます。

成功時は、JSON 形式では `{"schema_version":1,"ok":true,...}` として接続値と revision を出力します。`--plan` のときは `would_save` を含み、実保存時は `previous_revision` と新しい `revision` を含みます。`human` 形式では同じ payload から `schema_version` / `ok` を除き、整形して出力します。JSON 出力では `ensure_ascii=False` です。

## 適用条件と副作用

この設定変更はローカルの接続記録に対する処理で、接続先サーバーへのリクエストは行いません。記録先は `STRATA_CONNECTION_DIR` が設定されていればその絶対パス、Windows では `%APPDATA%/Strata/connections`（未設定時はホーム下の既定値）、それ以外では `$XDG_CONFIG_HOME/strata/connections`（未設定時は `~/.config/strata/connections`）です。実保存時は接続記録をロックし、値が変わった場合に一時ファイルから置換します。`--plan` は保存を呼ばず、ファイルを変更しません。

値の検証や同時変更の検出は `--output` に関係なく適用されます。`--if-revision REVISION` を指定すると、読み込んだ revision が一致しない場合に保存前に失敗します。値が現在値と同じ場合、保存処理はファイルを書き換えず現在の revision を返します。

## 出力とエラー

`--output json` または `--json` の場合、処理エラーも標準出力に `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` として出力します。`human` では `strata: <message>` を標準エラーに出します。確認できた主な終了コードは、引数・代入値の不正が `2`、接続記録の欠落・不正・権限条件などが `5`、revision の競合が `6`、ローカルファイル操作の `OSError` が `6` です。無効な `--output` は parser のエラーで、コマンド処理には入りません。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection set` の parser 定義、`--output` の選択肢・既定値、`--json` alias、および `--plan` / `--if-revision`。
- `strata_cli/monitor_commands.py:124-164` — エラー表示形式、提案・revision 確認・plan/保存の分岐、成功 payload の出力。
- `strata_cli/monitor_commands.py:167-175,231-240` — JSON mode の決定、connection command の実行、例外と終了コードの変換。
- `strata_cli/monitor_commands.py:91-94,168-175` — `--quiet` の定義と human 出力だけを抑制する処理。
- `strata_cli/connections.py:72-94` — 接続記録ディレクトリと絶対パス要件、ディレクトリ検査。
- `strata_cli/connections.py:245-270` — 代入値の許可キー、保存前の revision 照合、変更なしの場合とファイル置換。
- `strata_cli/connections.py:167-187,190-218` — 一時ファイルによる置換と排他ロック。
- `strata_cli/cli.py:490-493,2165` — 接続 parser のトップレベル CLI への登録と共通 runner への委譲。

この調査ではソースコードを対象とし、CLI `--help` や Release 配布物との照合は行っていません。
