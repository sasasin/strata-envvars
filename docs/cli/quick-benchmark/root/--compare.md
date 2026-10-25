# `--compare`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（`tools/strata_bench.py` に委譲） |
| オプション | `--compare` |
| 別名 | なし |
| 値 | 比較する以前の結果フォルダー、または `results.json` のパス（`DIR`） |

## 役割

通常の quick benchmark を実行して現在の結果を保存した後、指定した以前の結果と主要指標を表で並べて表示します。これはローカルの quick speed check です。利用者間で比較する標準ベンチマークは `strata bench run` と案内されています。

## 使い方

Strata checkout のルートで実行します。

```sh
./bench.sh --compare /path/to/older-results
```

Windows では同じ引数を `BENCH.bat --compare C:\path\to\older-results` のように渡します。POSIX wrapper は引数を Python スクリプトへそのまま渡し、Windows wrapper も `tools\strata_bench.py` を起動します（`bench.sh:6-10`、`BENCH.bat:8-17`）。

## 値と既定値

- `argparse` の `--compare` は `metavar="DIR"` の文字列引数です。オプションを省略した場合の値は `None` で、比較表は表示されません。別名、型変換、パス存在確認、JSON 検証を行う parser 設定はありません（`tools/strata_bench.py:932-948`）。
- 指定値がディレクトリーなら、その直下の `results.json` を読みます。ディレクトリーでなければ指定値そのものを UTF-8 の JSON ファイルとして読みます（`tools/strata_bench.py:894-898`）。
- 同じ `--compare` を複数回指定した場合、`argparse` の通常の `store` 動作により最後の値が使われます（`tools/strata_bench.py:944`）。

## 実行時の動作

`--compare` 単独では計測を省略しません。通常どおりモデル設定または稼働中 server を用意し、suite を実行し、新しい結果フォルダーへ `results.json` と `README.md`（server を起動した場合は engine log excerpt も）を書いた後で、旧結果を読み込みます。その後、chat、prompt、agent、指定時の clients 指標について旧・新の中央値と変化率を標準出力へ表示し、GPU、engine version、model、quant、context の差があれば併記します（`tools/strata_bench.py:1000-1025`、`tools/strata_bench.py:879-898`、`tools/strata_bench.py:910-918`）。

`--compare-only NEW` も同時に指定した場合は別経路です。`--compare` が旧結果、`--compare-only` の値が新結果として使われ、2つを比較して終了します。この経路は model/server の準備や新しい計測・レポート作成を行いません（`tools/strata_bench.py:945`、`tools/strata_bench.py:951-955`）。

## 適用条件と副作用

- 通常実行では `--compare` の処理に到達する前に quick benchmark の全計測と結果保存が行われます。したがって、このオプションは読み取り専用の比較だけを行う指定ではありません。レポートの既定保存先は `bench/results`、`--out` で変更できます（`tools/strata_bench.py:1000-1025`、`tools/strata_bench.py:1017-1018`）。
- 計測のためにこのスクリプト自身が server を起動した場合は、通常終了時および比較時の例外時に `finally` から停止処理を行います。既存 server を利用した場合は `started` が偽のままで停止処理を呼びません（`tools/strata_bench.py:981-995`、`tools/strata_bench.py:1035-1037`）。
- 比較表は結果 JSON の `results` と `machine` を参照します。値の schema や実験条件が同一かを検証して揃える処理は確認できません。異なる GPU、engine version、model、quant、context は差分として表示されますが、その他条件の同等性は保証されません（`tools/strata_bench.py:879-891`）。

## 出力とエラー

- 比較結果は標準出力に表示します。通常実行では比較結果の前に新規レポートのパス等も出力されます（quiet 時を除く）。
- `--compare` に値を付けなければ `argparse` が構文エラーを出します。通常経路で比較先が存在しない、JSON が不正、または必要な `results` / `machine` キーがない場合は、ファイル読み込み・JSON decode・キー参照で例外になります。比較専用のエラー整形や終了コード変換はこの経路に見当たりません（`tools/strata_bench.py:944`、`tools/strata_bench.py:894-898`、`tools/strata_bench.py:879-890`）。通常経路の比較エラーより前に書かれた新規結果は残ります。
- 通常実行では比較前のモデル設定不在や server 不在など、計測開始前に終了する経路もあります（`tools/strata_bench.py:957-973`、`tools/strata_bench.py:982-999`）。

## 根拠

- `tools/strata_bench.py:932-948` — `--compare` の parser 定義と値の扱い。
- `tools/strata_bench.py:894-898,879-891` — 結果ファイル読み込み、表示する指標と差分。
- `tools/strata_bench.py:951-955,1000-1025` — compare-only と通常計測後の比較分岐。
- `tools/strata_bench.py:910-918,1035-1037` — 結果ファイル作成と起動 server の終了処理。
- `bench.sh:6-10`、`BENCH.bat:8-17` — POSIX / Windows wrapper の引数委譲。
- 索引 [`docs/cli/README.md`](../../README.md) は `quick-benchmark` の root scope に `--compare` を掲載しています。標準ベンチマーク `strata bench run` とは別の CLI です。
