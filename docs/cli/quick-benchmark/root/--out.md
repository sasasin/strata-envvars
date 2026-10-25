# `quick-benchmark` の `--out`

- 調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`
- 調査日: 2026-10-25
- スコープ: `quick-benchmark`（`bench.sh` / `BENCH.bat` が委譲する `tools/strata_bench.py` の root parser）

## 役割

ベンチマーク結果フォルダを置く親ディレクトリを指定します。レポートのファイル名ではなく、日時・GPU・モデル名を含むフォルダの保存先です。

## 使い方

```sh
./bench.sh --out /path/to/benchmark-results
```

または、Strata リポジトリのルートから次のように実行できます。

```sh
python tools/strata_bench.py --out /path/to/benchmark-results
```

## 値と既定値

- 値は1個のパス文字列です。parser は `type`、選択肢、必須指定を設定していないため、パスの存在や書き込み可能性は parser 段階では検証されません。`tools/strata_bench.py:932-948`
- 未指定時は `<Strata checkout>/bench/results` が使われます。`tools/strata_bench.py:1017-1018`
- 指定値は `Path(a.out)` に変換されます。絶対パスはそのまま、相対パスはプロセスの現在作業ディレクトリ基準です。`./bench.sh` と `BENCH.bat` は先に Strata ルートへ移動するため、これらの wrapper 経由では相対値も Strata ルート基準になります。`bench.sh:6-10`, `BENCH.bat:8-16`
- 空文字列も parser では拒否されません。Python の `Path("")` は現在ディレクトリを表すため、実質的に現在ディレクトリが保存先親になります。`tools/strata_bench.py:943,1017`

## 実行時の動作

通常実行では、`--out` の値を親ディレクトリとして `write_results` に渡します。子ディレクトリ名は `<日付>-community-<GPU>-<モデル>` 形式です。同名の子がすでにあれば `-2`、`-3` のような連番を追加し、既存の結果フォルダは選択しません。その子フォルダに `results.json` と `README.md` を書き、サーバーをこの実行で起動した場合は `engine-log-excerpt.txt` も書きます。`tools/strata_bench.py:773-782`, `tools/strata_bench.py:910-918`, `tools/strata_bench.py:1017-1018`

`--compare DIR` を併用すると、新規レポートの保存後に既存結果との比較を表示します。`--compare-only NEW` は既存レポート同士の比較後に終了する分岐であり、`--out` を指定しても新規レポートを保存しません。`tools/strata_bench.py:951-955`, `tools/strata_bench.py:1023-1025`

## 適用条件と副作用

- `--out` は比較専用の早期終了を除く通常の測定経路で使われます。ベンチマークはサーバーの HTTP API を呼び出し、出力先に結果を作成します。出力データには機械・実行情報が含まれますが、保存前にホームパス、ユーザー名、ホスト名、IP アドレス、API key などを redactor で置換する処理があります。`tools/strata_bench.py:67-105`, `tools/strata_bench.py:913-918`
- 保存先の子ディレクトリは `d.mkdir()` で作成され、`parents` は既定の `False` です。そのため、`--out` で指定した親ディレクトリが存在しない場合、その親は再帰作成されず保存に失敗します。指定値が既存ファイルの場合や書き込み権限がない場合も、保存時に OS エラーとなる経路があります。`tools/strata_bench.py:910-918`
- 既存の結果フォルダを上書きしない意図で `unique_dir` が空き名を選びますが、空き名の確認と作成の間に別プロセスが作成する競合までは処理していません。`tools/strata_bench.py:777-782`, `tools/strata_bench.py:910-918`

## 出力とエラー

- 通常実行では保存した `README.md` のパスを標準出力に表示します。`--quiet` を併用すると、この通常ログは抑制されます。`tools/strata_bench.py:947-949`, `tools/strata_bench.py:1026-1033`
- 保存処理の `OSError` などを `--out` 専用の診断や終了コードへ変換する catch は、保存呼び出し周辺にありません。エラー表示の詳細・終了コードは Python 実行時の例外処理に委ねられます。`tools/strata_bench.py:1017-1018`, `tools/strata_bench.py:1034-1041`
- この option 自体に数値などの値検証や専用の終了コードはありません。

## 根拠

- parser 定義と既定値: `tools/strata_bench.py:932-948`
- 保存先の決定、比較専用経路、出力: `tools/strata_bench.py:951-955`, `tools/strata_bench.py:1017-1034`
- フォルダ名、既存名回避、ファイル作成: `tools/strata_bench.py:773-782`, `tools/strata_bench.py:910-918`
- ラッパーの委譲と作業ディレクトリ: `bench.sh:6-10`, `BENCH.bat:8-16`

この調査では同一 revision の CLI `--help` は実行していません。parser 定義と実際の参照・保存処理をソースで確認しました。相対パスの規則は wrapper の `cd` と Python の `Path` の使用から判断しています。
