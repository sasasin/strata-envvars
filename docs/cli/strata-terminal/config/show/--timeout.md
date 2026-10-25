# `strata config show --timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。

## 概要

接続設定を表示する `strata config show` で、表示される実効設定の `timeout_s`（秒）を指定します。この値はクライアント設定として解決結果に含まれます。このコマンド自体はサーバーへリクエストしません。

## 使い方

```sh
strata config show --timeout 5
strata config show --connection office --timeout 10 --json
```

## 値と既定値

- 値は秒数を表す浮動小数点数です。parser は `float` として読み取ります。
- 指定できる範囲は `0 < 秒数 <= 30` です。未指定時は `3.0` 秒です。
- `0`、負数、30を超える値、数値に変換できない値は受理されません。`nan` も範囲判定を満たさず拒否されます。

## 実行時の動作

`config show` の parser は接続関連オプションを共通定義から追加し、その中で `--timeout` を任意の `float` として受理します。実行時には `connections.resolve()` が値を検証し、`timeout_s` とその由来（`origins.timeout_s` が `flag` または `default`）を解決結果に入れます。人向け出力でも JSON 形式の設定オブジェクトとして表示され、`--json` を指定した場合は `schema_version` と `ok` を含む機械向け envelope になります。

`--timeout` は `--url`、`--connection`、`--credential-env` と併用できます。`--connection` を選ぶと保存済み接続の URL・prefix・credential 環境変数参照が使われます。`--url` と `--connection` は同時指定できず、同時指定はエラーです。接続の選択とは独立して、明示した `--timeout` が timeout の値になります。未指定なら既定値 `3.0` が使われます。

`--effective` は「解決済み設定を表示する」フラグとして受理されますが、`config show` は指定の有無にかかわらず同じ解決結果を表示します。`--quiet` を付けると通常出力は抑制され、`--json` を付けると機械向け出力になります。

このコマンドは解決済み設定を表示して終了します。`Endpoint` の作成や HTTP 通信は行わないため、`--timeout` はこの表示操作の待ち時間を制限するものではありません。後続の接続クライアントが使う timeout 設定を確認・上書きする値です。

## 適用条件と副作用

値の範囲検証後、URL と prefix の正規化や、指定された保存済み接続の読み込みを行います。成功時にこのコマンドが設定ファイルや環境変数を書き換える処理はありません。保存済み接続名が不正・未読込、または接続設定が不正な場合は、解決に失敗します。

## 出力とエラー

- 成功時は実効設定を stdout に JSON として表示し、終了コード `0` を返します。`--json` では成功 envelope に包みます。
- timeout が範囲外なら `timeout must be greater than zero and at most 30 seconds`、`--url` と `--connection` の併用なら `choose --url or --connection, not both` をエラーとして出し、終了コード `2` になります。通常出力ではエラーは stderr、`--json` ではエラー envelope が stdout に出ます。
- 保存済み接続の読込エラーなども `ConnectionError` として処理されます。個々のファイル状態に応じた文言・終了コードは接続データと失敗箇所によるため、ここでは一律の結果を断定しません。

## 根拠

- `strata_cli/monitor_commands.py:20-25,96-103` — 接続共通オプションの parser 定義と `config show` への適用。
- `strata_cli/monitor_commands.py:124-139,167-175,231-240` — 接続解決、表示形式、エラー処理。
- `strata_cli/connections.py:273-303` — 接続選択、timeout の検証、既定値・由来を含む設定の生成。
- `strata_cli/cli.py:139-140,2165,2217-2235` — 共通 parser 登録と Terminal CLI からの dispatch。
- `strata_cli/client.py:85-95,101-110` — 後続の `Endpoint` が timeout を検証し、HTTP リクエストに適用する処理。`config show` 自体はこの `Endpoint` を呼び出さない。
