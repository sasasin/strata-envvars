# `strata monitor --credential-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--credential-env NAME` |
| 別名 | なし |
| 値 | サーバー認証情報を格納した環境変数の名前。秘密値自体は引数に渡さない |

## 役割

モニターが読み取り専用の telemetry endpoint へ接続するときに使う認証情報の環境変数名を指定します。実際の環境変数値は `Authorization: Bearer ...` としてリクエストへ渡されます。

## 使い方

POSIX shell で環境変数を設定してから参照名を渡す例です。

```sh
STRATA_TELEMETRY_KEY='(設定済みのキー)' strata monitor --url https://strata.example --credential-env STRATA_TELEMETRY_KEY --once
```

## 値と既定値

- parser はこの option に続く `NAME` を1つの文字列値として受け取り、option 自体は任意です。parser 側に既定値や専用の `choices` はありません。monitor 用 parser は status/logs と共有の `_connection` 定義を使います（`strata_cli/monitor_commands.py:20-25,49-60`）。
- 実行時には ASCII の環境変数名として `[A-Za-z_][A-Za-z0-9_]{0,127}` に一致する必要があります。値の設定有無や内容は名前の検証対象ではありません（`strata_cli/connections.py:41-42,66-69`）。
- `--credential-env` を省略したとき、保存済み `--connection` が選ばれればその接続に保存された `credential_env` 参照を使います。直接 URL、環境 URL、既定 URL で接続する場合の参照名は `STRATA_API_KEY` です（`strata_cli/connections.py:273-294`）。
- 指定された環境変数が未設定または空でも名前自体は受理されます。その場合、通常の直接接続では認証ヘッダーを付けず、monitor が既存の launch 情報を検出できた場合はその情報に含まれる鍵を代替値として使います（`strata_cli/monitor_commands.py:195-199`）。

## 実行時の動作

`strata monitor` は `monitor_commands.run` に処理を委譲します。URL と保存済み接続を同時に使うことはできず、明示した `--credential-env` は保存済み接続に記録された参照名より優先します（`strata_cli/cli.py:490-492,2165`; `strata_cli/connections.py:277-294`）。

URL・接続の明示がなく、`STRATA_URL` と `STRATA_CONNECTION` も設定されていない場合、Terminal CLI は実行中の `strata launch` 情報から接続先と鍵を探します。見つかった場合でも `--credential-env` の環境変数に値があればそちらを優先し、その値が空なら launch 情報の鍵を使います。明示 URL、保存接続、または URL/接続環境設定がある場合は、この launch 情報探索を行いません（`strata_cli/monitor_commands.py:36-46,195-199`）。

環境変数に値があれば endpoint client はその値を Bearer 認証ヘッダーに設定します。値は URL やコマンドライン引数には埋め込まれません。接続処理は telemetry snapshot を読み取り、対話 monitor または `--once` の表示に使います（`strata_cli/monitor_commands.py:198-229`; `strata_cli/client.py:101-107,134-152`）。

## 適用条件と副作用

- `--once` の一回表示と対話 monitor の両方で、接続先認証の環境変数参照に使われます。値の書き込みやサーバー起動はこのオプションの役割ではありません（`strata_cli/monitor_commands.py:189-229`）。
- monitor は読み取り専用の telemetry API を利用します。認証値がある場合、`/v1/telemetry` へのリクエストに Bearer header を付けます。旧サーバー互換のため telemetry が 404 の場合は metrics/status endpoint にフォールバックします（`strata_cli/client.py:101-107,134-152`）。
- このオプションは鍵の権限を制限・検証しません。どの API を許可するかはサーバー側の認証設定によります。
- モニターの対話実行は端末を必要とします。端末でない場合は `--once` を使うよう失敗します（`strata_cli/monitor_commands.py:191-194`）。

## 出力とエラー

- 不正な環境変数名は `connections.resolve` 内で拒否され、既定終了コード 2 のエラーになります（`strata_cli/connections.py:47-50,66-69,292-301`; `strata_cli/monitor_commands.py:233-236`）。
- 認証環境変数が未設定でも、monitor 起動前の名前検証エラーにはなりません。サーバーが認証を要求して無効・不足と判定した場合は「telemetry authentication or permission failed」となり、終了コード 4 です（`strata_cli/client.py:117-123`; `strata_cli/monitor_commands.py:231-234`）。
- 人間向けエラーは標準エラーへ `strata: ...` として出力されます。`--output json` のエラーは JSON の `ok: false` レコードになります（`strata_cli/monitor_commands.py:124-129,167-169,231-240`）。
- リモート接続では HTTPS が必要です。HTTP は localhost/loopback に限られ、リダイレクトは追従せずエラーになります（`strata_cli/client.py:45-63,79-82,117-125`）。

## 根拠

- parser と option scope: `strata_cli/monitor_commands.py:20-25,49-60`。`strata_cli/cli.py:490-492` が同じ parser module から monitor を登録し、`strata_cli/cli.py:2165` が実行を委譲します。
- 接続設定の優先順位と環境変数名 validation: `strata_cli/connections.py:41-50,66-69,273-303`。
- launch 情報からの接続先・鍵の補完: `strata_cli/monitor_commands.py:36-46,195-199`。launch 情報の鍵の取得元: `strata_cli/launch/cmd.py:605-625`。
- Bearer header、許可 endpoint、認証・HTTP エラー: `strata_cli/client.py:79-125,134-152`。
- この文書は索引の `strata monitor` 項目（`docs/cli/README.md:1000-1017`）に対応します。同じオプション名が `status`、`logs`、`models list` 等にもありますが、それぞれのコマンドスコープに属します。

調査範囲は上記 commit の checkout に含まれる Terminal CLI の parser、接続解決、monitor 実行、HTTP client です。別 platform の配布 bundle や外部サーバーの認証設定までは検証していません。
