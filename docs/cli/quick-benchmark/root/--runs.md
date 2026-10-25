# `--runs`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（実体: `python tools/strata_bench.py`） |
| オプション | `--runs` |
| 別名 | なし |
| 値 | 整数。parser で `int` に変換。parser 自体に範囲制限なし |

## 役割

quick benchmark の各測定を何回繰り返すか指定します。回数はチャット、prompt、agent、`--clients` による並列測定に使われ、結果の中央値・範囲を計算する標本数に影響します。標準比較用ベンチマーク `strata bench run` ではなく、`bench.sh` / `BENCH.bat` が起動するローカル測定用のオプションです。

## 使い方

```sh
./bench.sh --runs 5
```

Windows では `BENCH.bat --runs 5` を使います。両 wrapper は引数を `tools/strata_bench.py` に渡します。Python を直接実行する場合は `python tools/strata_bench.py --runs 5` です。

## 値と既定値

- 省略時は `3` 回です。
- `argparse` の `type=int` で整数へ変換します。整数に変換できない値は argparse のエラーになります。parser に正数の下限や上限は定義されていません。
- suite を作るとき `max(1, a.runs)` が渡されるため、0 と負数は拒否されず、実行回数 1 に補正されます。整数値の上限チェックはありません。
- `--compare-only` を指定した場合、比較表示をして benchmark suite を起動せずに終了します。この場合 `--runs` は parser で整数変換されますが、実行回数には使われません。

## 実行時の動作

- suite の `runs` は短いチャットの各質問、4K prompt、（context 条件を満たす場合の）16K prompt、agent session の反復回数になります。`--clients N` を有効にした場合も N 件の同時要求を送る round 数になります。`--long` を有効にした場合は32K promptも同じ回数実行します。context 不足で prompt や agent が skip される場合、その項目は実行されません。
- chat は3つの質問それぞれを各 run で送信します。prompt は各 run で新しい prompt を送り、agent は各 run で複数 turn の session を行います。`--runs` は warm-up と calibration の回数を変えません。
- 結果の `params.runs` には補正後の回数が記録されます。一方、結果 JSON の `params.command` は指定された生の値を `--runs` として記録します（値が既定値3以外の場合）。そのため `--runs 0` では実測回数・`params.runs` は1ですが、記録コマンドには `--runs 0` が残ります。
- 通常の suite 完了後、結果は `--out` の指定先、または既定の `bench/results` 以下に新しい結果 directory として書かれます。`results.json` と README に回数と測定結果が入ります。

## 適用条件と副作用

この値は `--compare-only` 以外の通常測定経路で適用されます。回数を大きくすると各測定の HTTP 要求と実行時間が増えます。ベンチマークがサーバーを起動した場合は測定終了後にそのプロセスを停止します。すでに動作中の Strata サーバーを使う場合は、追加要求による負荷がそのサーバーにかかります。

## 出力とエラー

- 非整数値は argparse が usage/error を表示して拒否します（通常の argparse 終了コードは2）。負数や0は引数エラーにはならず、suite 内で1回に補正されます。
- 個別要求の失敗は結果の `failures` に記録されます。suite の結果が全く得られず失敗がある場合、main は終了コード1を返します。通常の起動前エラー（モデル設定なし、指定 URL の Strata server 不在、port の競合）は stderr に診断を出して終了コード2、起動後の ready timeout は stderr にログ末尾を出して終了コード1です。これらの経路は `--runs` の値による専用エラーではありません。

## 根拠

- `tools/strata_bench.py:933-948` — parser 定義。`--runs` は `type=int`、既定値3。
- `tools/strata_bench.py:264-305,342-375,403-413` — 回数が chat、prompt、agent、clients の反復に使われる箇所、suite の項目と条件。
- `tools/strata_bench.py:1000-1018` — `max(1, a.runs)` による補正、結果への実回数・コマンド記録、出力先と保存。
- `tools/strata_bench.py:951-955` — `--compare-only` の早期終了。
- `tools/strata_bench.py:969-999,1021-1037` — 起動前・ready timeout の失敗経路、request failure に応じた終了コード、起動した server の停止。
- `bench.sh:6-13`, `BENCH.bat:6-19` — wrapper が引数を Python CLI に委譲する処理。
- `docs/cli/README.md:1522-1544` — quick-benchmark の索引、コマンド階層、`--runs` の予定リンク。

調査は指定 commit の parser と関連ソースの読解に限定しました。CLI help の実行、build、GPU 実行、性能測定、テストは行っていません。
