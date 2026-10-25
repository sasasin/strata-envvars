# `--telemetry-credential-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--telemetry-credential-env` |
| 別名 | なし |
| 値 | 環境変数名。Python の `str.isidentifier()` に合格する名前 |
| 既定値 | `None`（未指定） |

## 役割

serving suite がサーバーの `/v1/telemetry` を読むときに使う資格情報の環境変数名を指定します。推論リクエスト用資格情報とは別の変数を選べます。たとえば telemetry 専用キーを使うときは、値そのものをコマンドラインに書かず、変数名を渡します。

## 使い方

```sh
STRATA_API_KEY='推論用キー' STRATA_TELEMETRY_KEY='読み取り用キー' \
  strata bench run --url http://127.0.0.1:8080 \
  --suite serving-smoke --out ./bench-smoke \
  --telemetry-credential-env STRATA_TELEMETRY_KEY
```

この例ではローカルの既存サーバーに接続します。`--url` と `--profile` は同時に指定できず、どちらか一方が必要です。serving suite は `--out` に新規ディレクトリを必要とします。

## 値と既定値

- parser は値を1つ受け取り、既定値は `None` です。parser 定義に `choices`、型変換、`metavar`、オプション固有の help 文はありません。(`strata_cli/cli.py:291-314`)
- `strata bench run` の処理は、環境変数名について Python の `isidentifier()` を検査します。不適合なら `credential options must name environment variables` を返して終了コード 2 になります。(`strata_cli/cli.py:1183-1185`)
- 値は環境変数名であり、資格情報の実値ではありません。変数が未設定なら `os.environ.get()` は `None`、設定値が空文字なら `""` です。`Endpoint` は資格情報が truthy な場合だけ Bearer 認証ヘッダーを追加します。したがって空文字は認証ヘッダーなしとして扱われます。(`strata_cli/cli.py:1215-1218`; `strata_cli/client.py:101-107`)
- この名前自体は値を trim したり、変数の存在を必須にしたりしません。変数名を指定したのに未設定でも parser の validation は通ります。

## 実行時の動作

- 値を省略すると、telemetry endpoint は `--credential-env` が指す変数の値を推論 endpoint と telemetry endpoint の両方に使います。`--credential-env` の既定名は `STRATA_API_KEY` です。(`strata_cli/cli.py:312-313, 1215-1218`)
- 値を指定すると、telemetry endpoint はその名前の環境変数だけを参照します。変数が未設定または空なら認証なしになり、推論用キーへの fallback はしません。推論リクエストの `endpoint` は引き続き `--credential-env` の値を使います。(`strata_cli/cli.py:1215-1218`; `strata_cli/bench.py:223-235, 602-604`)
- benchmark runner は開始前に telemetry snapshot を取得し、インスタンス ID がありモデルがロード済みであることを確認します。その後、各 serving phase で snapshot を定期取得し、sample を結果に記録します。資格情報は `Endpoint` の Authorization ヘッダーに渡され、レポートの telemetry sample には資格情報そのものを含めません。(`strata_cli/bench.py:744-760, 576-588, 643-646`; `strata_cli/client.py:101-107`)
- `Endpoint.snapshot()` は `/v1/telemetry` を優先し、HTTP 404 の場合に限って旧形式として `/metrics` と `/v1/status` を試します。401/403 などは fallback 条件ではありません。(`strata_cli/client.py:134-152`)

## 適用条件と副作用

- 対象は serving suite です。既定 suite の `standard-v1` では workload の条件が固定され、この option は適用されません。空でない値を指定すると `--telemetry-credential-env do not apply to the standard suite...` となり終了コード 2 です。(`strata_cli/cli.py:1186-1188, 1241-1248`)
- serving suite で値に空文字を渡すと、環境変数名の検査を通過し、資格情報なしになります。`standard-v1` では空文字でも値が明示された扱いとなり、fixed-option 検査で拒否されます。(`strata_cli/cli.py:1183-1188, 1241-1248, 1217-1218`)
- serving suite は `/v1/telemetry` 等の読み取り endpoint を問い合わせ、推論 workload は別 endpoint に送ります。オプション自体は環境変数やサーバー設定を変更しません。benchmark は出力先に `progress.json` と `results.json` を作成するため、`--out` は未使用の新規ディレクトリを指定してください。初回 snapshot と preflight を通過するまでは出力ディレクトリを作りません。(`strata_cli/bench.py:755-760, 792-802, 884-887`; `strata_cli/cli.py:1219-1225`)
- telemetry 用の環境変数は CLI 起動時に読み込まれ、実行中の環境変更は既に生成された `Endpoint` の資格情報には反映されません。(`strata_cli/cli.py:1215-1218`)

## 出力とエラー

- 無効な環境変数名、`standard-v1` での指定、または serving suite での `--out` 省略は終了コード 2 の CLI エラーです。(`strata_cli/cli.py:1183-1189, 1241-1248`)
- telemetry 認証の HTTP 401/403 は `ClientError` の終了コード 4（認証または権限エラー）になります。接続失敗等は通常終了コード 3 です。初回 snapshot の認証失敗など `bench.run()` で捕捉されないエラーは CLI のエラー出力に進み、benchmark 出力ディレクトリ作成前に終了します。(`strata_cli/client.py:38-40, 117-125`; `strata_cli/bench.py:757-760, 792`; `strata_cli/cli.py:2184-2188`)
- phase 中の通常 telemetry poll 失敗は `telemetry_sample_errors` に数えられ、その sample は欠落扱いです。終了時 snapshot が失敗すると `after` は空になり、結果は成功と判定されませんが、`results.json` は保存され得ます。キャンセル suite は必要な telemetry の喪失を別途失敗として扱います。(`strata_cli/bench.py:576-588, 843-887`; `strata_cli/bench.py:427-433`)
- `--output json` の場合、成功時は標準出力に結果概要と evidence path を出します。JSON のエラーは標準出力に JSON、human のエラーは標準エラーに `strata: ...` を出します。human 成功時は概要と evidence path を表示します。(`strata_cli/cli.py:527-542, 1226-1234, 2184-2188`)

## 関連資料

`STRATA_TELEMETRY_KEY` のサーバー側設定や monitor/status での利用は [環境変数文書](../../../../STRATA_TELEMETRY_KEY.md) を参照してください。同文書の調査 revision は本書と異なるため、ここでは上記 CLI の挙動を本書記載の commit のソースで確認しています。

## 根拠

- parser、既定値、環境変数名の検査、suite 別の制約、endpoint への資格情報設定: `strata_cli/cli.py:291-314, 1183-1225, 1241-1250`。
- Bearer header、HTTP エラー、snapshot fallback: `strata_cli/client.py:84-152`。
- benchmark の推論リクエスト、telemetry polling、初回条件、progress/report の作成・保存: `strata_cli/bench.py:223-235, 549-650, 744-802, 843-888`。
- コマンド階層と索引上の option scope: `docs/cli/README.md:610-641`（作業リポジトリ、調査対象 Strata checkout ではなく文書配置先）。
