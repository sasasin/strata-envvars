# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--json` |
| 別名 | `--output json` |
| 値 | 値を取らないフラグ。省略時は `false` |

## 役割

ベンチマーク実行後の標準出力を、人向けの表示から JSON 形式の機械可読な応答に切り替えます。ベンチマーク条件や計測内容を変えるフラグではありません。`bench run` に共通の one-shot オプションとして登録されています（`strata_cli/cli.py:508-515`）。

## 使い方

```sh
strata bench run --profile my-profile --json
```

URL を指定して serving suite を実行する場合:

```sh
strata bench run --url https://example.invalid --suite serving-smoke --out ./bench-results/run-01 --json
```

`--profile` と `--url` は排他的で、どちらか一方が必要です。serving suite（`standard-v1` 以外）は `--out` も必要です（`strata_cli/cli.py:293-311`, `1186-1196`）。

## 値と既定値

`--json` は `argparse` の `store_true` フラグで、引数値は不要です。明示しなければ `false` です。`--output` は `human` または `json` を受け取り、省略時は `human` です（`strata_cli/cli.py:314`, `508-515`）。

引数解析後、`--json` が指定されていれば `a.output` を `json` に設定します。そのため `--json` は `--output json` の別名として働き、両方指定した場合も JSON が選ばれます。`--json` を複数回書いても真偽値のままです（`strata_cli/cli.py:2223-2237`）。

## 実行時の動作

出力形式の切り替え後も通常どおりベンチマークを実行します。standard suite は `--profile` が指定され、対象サーバーが起動していない場合、`--no-start` がなければエンジンを起動し、終了時に停止を試みます。レポートを新しい出力ディレクトリに書き込みます（`strata_cli/cli.py:1237-1240`, `1289-1311`; `strata_cli/bench_standard.py:766-785`, `834-840`, `899-960`）。

成功時の JSON 応答は `schema_version: 1` と `ok` を含みます。standard suite は `path`、`status`、`engine_stop_error`、`quality`、`summaries` を返し、serving suite は `path` と `summary` を返します。`ok` が false の場合も応答は JSON ですが、コマンドは終了コード `6` を返します（`strata_cli/cli.py:1226-1234`, `1312-1328`）。

実行中のログ出力は標準エラーへ送られ、機械可読な最終応答は標準出力に出ます（`strata_cli/cli.py:1221-1230`, `1289-1303`, `1321-1328`）。`--json` は結果ディレクトリ内の `results.json` 等の生成形式を選ぶものではなく、CLI の標準出力形式を選びます。計測・結果ファイルの作成自体はベンチマーク実行の副作用です。

## 適用条件と副作用

- `strata bench run` のスコープです。値の validation はありません。JSON にできない数値が応答に含まれる場合、成功出力の `json.dumps(..., allow_nan=False)` はシリアライズに失敗し得ます（`strata_cli/cli.py:535-542`, `1226-1230`, `1321-1325`）。
- standard suite は出力先が既に存在すると拒否し、既定では `./bench/results`（存在する場合）または `./bench-results` の下に新しいフォルダーを作ります。serving suite も出力先が既存なら拒否し、`--out` が必須です（`strata_cli/cli.py:1188-1196`, `1279-1282`; `strata_cli/bench_standard.py:777-780`, `835-840`; `strata_cli/bench.py:744-756`）。
- `--json` は `--quiet` と併用しても JSON を維持します。parser 後処理で `output=json` となるため、quiet 時の人向け出力捕捉経路を通りません（`strata_cli/cli.py:2232-2244`）。
- standard suite では、計測レポートが完全でない場合でもレポートを保存したうえで `ok: false` と終了コード `6` になることがあります。開始したエンジンを停止できなかった場合も失敗扱いとなり、`ENGINE-NOT-STOPPED.txt` を書き込もうとします（`strata_cli/cli.py:1312-1328`）。

## 出力とエラー

捕捉された `ValueError`（`ProfileError` を含む）、`OSError`、`ClientError`、割り込みは、`--json` が有効なら `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式を標準出力へ出します。エラーコードは例外に付与された値、または各処理が返す値です。`BrokenPipeError` は終了コード `0` で処理されます（`strata_cli/cli.py:527-532`, `2166-2193`; `strata_control/profiles.py:30`）。

parser 自体が拒否する未知オプションや必須引数の不足は、引数解析エラーとなり、上記の JSON エラー応答を経由しません（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:291-315`, `508-515`
- `--json` から `--output json` への変換: `strata_cli/cli.py:2223-2237`
- 成功応答・計測処理の分岐: `strata_cli/cli.py:1129-1234`, `1237-1328`
- standard suite の成果物作成: `strata_cli/bench_standard.py:766-840`, `899-960`
- serving suite の前提・出力先・成果物: `strata_cli/bench.py:744-804`, `843-888`
- 共通エラー応答と例外処理: `strata_cli/cli.py:527-542`, `2166-2193`
