# `strata connection list`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection list` |
| 主な実装 | `strata_cli/monitor_commands.py`、`strata_cli/connections.py` |

## 役割

この端末ユーザー用に保存した、モニター接続先の一覧を表示します。接続レコードにはサーバー URL、任意の reverse-proxy prefix、資格情報を参照する環境変数名が含まれます。資格情報の値そのものは保存されず、このコマンドもサーバーへ接続しません。

## 使い方

```sh
# 保存済み接続を表示
strata connection list

# スクリプト向け JSON を出力
strata connection list --output json

# 成功時の human 出力を抑制
strata connection list --quiet
```

接続レコードの作成・詳細表示・変更には、それぞれ `strata connection create`、`show`、`set` を使います。

## 実行時の動作

- 接続ディレクトリにある名前が有効な `*.json` ファイルを名前順に列挙し、各レコードを読み込んで検証します。出力には ID、URL、prefix、資格情報環境変数名、内容から算出した revision が含まれます。名前が規則に合わないファイルは列挙対象から外れます。
- ディレクトリが存在しなければ、空の接続一覧を成功として返します。ディレクトリはこの処理では作成されません。
- 既定の human 出力は整形した JSON 形式で、`connections` 配列を表示します。`--output json` または同じ parser action の alias `--json` では、`schema_version` と `ok` を含む JSON オブジェクトを1行で出力します。
- `--quiet` は成功時の human 出力を抑制します。JSON 出力は抑制されません。

## 注意点

- `*.json` の候補が100件を超えると一覧全体が失敗し、個別確認を促すエラーになります。候補ごとの読み込み・検証エラーは一覧全体を止めず、そのレコードの `id` と `error` を含む項目として表示されます。
- 接続ディレクトリは `STRATA_CONNECTION_DIR`（絶対パスが必要）、Windows の `%APPDATA%/Strata/connections`、または POSIX の `${XDG_CONFIG_HOME:-~/.config}/strata/connections` から決まります。既存ディレクトリがディレクトリでない場合、または POSIX で owner-only でない場合はエラーになります。
- レコードは通常ファイルで4 KiB以下であること、POSIX では owner-only であることなどを検証します。不正レコードは行単位のエラーになります。Windows の ACL 条件はこの調査では確認していません。
- `--quiet` と `--json`（または `--output json`）を併用した場合は machine-readable 出力が優先され、JSON は出力されます。

## 出力とエラー

成功時の終了コードは `0` です。JSON 出力時は失敗を `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式で標準出力へ出し、human 出力時は `strata: ...` を標準エラーへ出します。ディレクトリ不正や100件超過などの `ConnectionError` はコード `5`、ファイル操作などの `OSError` はコード `6` です。個別レコードのエラーは一覧項目に含めるため、それだけでは一覧コマンドの失敗になりません。

## 関連文書

- [CLI 文書索引](../../../README.md) — 同じ `connection` 階層にある `create`、`show`、`set` の概要とオプション文書。
- 接続設定の利用者向け説明は、調査対象 Strata checkout の `docs/TERMINAL.md:30-44` にあります（保存形式、接続例、接続先の優先順位）。

## 根拠

- Strata `strata_cli/cli.py:27,40-45,490-493,2165` — Terminal CLI へのコマンド登録と共通実行経路。
- Strata `strata_cli/monitor_commands.py:75-95` — `connection list` parser、`--output`、`--json`、`--quiet` 定義。
- Strata `strata_cli/monitor_commands.py:140-143,162-175` — 一覧 payload、human/JSON 出力、quiet の処理。
- Strata `strata_cli/connections.py:72-90,128-164` — 接続ディレクトリの選択・検証、レコード列挙・検証、件数上限と不正レコードの扱い。
- Strata `strata_cli/cli.py:2165-2188` — `ConnectionError` 等の整形と終了コード処理。
- Strata `docs/TERMINAL.md:30-44` — 接続レコードの用途と利用者向け例。
