# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection show` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定値は `false` |

## 役割

保存済み接続の表示で、人間向けの成功結果を標準出力に出さないためのフラグです。接続情報を読み取る処理自体やエラー表示は抑止しません。

## 使い方

```sh
strata connection show production --quiet
```

通常の `human` 出力で成功しても標準出力は空になります。JSON 出力を指定した場合は `--quiet` を併記しても JSON レコードが出力されます。

## 値と既定値

値を取らない `store_true` フラグで、指定しなければ `false`、指定すれば `true` です。`--quiet=true` のような値付き指定は parser の定義上受理されません。`--output` は `human` または `json` を受理し既定値は `human`、`--json` は `--output json` の alias です。これらは `--quiet` と併用できます。

## 実行時の動作

`show` は名前を位置引数として受け取り、保存済み接続を `connections.load()` で読み込みます。通常の human 出力では schema 情報と `ok` を除いた `connection` と `revision` が整形 JSON として標準出力に表示されます。`--quiet` が有効で human 出力の場合、`run()` がこのローカル処理の標準出力をメモリ上にリダイレクトし、成功時に内容を表示しません。

`--json` または `--output json` の場合は `machine` が有効となり、quiet 抑止の対象外です。成功時は `schema_version`、`ok`、`connection`、`revision` を含む JSON が標準出力に出ます。接続レコードに含まれるのは credential の環境変数名であり、credential の値ではありません。

## 適用条件と副作用

このフラグは `strata connection show` parser に属し、引数や実行環境に関する追加条件はありません。`show` は保存ファイルを読み取るだけで、接続先へのネットワーク要求や接続レコードの変更は行いません。保存ディレクトリは `STRATA_CONNECTION_DIR`（絶対パス必須）、Windows の `APPDATA` 配下、または Unix 系の `XDG_CONFIG_HOME` / `~/.config/strata/connections` から決まります。

## 出力とエラー

- human 成功時は `--quiet` により標準出力を抑止します。JSON 成功出力は抑止しません。
- 接続名が未保存、ファイルが読めない、形式・権限・schema が不正などの失敗は quiet でも表示されます。human エラーは標準エラー、機械可読エラーは標準出力に JSON で出ます。
- 接続レコードの読み込み・検証エラーは通常終了コード `5`、不正な接続名などの `ConnectionError` 既定終了コードは `2` です。OS のファイル操作エラーは CLI のエラー処理でコード `6` になります。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection show` parser と、各 connection action への `--quiet`、`--output`、`--json` 追加。
- `strata_cli/monitor_commands.py:124-129,140-164` — human / machine エラー形式と show の読込・成功出力。
- `strata_cli/monitor_commands.py:167-175,231-240` — quiet の適用条件、標準出力の抑止、エラー経路。
- `strata_cli/connections.py:47-55,72-94,97-114,128-146` — 接続名、保存場所、レコード形式、読込・検証と失敗コード。
- `strata_cli/cli.py:2119-2173` — Terminal CLI から monitor command への振り分けと `ValueError` / `OSError` の処理。
