# `strata serve`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| 主な実装 | `strata_cli/cli.py`、`serve/server.py` |
| 必須指定 | `--profile CONFIG.json`（別名 `--config`） |

## 役割

準備済みの run config または保存済み profile を読み込み、Strata の推論 API server を前景プロセスとして起動します。`serve` 自体はセットアップやモデルファイルの取得を行わず、server 起動後もこのコマンドのプロセスが server として動作します。別途セットアップ済みの config が必要です。

## 基本的な使い方

```sh
# config JSON を指定して既定値で起動
strata serve --profile /path/to/run-config.json

# 保存済み profile を指定し、loopback の別 port で起動
strata serve --profile my-profile --host 127.0.0.1 --port 8095

# 起動せず、有効な設定と engine 引数を JSON で確認
strata serve --profile my-profile --plan --output json

# 前景起動の状態遷移を JSONL で受け取る
strata serve --profile my-profile --output jsonl
```

`--profile` は保存済み profile 名または run config JSON のパスです。`--config` は同じ parser 引数の別名です。CLI 指定値は、保存 profile の override と run config の値より優先されます。未指定値は profile、run config、既定値（host `127.0.0.1`、port `8095` など）の順で解決されます。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 前景 server | `strata serve --profile NAME` | 有効設定を組み立てて server を起動します。通常は人間向け出力で、プロセスは停止まで実行を続けます。 |
| 計画表示 | `strata serve --profile NAME --plan` | profile/config と engine 引数を検証し、起動計画を表示して終了します。server は起動しません。`--output json` で JSON にできます。 |
| JSONL lifecycle | `strata serve --profile NAME --output jsonl` | 前景起動し、`starting`、`ready`、`stopping`、`draining`、`stopped` または `failed` を標準出力へ1行ずつ出します。人間向け server 診断は標準エラーへ出ます。 |

`--output json` は `--plan` と併用する必要があり、前景起動のイベント出力には `jsonl` を使います。`--plan` と `--output jsonl` の組み合わせは拒否されます。`--json` は `--plan --output json` のショートカットです。`--quiet` は人間向け情報出力を抑えますが、JSON/JSONL の記録は抑止しません。

## 主な動作と副作用

- host、port、並列 slot、pipeline groups、queue 制限、queue timeout、offline、batch telemetry などの有効値を profile/config と CLI から解決し、server へ引き渡します。CLI override は保存 profile や run config を書き換えません。
- 起動時に API key の設定を検査します。ソースの現行実装ではネットワーク bind でも key がないことだけを理由に起動拒否せず、server 側が警告します。API key は `STRATA_API_KEY` または run config から取得します。
- POSIX/Windows では runtime activity lease を取得してから server を前景起動し、終了時に lease を閉じます。server は `--shutdown-timeout`（既定 30 秒）の範囲で所有中の inference call を drain し、期限切れ時にはそれらをキャンセルします。
- `--ready-file` を指定すると、bind 完了後に instance record を作成します。正常な停止処理で削除されますが、強制 kill では stale file が残ることがあります。`--plan` では書き込みません。
- `--offline` は MCP server または `before_load` command を持つ設定と併用できず、リモート画像 URL の取得や MCP/tool subprocess を止めます。loopback/ネットワーク API の bind 可否とは別の設定です。
- `--max-queue` を指定すると有効 slot 数に追加できる待機 inference call 数を制限します。`--queue-timeout` は `--max-queue` と併用必須で、prompt 準備後から engine の最初の turn が受理されるまでを制限します。

## 注意点

- `--port` は `0..65535`、`--parallel` は `1..1024`、`--max-queue` は `0..4096`、`--queue-timeout` は有限の `0.1..600` 秒、`--shutdown-timeout` は `0..300` 秒です。`--batch-groups` は `auto` または正の整数として profile validation に渡されます。
- `--queue-timeout` 単独指定、run config の engine args にある `--batch`/`--slots` と競合する parallel override、`--batch-groups` 重複指定、offline と MCP/before_load の組み合わせは profile error になります。
- 非 loopback host で公開する場合、到達可能なクライアントが inference API に接続できます。キーなしでも起動可能という実装上の挙動を安全性の保証とみなさず、公開範囲と認証設定を確認してください。
- 起動時の parser/設定エラーは通常終了コード `2`、API key の検証エラーは `5`、foreground server の一般的な失敗は `6`、Ctrl-C は `130`、drain deadline は `8` です。JSONL では startup/running の失敗情報が `failed` event に記録されます。

## オプション文書

このコマンドの option 文書は [`docs/cli/README.md`](../../README.md) の `strata-terminal` → `strata serve` に一覧します。個別の値・既定値・validation・副作用はそちらの各 option 文書を参照してください。

`strata launch` は対話的な設定から server を起動する別の入口です。用途の違いは [`strata launch` 概要](../launch/README.md) を参照してください。

## 根拠

- Strata `strata_cli/cli.py:40-67` — `serve` parser、option、既定の出力モード。
- Strata `strata_cli/cli.py:745-826` — profile/config と CLI 値の優先順位、相互作用、server argv と ready file の準備。
- Strata `strata_cli/cli.py:915-955,2119-2123` — 値検証、plan/foreground 分岐、runtime lease、コマンド dispatch。
- Strata `strata_cli/cli.py:838-897` — JSONL lifecycle event、stdout/stderr、失敗と終了コードの処理。
- Strata `serve/server.py:8140-8172,8290-8308,8615-8633,8674-8708` — 下位 parser、key 未設定時の扱い、bind 後の警告、ready file と graceful drain。
- Strata `docs/TERMINAL.md:220-234` — server の利用方法、JSONL/ready file、queue と offline の説明。ネットワーク bind 時の key 要件については文書と現行ソースの表現に差があるため、本文は parser/起動コードで確認できる挙動を記載。
