# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection show <name>` |
| オプション | `--json` |
| 別名 | `--output json` |
| 値 | 値を取らないフラグ。未指定時は `false` |

## 役割

保存済み接続の情報を JSON 形式で標準出力へ出します。出力には schema version、成功状態、接続レコード、レコード内容から算出した revision が含まれます。接続レコードには credential の値ではなく環境変数名が格納されるため、このコマンドも credential 値を表示しません。

## 使い方

```sh
strata connection show myserver --json
```

`--output json` も同じ JSON 出力を選びます。`--output` の既定値は `human` ですが、`--json` を付けると JSON 出力になります。

## 値と既定値

- `--json` は値を受け取らない `store_true` フラグです。指定しない場合は偽です。
- 同じ parser で `--output` は `human` または `json` のみを受け付け、既定値は `human` です。`--json` の真偽または `--output json` のいずれかで機械可読出力になります。
- `--output` に他の値を指定すると、argparse が usage とエラーを標準エラーへ出し、終了コード 2 で終了します。

## 実行時の動作

`show` は `<name>` を `connections.load()` に渡して接続ファイルを読み、返された接続情報と revision を出力 payload にします。JSON 成功時の形は `{"schema_version":1,"ok":true,"connection":...,"revision":"..."}` です。revision は保存ファイルの生バイト列に対する SHA-256 の先頭16桁です。

この経路は接続ファイルをローカルで読むだけで、サーバーへのリクエストや設定ファイルの変更を行いません。`--quiet` も指定した場合、human 出力は抑制されます。JSON 出力では `quiet` が無効扱いとなるため JSON は出力されます。

## 適用条件と副作用

接続名は小文字 `a-z` で始まり、その後は小文字英字・数字・`_`・`-` を使える最大64文字の名前です。既定の保存場所は Windows では `%APPDATA%/Strata/connections`（`APPDATA` がなければユーザーの `AppData/Roaming/Strata/connections`）、他の OS では `$XDG_CONFIG_HOME/strata/connections`（未設定時は `~/.config/strata/connections`）です。`STRATA_CONNECTION_DIR` が設定されていれば絶対パスであることを要求し、その場所を使います。

読み込む記録は通常ファイルで4 KiB以下である必要があり、POSIX では所有者専用の権限・所有者であることも検査されます。記録は schema version 1 で、`schema_version`, `id`, `url`, `prefix`, `credential_env` の5キーだけを持ち、ID はファイル名と一致しなければなりません。URL と prefix は正規形である必要があります。読み取り時にディレクトリやファイルを作成・更新・削除する処理はありません。

## 出力とエラー

- 成功時は標準出力に1行の JSON を出し、終了コード 0 です。
- 指定名の記録がない場合はエラーコード 5、接続記録の権限・形式・値が不正な場合もコード 5 です。JSON モードでは `schema_version`, `ok:false`, `error:{code,message}` の JSON を出力します。human モードでは `strata: ...` を標準エラーへ出します。
- 接続名の形式不正は `ConnectionError` の既定終了コード 2 です。JSON モードでのエラー JSON と、human モードでの標準エラー出力は上記と同様です。
- ファイル操作の `OSError` はコード 6 として扱われます。JSON モードではエラー JSON、human モードではファイル操作エラーを標準エラーへ出します。
- `--quiet` を human モードで併用すると成功時の標準出力は抑制されます。失敗時のエラーは抑制されません。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — connection/show parser、`--output` の候補と既定値、`--json` と `--quiet` の定義。
- `strata_cli/monitor_commands.py:124-129, 140-146, 162-175` — JSON エラー envelope、show payload、出力形式の選択、quiet 時の stdout 抑制。
- `strata_cli/monitor_commands.py:231-240` — connection/client/value/OS エラーと終了コードの処理。
- `strata_cli/cli.py:488-493, 2165` — Terminal CLI への parser 登録と共通 runner への委譲。
- `strata_cli/connections.py:41-56, 72-95` — 接続名形式と保存先の選択。
- `strata_cli/connections.py:97-115, 124-146` — 保存レコードの schema・canonical 値検査、ファイルの安全条件、欠損・不正時のエラー、revision の計算。

この文書は上記 commit のソースを調査したものです。Release 配布物や別 OS で実行しての挙動確認は行っていません。
