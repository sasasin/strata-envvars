# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection create` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

接続作成の結果を機械可読な JSON で標準出力へ出します。`--output json` の短縮指定です。接続を作成・保存する処理そのものは省略されません。

## 使い方

```sh
strata connection create work --url https://inference.example --prefix /strata --credential-env STRATA_TELEMETRY_KEY --json
```

## 値と既定値

`--json` は `argparse` の `store_true` フラグで、指定時は真になります。省略時の `json` 属性は偽で、出力形式は既定の `--output human` に従います。`--output` は `human` または `json` を選べ、既定値は `human` です。両方を指定した場合、`--json` があれば JSON 出力になります（`--output human` を併記しても同じです）。

## 実行時の動作

`strata connection create` の parser は `--json` を `--output` とともに登録し、ヘルプ上も `--output json` の alias と定義しています。トップレベル CLI から接続コマンドは monitor command handler に渡されます。同 handler は `--json` または `--output json` のどちらかが指定されると machine 出力として扱い、`connections.create()` が返す接続情報と revision を成功 payload に含めます（`strata_cli/monitor_commands.py:75-94, 132-150, 162-164`; `strata_cli/cli.py:490-493, 2119-2165`）。

成功時の JSON は `schema_version: 1`、`ok: true`、`connection`、`revision` を持ちます。`connection` には ID、URL、prefix、credential 環境変数名が含まれますが、credential の値は保存対象にも出力にもなりません。JSON は標準出力に1行で出力されます（`strata_cli/monitor_commands.py:148-150, 162-164`; `strata_cli/connections.py:221-242`）。

## 適用条件と副作用

このオプション自体に追加の入力検証やネットワーク接続はありません。接続作成時には、名前、URL、prefix、credential 環境変数名が検証されます。URL は `http` / `https` のサーバー root のみで、非 localhost の remote root は HTTPS が必要です。prefix は最大256文字の単純な `/path` セグメントで、`.`・`..` や query を受け付けません。credential 環境変数名は ASCII の環境変数識別子形式です（`strata_cli/connections.py:41-69, 221-226`; `strata_cli/client.py:45-76`）。

接続ファイルは `STRATA_CONNECTION_DIR` があればその絶対パス配下、Windows では `%APPDATA%/Strata/connections`（未設定時はホーム配下）、その他の OS では `${XDG_CONFIG_HOME:-~/.config}/strata/connections` に作成されます。ディレクトリがなければ作成し、作成するファイルは `0600` で排他的に開きます。同名ファイルがある場合は上書きせず失敗します。保存レコードは最大4 KiBです（`strata_cli/connections.py:72-95, 117-121, 221-242`）。POSIX では既存ディレクトリの所有者・権限も検査されます。Windows の ACL 検証はこのコード経路からは確認できません（`strata_cli/connections.py:83-90`; `docs/TERMINAL.md:44`）。

## 出力とエラー

成功 JSON は stdout に出力されます。`--quiet` を併用しても machine 出力は抑制されません（`strata_cli/monitor_commands.py:167-175`）。失敗時に JSON モードなら stderr ではなく、stdout に `schema_version: 1`、`ok: false`、`error: {code, message}` の JSON が出ます。人間向けモードでは `strata: ...` を stderr に出します（`strata_cli/monitor_commands.py:124-129, 231-240`）。

不正な接続名・URL・prefix・credential 参照、相対パスの `STRATA_CONNECTION_DIR`、既存名との衝突は作成を拒否します。既存の接続ディレクトリがディレクトリでない、または POSIX で owner-only 条件を満たさない場合も拒否します。これらの入力・競合エラーは通常 exit code 2、保存先の安全性エラーは code 5、ファイル操作の `OSError` は code 6 となり、machine モードでは同じ code が JSON の `error.code` に入ります（`strata_cli/connections.py:53-69, 72-90, 221-242`; `strata_cli/monitor_commands.py:231-240`）。parser が認識しない引数は `argparse` が usage error として処理し、トップレベル CLI は `SystemExit` で終了します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection create` と `--json` / `--output` の parser 定義。
- `strata_cli/monitor_commands.py:124-129, 132-164, 167-175, 231-240` — 成功 payload、JSON 判定、quiet の扱い、エラー形式。
- `strata_cli/connections.py:41-43, 53-90, 117-121, 221-242` — 名前・参照・保存先・容量・作成時の検証とファイル作成。
- `strata_cli/client.py:45-76` — server root URL と prefix の形式検査。
- `strata_cli/cli.py:490-493, 2119-2165, 2217-2231` — parser 登録、command handler への委譲、引数エラー経路。
- `docs/TERMINAL.md:30-44` — 接続レコードの目的と利用例。実装挙動の根拠は上記ソース。
