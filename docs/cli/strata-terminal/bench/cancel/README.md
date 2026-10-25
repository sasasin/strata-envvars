# `strata bench cancel`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench cancel` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/benchmarking.py`、`strata_cli/bench.py` |

## 役割

保存済み profile を使って実行中の serving benchmark を中断する要求を出します。指定した run directory が、その profile に紐づく現在の benchmark lease と一致し、進捗状態が `running` の場合だけ受け付けます。中断要求は対象 benchmark が所有するクライアント側 stream に作用します。Strata server や推論 engine を停止するコマンドではありません。

このページはコマンド全体の概要です。オプションの詳細は [`strata bench cancel` のオプション一覧](../../../README.md)を参照してください。

## 基本的な使い方

```sh
# 実行中 benchmark の出力ディレクトリを指定
strata bench cancel --profile four-gpu --path /absolute/path/to/bench-run

# results.json を指定する形も使える
strata bench cancel --profile four-gpu --path /absolute/path/to/bench-run/results.json --output json
```

`--path` には実行時に `strata bench run --profile NAME --suite SUITE --out DIR` へ渡した出力ディレクトリを指定します。`results.json` または `progress.json` を指定した場合は、その親ディレクトリが対象になります。パスは絶対パスでなければなりません。相対パスは usage error として終了コード 2 で拒否されます。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 人間向け表示 | `strata bench cancel --profile four-gpu --path /absolute/path/to/bench-run` | 要求を受け付けると「Cancellation requested」と表示し、最終結果は保存レポートで確認するよう案内します。 |
| JSON 表示 | `strata bench cancel --profile four-gpu --path /absolute/path/to/bench-run --output json` | `ok`、レポート path、`cancel_requested` または `cancelled` state を含む JSON を stdout に出します。 |

## 実行時の主な動作

- `--profile` は必須です。CLI は保存済み profile を読み込み、未保存、無効、または読み込み不能なら処理を失敗させます。
- `--path` も必須で、profile ごとの lease が記録した絶対パスと対象 run のパスを照合します。lease がない、別 run が active、または run がすでに終了している場合は対象外です。
- 対象の progress record が `running` のとき、出力ディレクトリに owner-only の `cancel.request` ファイルを作成します。作成後の要求は benchmark の監視スレッドが最大約 0.1 秒間隔で検知し、benchmark が追跡している socket を shutdown します。
- benchmark は実行ループを抜け、実行後の telemetry を取得できる範囲で取得して `results.json` と最終 `progress.json` を保存します。レポートは `cancelled: true`、進捗 state は `cancelled`、成功フラグは `false` になります。CLI の受付成功は最終完了を意味しないため、保存されたレポートを確認してください。
- 人間向け出力では受付文を stdout に表示します。`--output json` では成功 payload を JSON で stdout に出します。エラーは人間向けなら `strata: ...` として stderr、JSON モードなら `{ok:false,error:...}` として stdout に出ます。

## 適用条件と注意点

- この cancel 経路の lease は、`strata bench run` のうち保存済み profile と新規出力先を使う serving suite が取得します。`standard-v1` は別の実行経路であり、この cancel 機構を利用しません。また、`--url` だけで実行した remote benchmark は profile lease を持たないため対象になりません。
- POSIX では出力ディレクトリと progress file が owner-only であることも確認されます。進捗ファイルとレポートの整合性が確認できない場合や、cancel marker が不正な場合は受け付けません。
- 実行中 benchmark がすでに送ったリクエストは取り消しまでに処理が進んでいる可能性があります。コマンドはサーバー側の共有 workload や他のクライアント接続を停止しません。
- 調査は記載 revision のソースを対象としました。安全に実行できる同一 revision の CLI `--help`、Release archive、Windows 上の実行挙動はこの調査では確認していません。

## 関連文書

- [`strata bench` の索引と全オプション](../../../README.md)
- [`strata bench run`](../run/README.md)
- [`strata bench report`](../report/README.md)
- [`strata bench compare`](../compare/README.md)

## 根拠

- Strata `strata_cli/cli.py:291-300,335-338` — `bench` / `cancel` の parser 登録、必須引数、`--output` の値と既定値。
- Strata `strata_cli/cli.py:1175-1182` — 絶対パス検査、profile 読み込み、cancel 要求、成功表示。
- Strata `strata_cli/cli.py:1186-1225` — serving suite と `standard-v1` の経路分岐、および保存済み profile の benchmark lease。
- Strata `strata_control/benchmarking.py:82-100,105-135` — profile ごとの lease と、対象 path の active 状態照合。
- Strata `strata_control/benchmarking.py:138-180` — run directory の検査、progress state の確認、cancel marker の作成と検証。
- Strata `strata_cli/bench.py:57-82,812-888` — marker の監視、所有 stream の shutdown、キャンセル時レポートと progress の保存。
- Strata `strata_cli/bench.py:695-740` — progress file の形式・状態・最終 report との整合性検証。
- Strata `strata_cli/cli.py:527-542,2166-2188` — 人間向け/JSON の成功・失敗出力と例外終了コード。
- Strata `strata_control/profiles.py:150-166` — 保存済み profile の読み込みと検証。
- `docs/cli/README.md:643-650` — `bench/cancel` の概要リンクとオプション scope。
