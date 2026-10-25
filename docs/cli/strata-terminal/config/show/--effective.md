# `--effective`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config show` |
| オプション | `--effective` |
| 別名 | なし |
| 値 | 値を取らないフラグ。`argparse` の `store_true`。 |

## 役割

接続先、接続設定の出所、資格情報を参照する環境変数名とその値が設定済みかどうかを表示するコマンドのフラグです。ただし現在の実装では `--effective` の有無を処理側が参照せず、`strata config show` はフラグを省略しても同じ解決済み設定を表示します。したがってこのフラグ単独で表示内容や処理は変わりません。parser は `default=False` の `store_true` として定義されています（`strata_cli/monitor_commands.py:96-103,132-139`）。

## 使い方

```sh
strata config show --effective --url http://127.0.0.1 --output json
```

接続設定を解決して表示しますが、このコマンド自体はサーバーへ接続しません。

## 値と既定値

- 値は不要です。指定すると parser の `a.effective` が真になり、省略時は偽です（`strata_cli/monitor_commands.py:98-99`）。
- 同じ parser に `--url`、`--connection`、`--credential-env`、`--timeout` が定義されています（`strata_cli/monitor_commands.py:20-26,98-103`）。`--url` と `--connection` の同時指定は拒否されます。
- `--output` は `human`（既定）または `json`、`--json` は JSON 出力の別表記です（`strata_cli/monitor_commands.py:101-103,168-175`）。`--quiet` は人向け出力を抑制します。JSON 出力時は quiet 指定でも結果を表示します（同 `:168-175`）。

## 実行時の動作

コマンド処理は `connections.resolve(...)` を呼び出し、解決した値を `effective` キーに含めて出力します。`--effective` を条件にした分岐はなく、出力は常に解決済み設定です（`strata_cli/monitor_commands.py:132-139`）。

解決の優先順位と表示される主な値は次のとおりです（`strata_cli/connections.py:273-303`）。

- `--url` または `--connection` が指定されていれば、それを使います。両方を指定すると `choose --url or --connection, not both` で失敗します（`:277-280`）。
- どちらも指定しない場合、`STRATA_CONNECTION`、`STRATA_URL`、既定 URL `http://127.0.0.1:8095` の順で接続先を決めます。保存済み connection を使う場合は、その URL・prefix・資格情報環境変数名を読みます（`:277-291`）。
- 保存済み connection を選んだ場合を除き、資格情報の参照先は既定で `STRATA_API_KEY` です。`--credential-env NAME` は参照先名を上書きします。表示するのは環境変数名と `credential_present`（値が空でないか）であり、資格情報の値そのものではありません（`:289-301`）。
- timeout は `--timeout` がなければ `3.0` 秒です。指定値は `0 < timeout <= 30` を満たす必要があります（`:295-302`）。
- 解決結果には `url`、`prefix`、`base_url`、`credential_env`、`credential_present`、`timeout_s`、connection 名・revision、および各値の `origins` が含まれます（`:297-303`）。JSON モードでは `{ "schema_version": 1, "ok": true, "effective": ... }`、human モードでは解決結果オブジェクトを整形して出します（`strata_cli/monitor_commands.py:136-138`）。

URL は HTTP(S) のサーバールートであること、埋め込み認証情報・パス・query・fragment がないことを検証します。非 HTTPS は localhost または loopback のみ許可されます（`strata_cli/client.py:45-63`）。保存 connection の prefix にも単純なパス要素のみを許す検証があります（`strata_cli/client.py:66-76`; `strata_cli/connections.py:97-114`）。

## 適用条件と副作用

この操作はローカルで設定を解決して表示し、HTTP request は行いません。保存済み connection を指定するか `STRATA_CONNECTION` で選択した場合は、設定ファイルを読み取ります。`--effective` の有無による副作用の差はありません（`strata_cli/monitor_commands.py:132-139`; `strata_cli/connections.py:128-146,273-303`）。

## 出力とエラー

- 通常は成功時に終了コード `0` です。`--output json` または `--json` では成功・失敗とも versioned JSON を使います。通常の失敗は標準エラーに `strata: ...` として出力します（`strata_cli/monitor_commands.py:124-129,168-175,231-240`）。
- URL と connection の競合、timeout の範囲外、URL・prefix・環境変数名の不正などは設定解決エラーになります。保存設定が見つからない、読み込めない、または不正な場合も失敗します。`ConnectionError` は設定された終了コード（一般に引数・値の不正は `2`、保存設定の問題は `5`）で返され、その他の `ValueError` は `2`、`OSError` は `6` です（`strata_cli/connections.py:47-69,128-146,273-303`; `strata_cli/monitor_commands.py:231-240`）。
- 未知のオプションなど parser の引数エラーは `argparse` が処理します。`--effective` に値を付ける構文は受け付けません（`strata_cli/monitor_commands.py:98-103`; `strata_cli/cli.py:2217-2231`）。

## 根拠

- `strata_cli/monitor_commands.py:96-103` — `config show` parser と `--effective` の定義。
- `strata_cli/monitor_commands.py:132-139,168-175,231-240` — 解決結果の出力、quiet/JSON、エラー経路。
- `strata_cli/connections.py:273-303` — 優先順位、既定値、設定値と origin の組み立て。
- `strata_cli/connections.py:128-146` — 保存 connection の読み込みと失敗条件。
- `strata_cli/client.py:45-76` — URL と reverse-proxy prefix の検証。
- `strata_cli/cli.py:490-493,2217-2231` — Terminal CLI への parser 登録と引数処理。
- `docs/TERMINAL.md:30-44` — 接続設定の利用例と利用者向け説明（補助資料）。
