# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存プロファイル名、または run config JSON のパス |

## 役割

ベンチマーク対象の Strata サーバーをローカル設定から特定します。`--url` と相互排他で、どちらか一方が必須です。`--suite` を省略した場合の `standard-v1` では、プロファイルのアドレスに既存サーバーがあれば利用し、応答がなければ既定ではベンチマーク用に起動します。serving suite では、指定プロファイルから接続先を組み立てますが、サーバーの起動は行いません。parser は `strata_cli/cli.py:291-300`、実行分岐は同 `cli.py:1183-1205, 1237-1269, 1292-1305` にあります。

## 使い方

```sh
strata bench run --profile my-profile
strata bench run --profile my-profile --suite serving-smoke --out ./bench-results/my-serving-run
strata bench run --profile ./installed/run-config.json --no-start
```

最初の例は標準 suite です。2つ目は既に稼働しているプロファイルのサーバーに対する serving suite で、`--out` が必要です。3つ目は run config を指定し、標準 suite でサーバーを自動起動しない例です。コマンド例は parser と `_bench` / `_bench_standard` の分岐に基づきます（`strata_cli/cli.py:293-311, 1183-1205, 1237-1285`）。

## 値と既定値

- 値は1つの文字列です。parser は `--profile` と `--url` を required な相互排他グループに登録しており、このオプション自体に既定値はありません（`strata_cli/cli.py:293-296`）。両方を指定すると argparse が拒否します。
- `--profile` の値が `.json` で終わる、絶対パスである、または `/`・`\\` を含む場合は JSON ファイルパスとして扱われ、保存プロファイル名へのフォールバックはしません。それ以外は保存プロファイル名として読み込みます（`strata_control/profiles.py:382-388`）。
- parser の help は「installed run config」と説明しますが、ソースのパス分岐はインストール状態を照会しません。実際に検査するのは JSON の構造と必須 `exe` / `tokenizer` の文字列です（`strata_cli/cli.py:295`; `strata_control/profiles.py:135-147, 382-388`）。
- 保存名は小文字英字で始まり、小文字英字・数字・`_`・`-` のみ、最大64文字です（`strata_control/profiles.py:25, 48-55`）。JSON run config には文字列の `args` 配列と空でない `exe`、`tokenizer` が必要です（同 `profiles.py:135-147`）。
- 同じ `--profile` を複数回指定した場合の独自処理はありません。argparse の通常の単一値引数として最後の値が残ります。空文字列、存在しない名前、読み込めない・形式不正なファイルはプロファイル/設定の解決時に失敗します。

## 実行時の動作

`profiles.resolve()` は保存名ならプロファイルの `source_config` と保存データ・revision を返し、パス指定ならその JSON を直接使います。`_source()` はその run config を読み、`_launch_plan()` は保存プロファイルの override を含めて有効な host / port などを解決します（`strata_control/profiles.py:150-166, 382-388`; `strata_cli/cli.py:545-547, 782-825`）。

suite ごとの使われ方は次のとおりです。

- **`standard-v1`（既定）**: 解決した host / port を接続先にします。`/health` に応答がない場合、`--no-start` がなければ `strata serve --profile <指定値> --quiet` を子プロセスとして起動し、モデルロード完了まで待ちます。既にプロファイルのアドレスで稼働しているサーバーは再利用し、停止しません（`strata_cli/cli.py:297-300, 1253-1271, 1292-1305`; `strata_cli/bench_standard.py:658-695`）。
- **serving suites**: 接続先 URL と profile identity（保存名、revision、設定ファイルの SHA-256 など）を作り、サーバー側 telemetry に接続します。この分岐ではプロファイルからエンジンを起動しません（`strata_cli/cli.py:1186-1225`; `strata_cli/bench.py:744-765`）。
- serving suite で `--require-managed-match` を併用すると、`--profile` が保存名であることが必要です。実行前後に owner 状態、profile/source revision、instance ID、接続先を照合し、一致しなければ事前エラーまたは失敗扱いになります。照合は実行中継続ではなく開始時と終了時のみです（`strata_cli/cli.py:1197-1212`; `strata_cli/bench.py:173-203, 761-765, 852-876`）。このオプションは standard suite には適用できず、指定するとその suite 固有の workload と矛盾するためエラーになります（`strata_cli/cli.py:1241-1248`）。
- 保存プロファイル名を使うと、同じプロファイルのローカル benchmark の重複を防ぐ lease を取得します。JSON パス指定では saved profile がないため、この lease は使われません（`strata_cli/cli.py:1219-1225, 1282-1289`; `strata_control/benchmarking.py:82-95`）。

