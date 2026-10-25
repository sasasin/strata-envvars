# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection create` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `false` |

## 役割

接続先をローカルに保存する際、人向けの成功情報を標準出力に表示しないためのフラグです。接続レコードの作成自体は実行されます。`connection create` は名前付きのサーバー接続を保存するコマンドで、認証情報の値ではなく環境変数名を記録します（`strata_cli/monitor_commands.py:76-82`）。

## 使い方

```sh
strata connection create staging --url https://monitor.example.com --quiet
```

コマンドはサーバーへの接続確認を行わず、接続情報をローカルに保存します。`name` と `--url` は必須です（`strata_cli/monitor_commands.py:78-82`）。

## 値と既定値

- `--quiet` は `argparse` の `store_true` で登録されており、値を付けずに指定します。省略時は偽です（`strata_cli/monitor_commands.py:91-94`）。
- この parser では `--quiet` に短縮別名はありません。
- `--output json` またはその alias の `--json` と同時に指定しても、JSON 成功出力は抑制されません。実行時の `machine` 判定が真になると `quiet` を無効扱いにするためです（`strata_cli/monitor_commands.py:167-169`）。

## 実行時の動作

- 人向け出力（既定の `--output human`）で `--quiet` が有効なときは、接続作成処理中の標準出力をメモリ上の `StringIO` に向けます。成功時には通常の接続情報 JSON 表示も抑えられます（`strata_cli/monitor_commands.py:162-164`, `167-175`）。
- `--quiet` が抑えるのは出力だけです。処理では `connections.create(...)` を呼び、成功した接続情報と revision を組み立ててから通常どおり終了します（`strata_cli/monitor_commands.py:147-150`）。
- 保存先は `STRATA_CONNECTION_DIR` があればその絶対パス、なければ OS に応じたユーザー設定ディレクトリです。作成時にディレクトリを用意し、接続名を `<name>.json` として保存します（`strata_cli/connections.py:72-95`, `221-242`）。
- 既存の同名ファイルは上書きせず、作成に失敗します（`strata_cli/connections.py:228-233`）。接続レコードには認証情報の値でなく `credential_env` という参照名を保存します。既定の参照名は `STRATA_TELEMETRY_KEY` です（`strata_cli/monitor_commands.py:82`, `strata_cli/connections.py:221-226`）。

## 適用条件と副作用

- `--quiet` の抑制は人向け出力に限られます。JSON モードは機械可読出力を優先し、成功時の JSON を標準出力に出します（`strata_cli/monitor_commands.py:91-94`, `167-175`）。
- 成功時も接続 JSON ファイルと必要な設定ディレクトリを作成します。既存ファイルを置換しません。POSIX では private directory helper を使い、ファイルは排他的作成でモード `0600` を指定します（`strata_cli/connections.py:11-15`, `72-90`, `228-236`）。
- `--url` は `http` または `https` のサーバールートで、埋め込み認証情報、パス、query、fragment は拒否されます。非 TLS の URL は localhost / loopback に限られます。`--prefix` は最大 256 文字の単純なパスセグメントで、`.` / `..` を含むセグメントなどは拒否されます（`strata_cli/client.py:45-76`）。

## 出力とエラー

- 人向けモードの正常終了では `--quiet` により標準出力は空になります。エラーは `strata: <説明>` の形式で標準エラーに出力され、quiet によって抑制されません（`strata_cli/monitor_commands.py:124-129`, `167-175`, `231-240`）。
- JSON モードでは失敗も標準出力に JSON エラーとして出力されます（`strata_cli/monitor_commands.py:124-129`, `167-169`, `231-240`）。
- 無効な接続名、URL、prefix、環境変数名などは validation error になります。重複名は「already exists」で拒否されます。`ConnectionError` は通常終了コード `2`、設定ディレクトリの権限・安全性に関する一部のエラーは `5`、ローカルファイル操作の `OSError` は `6` を返します（`strata_cli/connections.py:47-69`, `72-90`, `221-242`; `strata_cli/monitor_commands.py:231-240`）。

## 根拠

- 索引のコマンド階層と予定リンク: `docs/cli/README.md:1039-1049`（調査対象文書側）。
- parser 定義、必須引数、共通出力オプション: `strata_cli/monitor_commands.py:75-94`。
- quiet の判定、出力抑制と作成処理: `strata_cli/monitor_commands.py:147-175`。
- エラー表示と終了コードの伝播: `strata_cli/monitor_commands.py:124-129`, `231-240`。
- 接続値の検証、保存先、既存ファイル拒否とファイル作成: `strata_cli/connections.py:41-90`, `221-242`。
- URL と prefix の規則: `strata_cli/client.py:45-76`。

調査は上記 checkout の parser と処理経路に限定しました。同一 revision の `--help` 実行、Release 配布物、各 OS での実行確認は行っていません。
