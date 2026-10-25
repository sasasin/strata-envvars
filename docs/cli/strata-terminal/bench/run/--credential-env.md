# `--credential-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--credential-env` |
| 別名 | なし |
| 値 | 環境変数名。値は省略不可 |

## 役割

環境変数名を指定し、その環境変数に設定されたサーバー API credential をベンチマーク要求に使います。CLI 引数には credential の値でなく環境変数名を渡します。`strata bench run` 配下で定義され、全 suite で認識されます（`strata_cli/cli.py:291-314`）。環境変数自体の説明は [`STRATA_API_KEY`](../../../../STRATA_API_KEY.md) を参照してください。

## 使い方

```sh
export STRATA_API_KEY='サーバーの API credential'
strata bench run --url http://127.0.0.1:8000 --credential-env STRATA_API_KEY \
  --suite serving-smoke --out ./bench-results/serving-smoke-example
```

出力先ディレクトリは新規である必要があります。ベンチマークは実際に対象サーバーへ要求を送ります。引数の値は `STRATA_API_KEY` のような環境変数名にし、credential 自体をコマンドラインへ書かないでください（`strata_cli/cli.py:312-314`, `strata_cli/bench.py:744-760, 792-802`）。

## 値と既定値

- 既定値は `STRATA_API_KEY` です。値を取るオプションで、短縮 alias はありません（`strata_cli/cli.py:312`）。
- 実行時に `str.isidentifier()` で名前を検証します。無効なら `credential options must name environment variables` を返し、終了コード `2` になります（`strata_cli/cli.py:1183-1185, 1249-1250`; 共通エラー出力は `strata_cli/cli.py:527-532`）。
- 名前が有効でも、その環境変数が未設定または空なら、serving suite では credential なしで接続します。標準 suite の `--profile` 経路では後述の profile 設定からの fallback があります（`strata_cli/cli.py:1215-1218, 1255-1267`）。

## 実行時の動作

credential は `os.environ.get(<指定名>)` で読み出され、HTTP `Authorization: Bearer <credential>` ヘッダーに使われます。serving suite では通常の要求およびキャンセル用要求の両方で同じ endpoint credential を使います（`strata_cli/cli.py:1215-1218`; `strata_cli/bench.py:223-234, 306-318`）。標準 suite では `Target` が同じ形式のヘッダーを作成します（`strata_cli/bench_standard.py:132-152`）。

未設定時の挙動は suite と接続方法で異なります。

- `--suite standard-v1`（既定）で `--url` を使う場合、指定環境変数の値だけを使います。空または未設定なら credential を送信しません（`strata_cli/cli.py:1255-1271`）。
- `standard-v1` で `--profile` を使う場合、環境変数の値が空で、profile の `api_key` 設定も空でなく `none` でもなければ、その設定から最初の API key を取得して使います（`strata_cli/cli.py:1255-1267`）。環境変数に値があれば profile 側より優先されます。
- `--suite serving-smoke` など標準以外の serving suite では、指定環境変数の値が endpoint credential です。profile 設定の `api_key` への fallback はありません。`--telemetry-credential-env` を指定すると telemetry 用の別 credential を読み、指定しなければ `--credential-env` と同じ credential を telemetry にも使います（`strata_cli/cli.py:1213-1218`）。標準 suite では `--telemetry-credential-env` は適用できず、指定すると終了コード `2` のエラーになります（`strata_cli/cli.py:1241-1248`）。

標準 suite は外部プロセスに credential を引数として渡すのではなく、要求ヘッダーに設定します。保存レポートには credential の値でなく、送信の有無を表す `api_key_sent` が記録されます（`strata_cli/bench_standard.py:148-152, 949`）。

## 適用条件と副作用

サーバー要求の認証にだけ使われます。標準 suite は `/health`、`/props`、`/v1/status`、`/metrics` の取得と benchmark request を行います（`strata_cli/bench_standard.py:781-801, 181-192`）。serving suite は telemetry snapshot の取得と `/v1/chat/completions` への要求を行います（`strata_cli/bench.py:223-234, 744-760, 757-760`）。したがって、正しい環境変数名を指定しても、credential がサーバーに受理されることや必要な権限があることまでは保証しません。

標準 suite の `--profile` 経路では、対象サーバーが未起動ならベンチマーク中に engine を起動し、終了時に停止します。すでに応答するサーバーを使う場合は停止しません。これはこのオプション固有の副作用ではなく、`standard-v1` の profile 実行条件です（`strata_cli/cli.py:1237-1239, 1292-1307`）。

## 出力とエラー

- 無効な環境変数名は終了コード `2`。`--output json`（`--json` alias）では JSON error、通常表示では stderr にエラーを出します（`strata_cli/cli.py:1183-1185, 527-532`; `strata_cli/cli.py:508-515`）。
- `standard-v1` はサーバーが応答しない、モデル未ロード、または `/props` に応答しない場合に終了コード `5` の失敗となります。`/props` の失敗メッセージは API key が必要な可能性を案内します（`strata_cli/bench_standard.py:781-789`）。
- serving suite では telemetry 認証・権限エラーは `ClientError` として報告されます。要求を実行した後は `results.json` に成功状態・各 phase の結果を書き、失敗した suite は終了コード `6` になります（`strata_cli/client.py:104-125`; `strata_cli/bench.py:843-888`; `strata_cli/cli.py:1221-1234`）。

## 根拠

- parser、既定値、suite 分岐、環境変数読み出し: `strata_cli/cli.py:291-314, 1129-1234`
- 標準 suite の環境変数優先順位、profile fallback、engine 起動・停止: `strata_cli/cli.py:1237-1307`
- serving suite の要求ヘッダー・telemetry: `strata_cli/bench.py:223-234, 306-318, 744-760`; `strata_cli/client.py:101-125`
- 標準 suite の要求ヘッダー・レポート記録・接続失敗: `strata_cli/bench_standard.py:132-164, 781-790, 949`
