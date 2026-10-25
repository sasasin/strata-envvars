# `strata monitor --connection`

`--connection NAME` は、`strata connection create` で保存した接続設定を名前で選び、読み取り専用の Terminal Monitor の接続先として使います。接続レコードから URL、reverse-proxy prefix、認証情報を格納した環境変数名を読み込みます。認証情報そのものは接続ファイルに保存されません（`strata_cli/monitor_commands.py:20-25`、`strata_cli/connections.py:97-114, 273-303`）。

## 使い方

```sh
strata monitor --connection office
strata monitor --connection office --once --json
```

1つ目は対話型モニター、2つ目は一度だけ JSON snapshot を出力します。`--connection` は `monitor` サブコマンドの接続オプションです。`status` と `logs` にも同じ parser helper 経由で定義されていますが、ここでは `monitor` の動作を扱います（`strata_cli/monitor_commands.py:28-33, 49-60, 63-72`）。

## 値と既定値

- `NAME` は位置引数ではなく `--connection` の値です。option 自体に既定値はありません（`strata_cli/monitor_commands.py:20-25`）。
- 保存名は小文字 `a-z` で始まり、以降は小文字英字・数字・`_`・`-`、全体で最大64文字です。無効名は `ConnectionError` になります（`strata_cli/connections.py:41-56`）。
- 指定名の JSON レコードは接続設定ディレクトリから読み込まれます。既定位置は Windows では `%APPDATA%/Strata/connections`（APPDATA がなければユーザーの Roaming 配下）、その他では `$XDG_CONFIG_HOME/strata/connections`（未設定なら `~/.config/strata/connections`）です。`STRATA_CONNECTION_DIR` があれば絶対パスとして優先されます（`strata_cli/connections.py:72-95`）。

## 実行時の動作と相互作用

- `--connection` と `--url` は同時に指定できません。両方ある場合は `choose --url or --connection, not both` で失敗します（`strata_cli/connections.py:273-280`）。
- 接続名を指定すると保存レコードの URL、prefix、credential-env 名を使い、`STRATA_URL` は接続先選択に使いません。`--credential-env NAME` が併記されると、保存された認証環境変数名をその値で上書きします。レコードには credential 値ではなく環境変数名が保持されます（`strata_cli/connections.py:280-294`、`strata_cli/monitor_commands.py:20-25, 195-199`）。
- 明示的な `--url` / `--connection` がない場合、`STRATA_CONNECTION` があれば保存接続を選びます。これらも環境変数もなければ `STRATA_URL`、さらに未設定なら `http://127.0.0.1:8095` が接続先になります。`--connection` 指定時は起動中の `strata launch` の情報を探索せず、その接続を解決します（`strata_cli/connections.py:44, 273-292`、`strata_cli/monitor_commands.py:36-46, 195-197`）。
- 解決した URL・prefix・credential-env を `Endpoint` に渡し、認証値はその環境変数から取得します。モニターはサーバーから snapshot を取得し、対話型 UI を起動します。`--connection` 自体は保存設定を書き換えません（`strata_cli/monitor_commands.py:195-229`）。

## 適用条件、副作用、失敗

接続ファイルは読み取り対象です。ファイルがない場合、形式・schema・接続 ID・URL・prefix・credential-env が不正な場合、ファイルが非 private / 非 regular / 4 KiB 超の場合などは接続解決に失敗します。POSIX では接続ディレクトリと接続ファイルの所有者専用権限も検査されます（`strata_cli/connections.py:85-114, 128-146`）。

接続名が未保存なら `strata connection create` を案内するエラーになり、接続エラーは通常 stderr の `strata: ...` と終了コードで報告されます（machine output 時は JSON error）。接続エラーの既定終了コードは 2 ですが、ファイルや schema の検証エラーは 5 です（`strata_cli/connections.py:47-50, 128-146`、`strata_cli/monitor_commands.py:124-129, 231-240`）。

## 根拠と調査範囲

調査対象 Strata revision: `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。調査開始時の `git status --short --branch` は `## main...origin/main` で、表示された未コミット変更はありませんでした。

parser 登録は `strata_cli/cli.py:488-493`、monitor parser と共通接続 option は `strata_cli/monitor_commands.py:20-25, 49-60`、解決・endpoint への受け渡しとエラー出力は `strata_cli/monitor_commands.py:124-129, 189-240`、保存接続の validation と選択規則は `strata_cli/connections.py:41-114, 128-146, 273-303` を確認しました。ビルド済み CLI help、実行時の OS ごとの権限挙動、配布 bundle の差は調査していません。
