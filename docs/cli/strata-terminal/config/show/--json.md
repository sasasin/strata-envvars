# `strata config show --json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config show` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ。指定すると JSON 出力を選ぶ |
| 既定値 | `false` |

## 役割

接続設定の実効値を JSON で標準出力へ出します。設定値の解決方法は変えず、`strata config show` が通常表示する接続 URL、prefix、認証情報を参照する環境変数名、その環境変数に値があるか、各設定の由来などを機械処理しやすい形式にします。

## 使い方

```sh
strata config show --json
```

URL を直接指定する場合も同じです。

```sh
strata config show --url https://strata.example --json
```

接続設定の選択方法やその優先順位は [`--url`](--url.md)、[`--connection`](--connection.md)、[`--credential-env`](--credential-env.md) を参照してください。

## 値と既定値

- `--json` は値を取らない `argparse` の `store_true` オプションです。省略時は `false`、指定時は `true` になります。短縮別名はありません（`strata_cli/monitor_commands.py:96-103`）。
- `--output` の選択肢は `human` と `json`、既定値は `human` です（同 `:101-102`）。ただし `--json` が指定されると、実行側の `machine` 判定が真になるため JSON が選ばれます。明示的に `--output human` を併記しても `--json` が優先します（同 `:167-168`）。
- このコマンドでは JSONL 出力は定義されていません。`--json` を複数回指定しても真偽値のままで、出力形式は変わりません。

## 実行時の動作

CLI の `config show` parser は `monitor_commands.add_connections()` からトップレベル `strata` parser に登録されます。その `show` parser が `--json` と `--output` を定義します（`strata_cli/cli.py:490-493`、`strata_cli/monitor_commands.py:96-103`）。実行時には `machine = a.output in ("json", "jsonl") or a.json` と判定されるため、フラグを指定すると JSON モードになります（`strata_cli/monitor_commands.py:167-168`）。

config 処理は `connections.resolve()` で設定を解決し、JSON モードでは次の形の1行を標準出力へ出して終了コード `0` を返します（`strata_cli/monitor_commands.py:132-139`）。

```json
{"schema_version":1,"ok":true,"effective":{"url":"...","prefix":"...","base_url":"...","credential_env":"...","credential_present":false,"timeout_s":3.0,"connection":null,"connection_revision":null,"origins":{"url":"default","prefix":"default","credential_env":"default","timeout_s":"default"}}}
```

フィールドの値は実行環境で解決されます。たとえば、保存済み接続を選択すると URL・prefix・認証環境変数名の由来は `connection` になります。未指定時は URL が `STRATA_URL` または `http://127.0.0.1:8095`、認証環境変数名が `STRATA_API_KEY` から解決されます。出力するのは環境変数名と `credential_present` の真偽値であり、認証情報の値そのものではありません（`strata_cli/connections.py:273-303`）。

JSON 出力は `ensure_ascii=False` でシリアライズされます。`--quiet` を併記しても JSON は抑制されません。`quiet` は human 出力時のみ有効で、config 解決が標準出力に書く内容を一時的に捕捉しますが、`machine` が真なら捕捉されません（`strata_cli/monitor_commands.py:137-139,167-175`）。

## 適用条件と副作用

- `--json` は `config show` の出力形式だけに作用します。URL、接続設定の選択、credential の参照先、timeout の値は、このフラグでは変更されません。
- `config show` は `connections.resolve()` を呼び、選択された接続記録があれば読み込みます。実装上、この分岐では接続先への HTTP 要求は行わず、設定ファイルや環境変数から実効設定を組み立てます（`strata_cli/monitor_commands.py:132-139`、`strata_cli/connections.py:273-303`）。
- `--effective` も同じ parser にありますが、処理はフラグ値にかかわらず常に実効設定を出力します。従って `--json` が `--effective` を有効化する仕組みではありません（`strata_cli/monitor_commands.py:98-103,132-139`）。

## 出力とエラー

- 成功時は `schema_version: 1`、`ok: true`、`effective` を持つ JSON オブジェクト1行を stdout に出し、終了コード `0` です（`strata_cli/monitor_commands.py:132-139`）。
- 接続 URL と接続名の同時指定、無効な timeout、壊れた接続記録など `ConnectionError` / `ValueError` が起きると、JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":N,"message":"..."}}` を stdout に出します。timeout は `0 < timeout <= 30` 秒でなければならず、接続名と URL の同時指定も拒否されます（`strata_cli/connections.py:273-303`、`strata_cli/monitor_commands.py:124-129,231-236`）。
- 接続解決で使う接続記録の未存在・不正値などは終了コード `5`、その他の値エラーは通常 `2` です。ファイルシステムの I/O エラーは終了コード `6` の JSON エラーとして処理されます（`strata_cli/connections.py:128-146`、`strata_cli/monitor_commands.py:231-240`）。
- `--json` を認識しない引数など parser エラーは、Terminal CLI の `parse_known_args()` 後に `argparse` の `error()` を呼び、usage とエラー表示を行ってコマンド処理前に終了します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:490-493` — config parser 群を Terminal CLI に登録。
- `strata_cli/monitor_commands.py:96-103` — `strata config show` の parser、`--json` と `--output` の定義。
- `strata_cli/monitor_commands.py:132-139,167-175` — JSON モード判定、実効設定の生成と標準出力。
- `strata_cli/connections.py:273-303` — 接続設定の選択、既定値、由来、timeout 検証、出力データ。
- `strata_cli/monitor_commands.py:124-129,231-240` — JSON エラーと例外処理。
- `strata_cli/cli.py:2223-2231` — parser の実行と未知引数のエラー処理。
