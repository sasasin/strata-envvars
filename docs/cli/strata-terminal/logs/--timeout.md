# `strata logs --timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。調査時の作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--timeout` |
| 別名 | なし |
| 値 | 秒数（浮動小数点数）。`0 < 値 <= 30` |

## 役割

ログ取得コマンドが Strata サーバーへ送る各 HTTP リクエストの待ち時間上限を指定します。`--follow` を使う場合も各ポーリング要求に適用されます。コマンド全体の実行時間を制限する値ではありません。

## 使い方

```sh
strata logs --url http://127.0.0.1:8095 --timeout 5
```

保存済み接続を使う場合も指定できます。

```sh
strata logs --connection local --timeout 1.5 --follow
```

## 値と既定値

- parser は `float` として読み取り、parser 上の既定値は未指定（`None`）です。接続設定の解決時に省略値を `3.0` 秒にします。
- 明示値は正数かつ30秒以下でなければなりません。0、負数、30を超える値、NaN、無限大は接続解決で拒否されます。文字列を数値へ変換できない値は `argparse` の引数エラーになります。
- 同じオプションを複数回指定した場合、通常の `argparse` の `store` 動作により最後の値が使われます。

## 実行時の動作

`strata logs` parser は共有接続オプション群を追加し、その中に `--timeout` を定義します。コマンド実行では `connections.resolve()` に値を渡し、結果の `timeout_s` で HTTP クライアントの `Endpoint` を作り、ログ取得処理へ渡します。`Endpoint.get()` が `urllib` の各 `open()` にこの秒数を指定します。

サーバー指定は `--url` または `--connection` を使います。両方を同時に指定すると拒否されます。どちらもないときは、保存済み接続や環境設定などで接続先を解決しますが、タイムアウトはその接続先設定とは独立して、明示値または3秒の既定値になります。`--follow` では待ち時間の後に snapshot 要求を繰り返すため、総実行時間は制限されません。また snapshot は互換性のため複数 endpoint を順に試す場合があり、そのとき各要求に個別の上限がかかります。

## 適用条件と副作用

`--timeout` は `strata logs` 専用ではなく、`strata status`、`strata monitor`、`strata config show` にも共有接続オプションとして定義されています。この文書では `strata logs` でのスコープを説明します。

このオプションは読み取り専用の telemetry/activity 要求の接続待ち時間に作用します。`strata logs` はローカルのログファイルを読むのではなく、サーバーの request activity snapshot を取得します。`--follow` は Ctrl+C まで継続し、Ctrl+C は正常終了扱いです。

## 出力とエラー

- 無効な数値範囲は `strata: timeout must be greater than zero and at most 30 seconds` を stderr に出し、終了コード2になります。`--output json` / `--json` の machine 出力では標準出力にエラー JSON を出します。
- 通信タイムアウトを含む接続失敗は `cannot reach Strata server: <例外型>` として扱われ、既定の終了コード3になります。通常出力では stderr、JSON 出力では標準出力にエラー JSON を出します。
- `--follow` 中の接続失敗は最大3回まで再試行し、3回目で失敗します。タイムアウト値は各要求の待ち時間上限に作用し、再試行の間隔は `--interval` が決めます。
- 接続解決時の範囲エラーは `monitor_commands.run()` 内で捕捉され、`strata` prefix 付きのエラーとして出力されます。数値への変換に失敗した場合は `argparse` が usage とエラーを出し、終了コード2で終了します。

## 根拠

- `strata_cli/monitor_commands.py:20-26` — 共有接続オプションとしての `--timeout`、型、help 上の既定値説明。
- `strata_cli/monitor_commands.py:63-72` — `logs` parser への共有接続 parser の適用と関連オプション。
- `strata_cli/monitor_commands.py:167-202` — `logs` の interval/source 検証、接続解決、Endpoint 生成、ログ処理への転送。
- `strata_cli/monitor_commands.py:231-244` — 接続・クライアントエラーと Ctrl+C の出力・終了コード処理。
- `strata_cli/connections.py:273-302` — `--url` と `--connection` の排他、タイムアウト範囲検証、既定3秒および値の由来。
- `strata_cli/client.py:38-42` — クライアントエラーの既定終了コード3。
- `strata_cli/client.py:84-125` — Endpoint の範囲検証、HTTP要求への timeout 適用、接続失敗の変換。
- `strata_cli/client.py:134-152` — snapshot が telemetry endpoint の404時に複数 endpoint を試す互換経路。
- `strata_cli/logs.py:101-151` — one-shot activity 取得、follow の poll、接続失敗の再試行。
- `strata_cli/cli.py:488-493` — Terminal CLI の `strata logs` parser 登録。
- 索引 `docs/cli/README.md:1019-1033` — `strata logs` の文書階層と `--timeout` の掲載。
