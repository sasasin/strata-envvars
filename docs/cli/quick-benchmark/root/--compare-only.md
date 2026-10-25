# `--compare-only`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業ツリーは `## main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（委譲先: `python tools/strata_bench.py`） |
| オプション | `--compare-only` |
| 別名 | なし |
| 値 | 必須。新しい側の結果フォルダー、または `results.json` ファイルへのパス（parser の metavar: `NEW`） |

## 役割

保存済みの新旧2回分の quick benchmark 結果を比較して表示し、測定を開始せず終了します。`--compare` に旧結果を指定し、このオプションに新結果を指定します。通常経路で `--compare` だけを指定すると新しい測定を実行してから比較しますが、`--compare-only` はその測定を省略します（`tools/strata_bench.py:944-955, 1000-1025`）。

## 使い方

リポジトリのルートでの例:

```bash
./bench.sh --compare bench/results/old-run --compare-only bench/results/new-run
```

Windows では `BENCH.bat --compare bench\results\old-run --compare-only bench\results\new-run` とします。両 wrapper は引数をそのまま `tools/strata_bench.py` に渡します（`bench.sh:6-10`、`BENCH.bat:8-16`）。直接実行する例は次のとおりです。

```bash
python tools/strata_bench.py --compare OLD_FOLDER --compare-only NEW_FOLDER
```

この2結果を使う形式は `docs/COMMUNITY_BENCHMARKS.md:134-139` にも記載されています。

## 値と既定値

- `--compare-only` は `argparse` の値付き引数であり、値は1つ必要です。省略時は比較専用分岐に入りません（`tools/strata_bench.py:932-948, 951`）。
- 値は `Path` に渡されます。ディレクトリならその中の `results.json` を読み、ファイルなら指定パスを直接読みます。相対パスは実行時のカレントディレクトリ基準です（`tools/strata_bench.py:954, 894-898`）。
- `--compare` には旧結果のパスが必要です。`--compare-only` に値を指定しても `--compare` がなければ、`argparse` の `error()` が usage とエラーを stderr に出し、通常は終了コード 2 で終了します（`tools/strata_bench.py:944-948, 951-954`）。
- コードは `if a.compare_only:` と真偽値で分岐します。したがって、シェルで明示的に空文字 (`--compare-only ""`) を渡すと比較専用分岐に入りません。その場合、通常の測定経路へ進みます（`tools/strata_bench.py:951-957`）。

## 実行時の動作

比較専用分岐は引数解析の直後に評価され、通常経路のモデル設定ファイル読込、サーバー判定・起動、HTTP API 呼び出し、結果保存より前に処理を終えます。そのため、このモードではベンチマーク測定や Strata サーバーの起動・停止、`--out` への書き込みは行われません（`tools/strata_bench.py:948-957, 958-1000, 1000-1018, 1035-1037`）。

旧結果 (`--compare`) と新結果 (`--compare-only`) を読み込み、`results` の指標から中央値を取り出して並べます。指標ごとに old、new、変化率を表示し、GPU、engine version、model、quant、context の値に差があれば追加表示します（`tools/strata_bench.py:416-431, 879-898`）。変化率は旧中央値が真値かつ新中央値が存在する場合だけ計算されます（`tools/strata_bench.py:882-891`）。比較結果は通常の `print()` で stdout に出て、正常なら `main()` は 0 を返します。`--quiet` が指定されても、この直接出力は抑制されません（`tools/strata_bench.py:948-955`）。

## 適用条件と副作用

2つの入力がこのツールの保存形式に沿い、少なくとも比較処理が参照する `results` と `machine` のデータを含むことが必要です（`tools/strata_bench.py:879-898`）。コード上、同一マシン・同一モデルであることを必須とする検証はなく、違いは比較表下部に注記されます（`tools/strata_bench.py:888-891`）。

このオプション自体は入力ファイルを読み取って標準出力へ表示するだけで、結果ファイルを書き換える処理はありません（`tools/strata_bench.py:894-898, 951-955`）。ただし、`--compare` と `--compare-only` はどちらもパス引数であり、コードに特定ディレクトリ配下だけを許す制限はありません。

## 出力とエラー

- `--compare` 不足時は `argparse` の usage/error 経路になります（`tools/strata_bench.py:951-954`）。
- ファイル不存在、読み取り権限不足、不正な JSON、比較に必要なキーの不足などについて、この分岐固有の捕捉・整形処理はありません。`Path.read_text`、`json.loads` または比較関数内で例外となり、通常の Python 例外終了になります（`tools/strata_bench.py:879-898, 954`）。例外ごとの終了コードや文面はこのコードで固定されていません。
- 比較表は stdout に表示されます。`--quiet` による抑制対象ではありません（`tools/strata_bench.py:948-955`）。

## 根拠

- parser 定義と比較専用分岐: `tools/strata_bench.py:932-955`
- 結果ファイルの読み込み、指標の抽出、比較表: `tools/strata_bench.py:416-431, 879-898`
- 通常測定との分岐位置、副作用の境界: `tools/strata_bench.py:957-1000, 1000-1037`
- wrapper の引数委譲: `bench.sh:6-10`、`BENCH.bat:8-16`
- 利用例: `docs/COMMUNITY_BENCHMARKS.md:134-139`