## 適用条件と副作用

- `standard-v1` で新たに起動した子プロセスは、ベンチ終了時に停止されます。起動できない、または指定秒数内にモデルが ready にならない場合は停止を試みてエラーにします（`strata_cli/cli.py:1285-1311`; `strata_cli/bench_standard.py:673-695, 716-750`）。停止にも失敗すると stderr に警告を出し、結果フォルダーへ `ENGINE-NOT-STOPPED.txt` を書こうとし、終了を失敗扱いにします（`strata_cli/cli.py:1312-1328`）。
- `--no-start` は標準 suite 専用です。プロファイルのアドレスでサーバーが応答しなければ終了コード5のエラーになります。`--load-timeout`（既定1800秒）は1〜86400秒で、起動時のモデル ready 待ち時間です（`strata_cli/cli.py:318-321, 1251-1252, 1292-1299`）。
- 保存プロファイルの読み込みは通常は読み取りですが、管理者実行でロックされたファイルの権限を `read_bytes_repairing()` が一度修復する経路があります（`strata_control/profiles.py:150-166`）。ベンチマーク本体は結果ディレクトリとレポートを作成します。既存出力ディレクトリは拒否されます（`strata_cli/bench_standard.py:777-780, 902-960`; `strata_cli/bench.py:755-756`）。
- standard suite が既存サーバーを使う場合、そのプロセスは停止しません。serving suite も既存サーバーを測定します。プロファイルの指定だけでは、接続中サーバーがその設定から起動されたことは認証されません。managed match を要求しない serving suite のレポートは、選択した profile と稼働設定が照合されていない旨を記録します（`strata_cli/cli.py:1292-1305`; `strata_cli/bench.py:862-876`）。

## 出力とエラー

- 無効な引数・値は通常 stderr に `strata: <message>` を出して、エラーに設定された終了コードで終了します。`--output json` または `--json` では JSON の `ok: false` と `error` を出します（`strata_cli/cli.py:527-532, 2166-2188`）。
- 保存名がない、プロファイル/設定ファイルが読めない、設定形式が不正、`--no-start` 時にサーバー不在、またはベンチに必要な稼働サーバー情報がない場合に失敗します。ProfileError の既定コードは2で、解決・I/O・稼働条件ではコード5や6も使われます（`strata_control/profiles.py:30-35, 135-166`; `strata_cli/cli.py:1292-1299, 2166-2188`）。
- ベンチマーク中の進捗ログは stderr に出し、成功時は標準出力に要約または JSON 結果を出します。standard suite は結果ディレクトリに `results.json` と `README.md` を作成します（`strata_cli/cli.py:1289-1291, 1321-1328`; `strata_cli/bench_standard.py:958-960`）。

## 根拠

- parser と suite の既定値・相互排他: `strata_cli/cli.py:291-321`
- プロファイル名と JSON パスの識別、保存データ・run config 読み込み: `strata_control/profiles.py:25-55, 135-166, 382-388`
- `_source()` と有効な起動計画: `strata_cli/cli.py:545-547, 782-825`
- standard suite / serving suite の profile 利用、起動・再利用・lease: `strata_cli/cli.py:1183-1225, 1237-1311`; `strata_cli/bench_standard.py:658-695, 716-750`; `strata_cli/bench.py:173-203, 744-765, 852-888`; `strata_control/benchmarking.py:82-95`
- エラー出力と終了コード処理: `strata_control/profiles.py:30-35`; `strata_cli/cli.py:527-532, 2166-2188`

この文書は同一 checkout のソースを対象にしています。別 OS の配布バイナリや Release artifact での差異は照合していません。CLI の `--help` は実行していません。
