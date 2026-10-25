# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata status` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定時は `True` |

## 役割

status の人間向けスナップショット表示を抑えます。接続先への問い合わせやスナップショット生成は省略しません。

## 使い方

```sh
strata status --quiet
```

接続先を明示する場合は `strata status --url http://127.0.0.1:8095 --quiet` のように指定できます。

## 値と既定値

値は不要で、未指定時の既定値は `False` です。複数回指定しても同じ真偽値になります。値を付けて `--quiet true` のように書くと、`true` は別の引数として扱われ、引数解析エラーになります。

## 実行時の動作

- `--quiet` は `argparse` の `store_true` action として宣言されています（`strata_cli/monitor_commands.py:28-34`）。
- status 実行では、出力形式が人間向けの場合に `quiet` が有効になり、`render_view(...)` の呼び出しと標準出力への表示を飛ばします。ただし、その前に `endpoint.snapshot()` を呼ぶため、接続先への読み取り要求は通常どおり発生します（`strata_cli/monitor_commands.py:167-169,195-213`）。
- `--json` は `--output json` の別表記です。`--quiet --json` または `--quiet --output json` では machine output が優先され、JSON スナップショットを標準出力に出します。quiet は JSON を抑制しません（`strata_cli/monitor_commands.py:31-34,167-168,203-208`）。
- 接続先は `--connection` があれば保存済み接続、`--url` があればその URL、どちらもなければ `STRATA_CONNECTION` または `STRATA_URL`、最後に `http://127.0.0.1:8095` の順で解決されます。URL と接続名を同時に指定すると失敗します。明示 URL/接続名がなく `STRATA_URL` と `STRATA_CONNECTION` もない場合、Terminal が起動した server の URL/key を取得できればそれを使います（`strata_cli/monitor_commands.py:36-46,195-199`; `strata_cli/connections.py:273-302`）。

## 適用条件と副作用

このオプションが抑えるのは人間向け status 表示だけです。ネットワークへの読み取り要求、credential の解決、既定の接続先の解決は残ります。接続失敗などのエラーは quiet でも標準エラーに表示されます（`strata_cli/monitor_commands.py:124-129,195-213,231-240`）。

`--timeout` は status のリクエスト timeout を秒数で指定し、省略時は 3 秒です。受理範囲は `0 < timeout <= 30` で、範囲外はエラーになります（parser: `strata_cli/monitor_commands.py:20-25`; 解決・検証: `strata_cli/connections.py:273-302`; `Endpoint` の検証: `strata_cli/client.py:84-95`）。

## 出力とエラー

- 成功時に `--quiet` のみを指定した場合、status の人間向けスナップショットは標準出力に出ません。問い合わせも成功すれば終了コード `0` です（`strata_cli/monitor_commands.py:203-213`）。
- JSON 出力を指定した場合は quiet と併用しても JSON を標準出力に出し、成功時は終了コード `0` です（`strata_cli/monitor_commands.py:203-208`）。
- 接続・認証・不正な応答等の失敗は、人間向けモードでは `strata: ...` の形式で標準エラーに出ます。ClientError は既定で終了コード `3`、認証/権限拒否は `4`、互換性のない telemetry schema は `5` です。timeout や接続不能も ClientError となり、接続不能は既定の `3` です（`strata_cli/monitor_commands.py:124-129,231-240`; `strata_cli/client.py:38-42,117-152`）。
- 引数の型・parser エラーや `--timeout` の範囲外は終了コード `2` のエラー経路です（`strata_cli/monitor_commands.py:20-25`; `strata_cli/connections.py:295-297`; `strata_cli/cli.py:2223-2231,2165-2173`）。

## 根拠

- `strata_cli/monitor_commands.py:28-34` — `strata status` parser と `--quiet` の定義。
- `strata_cli/monitor_commands.py:167-213` — quiet/machine 判定、接続解決、status snapshot の取得と表示分岐。
- `strata_cli/monitor_commands.py:231-240`、`strata_cli/cli.py:2119-2173` — status 実行時の例外・エラー処理。
- `strata_cli/connections.py:273-302`、`strata_cli/client.py:45-63,84-152` — 接続先・timeout の解決、URL 検証、読み取り snapshot の通信と fallback。

この文書は指定 commit のソースを確認した結果です。CLI バイナリや公式 Release artifact の実行確認は行っていません。
