# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection set` |
| オプション | `--json` |
| 別名 | なし（`--output json` も指定可能） |
| 値 | 値なしの真偽フラグ。省略時は `false` |

## 役割

接続設定の更新結果を JSON で stdout に出力します。出力形式を変えるフラグであり、更新の実行／非実行は `--plan` が決めます。`--plan` を付けない場合、`--json` を指定しても接続記録は保存されます。

## 使い方

```sh
strata connection set lab prefix=/strata --json
```

同じ出力形式は `strata connection set lab prefix=/strata --output json` でも選べます。更新を行わず差分を確認する場合は `--plan` を加えます。

## 値と既定値

`--json` は値を取りません。省略時の `--output` は `human` で、受理値は `human` と `json` です。`--json` が真、または `--output json` のとき、接続 set の処理は JSON モードになります。両方を指定した場合も JSON です。`--output jsonl` はこのコマンドでは受理されません。

## 実行時の動作

成功時は `schema_version: 1` と `ok: true` を含む JSON オブジェクトを1行で stdout に出します。通常の更新では `connection`、`previous_revision`、`revision` が含まれます。`--plan` と併用すると `connection`、現在の `revision`、および保存内容が変わるかを示す `would_save` が含まれます。接続データには資格情報そのものではなく、参照する環境変数名が記録されます。

このオプション自体は接続データを変更しません。位置引数 `KEY=VALUE` は `url`、`prefix`、`credential_env` のいずれかで、`propose` が既存記録を読み込んで値を検証します。`--if-revision REVISION` は読み込み時点の revision と照合され、さらに保存時にもロック下で revision が再確認されます。値が現在と同じなら保存ファイルは置き換えられず、revision も変わりません。

## 適用条件と副作用

`--json` は `connection create`、`show`、`list`、`set` の各サブコマンド parser にそれぞれ定義されていますが、この文書の対象は `set` だけです。`--quiet` と同時に指定しても JSON 出力は抑止されません。

`--plan` なしでは、通常の保存先に接続記録を書き換えます。保存先は `STRATA_CONNECTION_DIR`（指定時は絶対パスが必要）、Windows では `%APPDATA%/Strata/connections`、その他では `$XDG_CONFIG_HOME/strata/connections` または `~/.config/strata/connections` です。保存時には接続用ディレクトリとロックファイルを使い、更新内容を一時ファイル経由で置き換えます。`--plan` は提案値の検証と既存値との比較を行いますが、保存処理は呼び出しません。

## 出力とエラー

成功時の JSON 例（revision は説明用の値です）:

```json
{"schema_version":1,"ok":true,"connection":{"schema_version":1,"id":"lab","url":"http://127.0.0.1:8095","prefix":"/strata","credential_env":"STRATA_TELEMETRY_KEY"},"previous_revision":"0123456789abcdef","revision":"fedcba9876543210"}
```

実行時エラーは JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":N,"message":"…"}}` の形で stdout に出ます。入力値の形式不正などは通常コード `2`、記録の欠落や不正・ファイルアクセスなどはコード `5` または `6`、読み込み後に他プロセスが更新した場合はコード `6` です。`--json` や `--output` の構文・値が不正な場合は処理本体より前の argparse エラーとなり、JSON エラー形式にはなりません。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection set` の parser、位置引数、`--plan`、`--if-revision`、`--output`、`--json`、`--quiet` の定義。
- `strata_cli/monitor_commands.py:132-164` — set の提案・revision 照合・plan／保存分岐と JSON 成功出力。
- `strata_cli/monitor_commands.py:167-175,231-240` — JSON モード判定、quiet との関係、接続・値・ファイルエラーの形式と終了コード。
- `strata_cli/connections.py:41-69,245-270` — 接続名・値の検証、更新可能なキー、revision 確認、同値時の扱い、保存。
- `strata_cli/connections.py:72-90,167-188,190-218` — 保存先、ディレクトリ検査、原子的な置き換えとロック。
- `strata_cli/client.py:45-76` — URL と prefix の受理条件。
- `strata_cli/cli.py:27,488-493,2119-2165` — Terminal CLI への parser 登録と `monitor_commands.run` への委譲。
- `strata_cli/cli.py:2217-2237` — CLI の引数解析と `--json` の共通処理。connection 系は `monitor_commands.run` が `--json` を直接判定するため、共通の `a.output = "json"` 変換対象から除外。
