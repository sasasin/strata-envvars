# `strata connection show`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection show` |
| 主な実装 | `strata_cli/monitor_commands.py`、`strata_cli/connections.py` |
| 必須引数 | `NAME` — 保存済み接続の名前 |

## 役割

名前付きで保存した monitor 接続の設定と revision を表示します。接続記録をローカルから読み取るコマンドで、接続先サーバーへの通信や設定変更は行いません。記録に入っているのは credential を参照する環境変数名であり、credential の値は保存も表示もしません。

## 使い方

```sh
# 保存済み接続の内容を人間向けの JSON 表示で確認
strata connection show work

# 成功 envelope を含む機械可読 JSON を取得
strata connection show work --output json
```

`NAME` は小文字の `a-z` で始まり、続けて小文字英字・数字・`_`・`-` を使える1〜64文字の名前です。接続記録の作成には [`strata connection create`](../create/README.md)、一覧には [`strata connection list`](../list/README.md)、編集には [`strata connection set`](../set/README.md) を使います。

## 実行モードと出力

`--output` は `human`（既定）または `json` を選びます。`--json` は `--output json` と同じ JSON 出力を選ぶフラグです。成功時、human モードは `connection` と `revision` を整形して表示し、JSON モードは `schema_version: 1` と `ok: true` を含む envelope を1行で出力します。`--quiet` を human モードで指定すると成功時の標準出力を抑制します。JSON 出力では quiet は抑制を行いません。

## 主な動作と副作用

`show` は `connections.load(NAME)` で接続ファイルを読み、正規化済みのレコードと、そのファイルの生バイト列から得た SHA-256 の先頭16桁の revision を出力します。保存先は `STRATA_CONNECTION_DIR` が設定されていればその絶対パス、それ以外は Windows では `%APPDATA%/Strata/connections`（`APPDATA` がなければユーザーの `AppData/Roaming/Strata/connections`）、その他の OS では `$XDG_CONFIG_HOME/strata/connections`（未設定時は `~/.config/strata/connections`）です。

読み込む記録は4 KiB以下の通常ファイルで、POSIX では所有者専用であることも確認されます。JSON schema version は `1` で、記録は `schema_version`、`id`、`url`、`prefix`、`credential_env` の5項目に限られます。ID は指定名と一致し、URL と prefix は canonical な値である必要があります。読み取りによってファイルを作成・更新・削除する処理はありません。

## 注意点と失敗

- 指定名の接続が存在しない場合、または記録を読み取れない・安全条件や形式検査を満たさない場合は失敗します。これらの接続記録エラーは終了コード `5` です。
- 名前の書式が不正な場合は `ConnectionError` の既定コード `2` で失敗します。
- human モードのエラーは `strata: ...` の形式で標準エラーへ出ます。JSON モードでは `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON が出ます。
- `connections.load` 内で捕捉される読み込み時の `OSError` は「接続ファイルを読み取れない」エラー（コード `5`）に変換されます。そこを通らず `monitor_commands.run` に届く `OSError` はファイル操作エラーとしてコード `6` になります。
- `--url`、`--connection` などの接続先を選ぶ monitor 用オプションはこの `show` parser には登録されていません。

## 関連文書

- [CLI 索引](../../../README.md) — `strata-terminal` のコマンドとオプション文書。
- [`strata connection`](../README.md) — 接続記録の共通仕様と保存先。
- [`--help`（alias: `-h`）](--help.md)、[`--json`](--json.md) — このコマンドで使えるオプションの説明。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection show` parser、必須位置引数 `name`、この parser 群に共通する `--output`、`--json`、`--quiet`。
- `strata_cli/monitor_commands.py:140-146,162-175` — show の読込呼び出し、成功 payload、human/JSON 出力と quiet の扱い。
- `strata_cli/monitor_commands.py:124-129,231-240` — human/JSON エラー表示、接続エラー・値エラー・ファイル操作エラーの処理。
- `strata_cli/cli.py:488-493,2153-2165` — parser 登録と Terminal CLI から共通 monitor command runner への dispatch。
- `strata_cli/connections.py:41-56,72-95` — 名前形式、保存先、`STRATA_CONNECTION_DIR` とディレクトリ検査。
- `strata_cli/connections.py:97-115,124-146` — schema/canonical 値の検証、ファイル条件、読込・revision 計算と失敗経路。

この記述は上記 commit のソースを対象にしています。Release 配布物や別 OS での実行は確認していません。
