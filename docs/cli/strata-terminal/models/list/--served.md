# `--served`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--served` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は無効 |

## 役割

ローカルのインストール済みモデル設定を列挙する代わりに、指定または解決された Strata サーバーへ接続し、現在のインスタンスが報告するモデルを表示します。取得範囲は現在のインスタンスだけで、インストール済みモデル全体の一覧ではありません（`strata_cli/cli.py:564-585`）。

## 使い方

ローカルサーバーの既定アドレスを調べる例です。

```sh
strata models list --served
```

別の HTTPS サーバーを指定し JSON で受け取る例です。

```sh
strata models list --served --url https://strata.example --output json
```

parser では `--served` は `store_true` で定義され、`--installed` と相互排他です。同じコマンドで両方を指定すると argparse の引数エラーになります（`strata_cli/cli.py:143-152`）。

## 値と既定値

- 値は不要です。省略時は `False` となり、通常のローカル設定一覧へ進みます。指定するとサーバー照会の分岐へ進みます（`strata_cli/cli.py:145-146,564-588`）。
- `--served` と同時に `--install-dir` を指定すると終了コード 2 で拒否されます。`--install-dir` はローカル一覧用です（`strata_cli/cli.py:566-567`）。
- `--url`、`--connection`、`--credential-env`、`--timeout` は `--served` と組み合わせて使用します。これらを `--served` なしで指定すると終了コード 2 になります（`strata_cli/cli.py:586-587`）。
- `--url` と `--connection` は同時指定できません。未指定時は `STRATA_CONNECTION`、それがなければ `STRATA_URL`、最後に `http://127.0.0.1:8095` の順で接続先を解決します（`strata_cli/connections.py:273-290`）。
- 接続先 URL は `http` または `https` のサーバールート形式で、埋め込み認証情報、パス、query、fragment は受け付けません。非 loopback の接続先には HTTPS が必要です（`strata_cli/client.py:45-63`）。保存済み connection を使う場合、その prefix も接続先に追加されます（`strata_cli/connections.py:280-301`）。
- timeout は秒単位の浮動小数で、既定値は 3 秒、指定可能範囲は 0 より大きく 30 以下です。範囲外は `ConnectionError` として拒否されます（`strata_cli/cli.py:151`, `strata_cli/connections.py:295-303`）。

## 実行時の動作

接続情報を解決した後、選択された環境変数から bearer credential を読み、`Endpoint.snapshot()` で読み取り専用の状態を取得します。既定の credential 環境変数は `STRATA_API_KEY` です。保存済み connection では記録された環境変数名が使われ、`--credential-env` があればその名前で上書きされます。credential の値自体は接続設定から読まず、HTTP `Authorization: Bearer ...` ヘッダーとして使用します（`strata_cli/connections.py:280-303`, `strata_cli/cli.py:568-573`, `strata_cli/client.py:101-110`）。

接続処理は `GET /v1/telemetry` を先に試します。HTTP 404 の場合に限り `/metrics` と `/v1/status` による旧形式の読み取りへ fallback し、metrics も 404 なら status のみを使います。他の HTTP エラーでは fallback せず失敗します。応答には JSON を要求し、本文は 2 MiB までに制限され、redirect は追従しません（`strata_cli/client.py:101-152`）。

応答から現在のモデル ID が報告されている場合だけ1行のモデル項目を作り、`loaded` 状態、instance ID、`execution_compatibility: "unverified"` を付けます。ID がない場合は空一覧です。人間向け出力では `loaded`、`unloaded`、または `load state unknown` を表示し、モデル ID がなければ `No model ID reported by this server` と表示します（`strata_cli/cli.py:573-585`, `strata_cli/client.py:363-403`）。

`--output` は `human`（既定）または `json` を選びます。one-shot parser では `--json` が `--output json` の alias として追加されています。JSON 成功応答には `scope: "served_current_instance"`、サーバー URL、モデル配列、件数、インストール済み一覧ではない旨が含まれます（`strata_cli/cli.py:510-515,535-542,578-585`）。

## 適用条件と副作用

- 照会はサーバーが稼働し、認証・権限が許可され、対象 endpoint が利用できる場合に成功します。読み取りは現在のインスタンス情報だけで、モデルのロード・アンロードや再起動を行う処理はこの分岐にはありません（`strata_cli/cli.py:568-585`, `strata_cli/client.py:101-152`）。
- HTTP 呼び出しは read-only telemetry contract に列挙された GET endpoint に限定されています（`strata_cli/client.py:101-110`）。
- 遠隔サーバーへの平文 HTTP は拒否されます。loopback（`localhost`、`127.0.0.1`、`::1`）は HTTP を使用できます（`strata_cli/client.py:58-63`）。

## 出力とエラー

- 成功時の終了コードは 0 です。人間向け出力は標準出力、JSON 出力は `schema_version: 1` と `ok: true` を含む1行の JSON です（`strata_cli/cli.py:535-542,581-585`）。
- `--install-dir` との併用、接続フラグの `--served` なし指定、URL と connection の競合、timeout 範囲外などの入力エラーは通常コード 2 です。エラーは人間向けなら標準エラー、JSON なら `ok: false` のオブジェクトに出力されます（`strata_cli/cli.py:527-532,566-570,586-587,2166-2173`, `strata_cli/connections.py:278-296`）。
- 接続失敗、通常の HTTP エラー、redirect、JSON 形式エラーは `ClientError` として既定コード 3、401/403 はコード 4、互換性のない telemetry schema はコード 5 です。終了時には `_run` がエラーを人間向けまたは JSON 形式で報告します（`strata_cli/client.py:38-42,117-143`, `strata_cli/cli.py:2184-2188`）。
- argparse が認識しない引数は `main()` の解析時に usage とエラーを出して終了します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:141-152`
- `--served` の分岐、適用条件、結果の組み立てと出力: `strata_cli/cli.py:564-596`
- URL、connection、credential 環境変数、timeout の解決: `strata_cli/connections.py:273-303`
- URL 制約、認証 header、HTTP request と snapshot fallback: `strata_cli/client.py:45-152`
- telemetry から model ID / loaded state を正規化する処理: `strata_cli/client.py:363-403`
- 成功・失敗形式と例外の終了コード: `strata_cli/cli.py:527-542,2166-2188`

## 調査範囲

ソース parser と処理経路を確認しました。`--help` の実行、サーバーへの接続、Release artifact の照合は行っていません。したがって接続先固有の応答内容や配布バイナリでの差異は確認対象外です。
