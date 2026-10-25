# `--prefix`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection create` |
| オプション | `--prefix` |
| 別名 | なし |
| 値 | reverse proxy 配下の URL path。省略可能 |

## 役割

保存する接続先に reverse proxy の path prefix を設定します。サーバー root URL と prefix は別々に保持され、後で monitor client が telemetry endpoint を組み立てるときに使われます。認証情報そのものではなく、認証情報を読む環境変数名とともに接続レコードへ保存されます。

## 使い方

```sh
strata connection create work --url https://inference.example --prefix /strata
```

`--url` は必須です。`--prefix` を省略すると空文字列が使われます。

## 値と既定値

- 値は 256 文字以下の path です。空文字列と `/` は prefix なしとして `""` に正規化されます。
- それ以外は `/` で始まり、各 path segment が `[A-Za-z0-9._~-]+` に一致する必要があります。`.` と `..` の segment、空 segment（例: `//` や末尾 `/`）、query・fragment・percent encoding 等は受理されません。
- 既定値は `""` です。単一 segment と複数 segment のどちらも指定できます（例: `/strata`、`/api/v1`）。

## 実行時の動作

Parser は `--prefix` を `create` subcommand にだけ追加し、既定値 `""` を設定します。dispatch はその値を `connections.create(..., prefix=a.prefix)` に渡します。`connections.create()` は `url_prefix()` で検証・正規化した値を接続レコードの `prefix` として含め、接続 JSON を作成します。後続の client は root URL と prefix を連結して base URL にします（`Endpoint.base_url`）。

例では `https://inference.example` と `/strata` が保存され、client の base URL は `https://inference.example/strata` になります。prefix は URL の origin を変えず、create 時に通信は行いません。

## 適用条件と副作用

この値は `strata connection create` の接続設定に適用されます。コマンドは接続ディレクトリがなければ作成し、名前に対応する JSON ファイルを新規作成します。作成時は `O_EXCL` を使うため、同名接続が既にある場合に上書きしません。prefix が空または `/` の場合も接続ファイルは作られますが、保存値は空文字列です。

## 出力とエラー

成功時は標準出力に接続情報と revision を出します。`--output json` または `--json` があれば schema version 1 の成功 JSON になります。

不正な prefix は接続エラー（終了コード 2）になり、人間向け出力では `strata: ...` を標準エラーへ出します。JSON 出力では標準出力に `ok: false` とエラー情報を出します。同名接続もエラーとなり、既存ファイルは変更されません。`--url` の欠落など parser の構文エラーは `argparse` が処理します。

## 根拠

- Parser と option scope・既定値: `strata_cli/monitor_commands.py:75-94`。
- `strata connection` parser 登録と dispatch: `strata_cli/cli.py:490-493`, `strata_cli/cli.py:2165`。
- 値の検証・正規化: `strata_cli/client.py:66-76`; `strata_cli/connections.py:59-64`, `strata_cli/connections.py:221-226`。
- ファイル作成と既存名の拒否: `strata_cli/connections.py:227-242`。
- prefix を base URL に反映する処理: `strata_cli/client.py:84-100`。
- 成功出力・エラー出力: `strata_cli/monitor_commands.py:124-129`, `strata_cli/monitor_commands.py:140-150`, `strata_cli/monitor_commands.py:162-164`, `strata_cli/monitor_commands.py:231-240`。
- 利用者向け作成例: `docs/TERMINAL.md:30-38`。
