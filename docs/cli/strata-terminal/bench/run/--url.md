# `--url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--url` |
| 別名 | なし |
| 値 | `URL`（Strata server の root URL） |

## 役割

保存済み profile を使わず、すでに稼働している Strata server をベンチマーク対象にします。`--profile` との相互排他グループに属し、どちらか一方が必須です。`--suite` を省略すると `standard-v1` が選ばれます（`strata_cli/cli.py:293-300`）。

## 使い方

```sh
strata bench run --url http://127.0.0.1:8080
```

`--suite` を省略した例です。serving suite を使うときは出力先も指定します。

```sh
strata bench run --url http://127.0.0.1:8080 --suite serving-smoke --out ./bench-smoke-run
```

## 値と既定値

`--url` は文字列値を1つ取ります。既定値はなく、`--profile` とちょうど一方の指定が必要です。省略して両方指定しない場合や、両方指定した場合は `argparse` が引数エラーにします（`strata_cli/cli.py:294-296`）。

値は `http://` または `https://` の server root でなければなりません。hostname が必要で、URL 内埋め込み資格情報（`user:password@host`）、root 以外の path、query、fragment は拒否されます。port は省略できますが、形式が不正なら拒否されます。非 HTTPS は `localhost`、`127.0.0.1`、`::1` に限り受理されます。受理後は scheme と小文字化した host、port を使う形に正規化されます（`strata_cli/client.py:45-63`）。

## 実行時の動作

- `standard-v1` では URL を `server_url()` で正規化してベンチマーク対象にします。profile を指定していないため、既存 server を相手にし、`--url` 経由で engine を起動する処理はありません（`strata_cli/cli.py:1253-1271,1286-1305`）。
- serving suite では profile 分岐を通らず、`a.url` を HTTP endpoint と telemetry endpoint に設定します。認証情報は `--credential-env` が指定する環境変数から取得され、既定名は `STRATA_API_KEY` です（`strata_cli/cli.py:312,1183-1188,1197-1218`）。`Endpoint` の生成時にも URL が検証されます（`strata_cli/client.py:84-95`）。
- `--url` は接続先を選ぶ指定であり、その server へ実際にリクエストを行います。標準 suite は server の health、props、status、metrics を読み、ベンチマーク workload を実行します（`strata_cli/bench_standard.py:766-803,841-849`）。標準 suite では loopback 外の server は記録上 nonconforming とされます（`strata_cli/bench_standard.py:793-795`）。
- URL 指定時には profile 由来の設定・API key の取得や profile の benchmark lease は適用されません（`strata_cli/cli.py:1200-1220,1255-1271,1282-1289`）。

## 適用条件と副作用

`--suite` が既定の `standard-v1` の場合、`--concurrency`、`--repeat`、`--request-timeout`、`--condition`、`--require-managed-match`、`--telemetry-credential-env` は標準プロトコルと併用できず、指定するとコード 2 で失敗します（`strata_cli/cli.py:1241-1248`）。この suite は稼働中でモデルをロード済みの Strata server を要求し、レポートを新規ディレクトリに作成します（`strata_cli/bench_standard.py:781-785,834-840`）。

他の serving suite では `--out` が必要です。URL 指定の場合も server に対し測定リクエストが送られ、結果ディレクトリに `results.json` が作成されます（`strata_cli/cli.py:1188-1190,1214-1234`、`strata_cli/bench.py:744-792,884`）。

## 出力とエラー

URL の形式エラーは `ValueError` として扱われ、エラーメッセージを stderr に出してコード 2 で終了します。標準 suite は開始前の health / loaded model / props の確認に失敗すると `ProfileError` のコード（該当する確認では 5）で終了します。実行後にレポートが不成功、または起動した engine を停止できない場合はコード 6 です（`strata_cli/bench_standard.py:781-789`、`strata_cli/cli.py:1312-1328`）。serving suite は成功した場合 0、レポートが不成功の場合 6 を返します。通信・認証エラーなどの `ClientError` はその例外の終了コード（既定 3、認証・権限エラー 4）で終了します（`strata_cli/client.py:38-42,117-125`）。`--output json` の場合は標準出力に機械可読 JSON を出し、一般の例外エラーは JSON モード時も標準出力にエラーオブジェクトを出します（`strata_cli/cli.py:527-532,1226-1234,1312-1328,2166-2188`）。

## 根拠

- `strata_cli/cli.py:291-300` — `bench run` parser、`--profile` との排他・必須指定、suite 既定値。
- `strata_cli/cli.py:1183-1234` — serving suite の validation、URL の選択、endpoint 作成、実行と結果出力。
- `strata_cli/cli.py:1237-1328` — standard suite の非対応オプション、URL から対象を作る処理、実行・終了コード。
- `strata_cli/client.py:45-63,84-95` — URL の形式・HTTPS 制約と Endpoint での検証。
- `strata_cli/bench_standard.py:766-803,834-849` — standard suite の server 前提、loopback 条件、リクエストと出力先作成。
- `strata_cli/bench.py:744-792,884` — serving suite の測定と結果ファイル出力。
- `strata_cli/cli.py:527-532,2166-2188` — エラー出力と例外終了コード。

この文書は checkout のソースを根拠にしています。同一 revision の CLI `--help` と Release 配布物は実行・照合していません。
