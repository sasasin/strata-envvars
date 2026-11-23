# `strata-hy4-sycl --out`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL） |
| オプション | `--out` |
| 別名 | なし |
| 値 | 出力先ディレクトリの文字列。省略時は `.` |

## 役割

通常の推論実行で `top5.txt`、生成時の `gen_ids.txt` と（条件により）`margins.txt`、および `--dump` が有効なときの NPY データを書き出す先を指定します。値は出力ファイル名の前に連結されます。

## 使い方

```sh
# あらかじめ用意した空の出力ディレクトリへ出力する
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata --tokens ids.txt --out ./run-output

# テンソルの NPY ダンプも同じディレクトリへ出す
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata --tokens ids.txt --dump --out ./run-output
```

例の `./run-output` は事前に存在する空ディレクトリに置き換えてください。出力先ディレクトリはプログラムが作成しません。

## 値と既定値

- `--out` の直後の引数をそのまま `out_dir` に格納します。専用の形式・範囲検査やパス正規化はありません（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,155`）。
- 未指定時は `out_dir = "."` です（`engine/src/hy4flash/sycl/sy_main.cpp:93`）。
- 複数回指定した場合、引数を順に走査して都度代入するため最後の値が残ります（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,155`）。
- 値を省略すると `nxt()` が標準出力に `ERR --out needs a value` を出し、終了コード `2` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。

## 実行時の動作

通常実行では値を `Runner::dump_dir` に渡します（`engine/src/hy4flash/sycl/sy_main.cpp:283-288`）。推論完了時に `top5.txt` を書き、生成処理に入った場合は `gen_ids.txt` を書きます。通常の生成経路で speculative decode の margins が存在すると `margins.txt` も書きます（`engine/src/hy4flash/sycl/sy_main.cpp:596-605`）。speculative decode 経路も `gen_ids.txt` を書きます（同 `:379-408`）。

`--dump` と併用すると、最終 logits の `logits.npy` に加え、`Runner::maybe_dump` が保存する中間テンソルの NPY ファイルもこのディレクトリに書きます（`engine/src/hy4flash/sycl/sy_main.cpp:363`; `engine/src/hy4flash/sycl/sy_graph.h:797-807`）。各層の追加デバッグ出力は `--dump` と `--dbg-layers` の両方が有効な場合に保存されます（`engine/src/hy4flash/sycl/sy_graph.h:1215-1227`）。

## 適用条件と副作用

- `--out` は `--serve` の serve 経路では出力先に反映されません。serve 分岐は `ServeOpts` を組み立てて `hy4s_serve_main` を呼びますが、その構造体へ `out_dir` を渡していません（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`）。
- 出力ファイルは `out_dir + "/" + ファイル名` の形で開かれます。ディレクトリの作成・検証は行われません（`engine/src/hy4flash/sycl/sy_main.cpp:363,407,596-605`; `engine/src/hy4flash/sycl/sy_graph.h:52-71,806-807`）。
- `gen_ids.txt`、`margins.txt`、`top5.txt` は `std::ofstream` の既定モードで開かれ、同名ファイルがあれば内容を置き換えます。NPY ファイルも `fopen(..., "wb")` で開くため既存ファイルを置き換えます（`engine/src/hy4flash/sycl/sy_main.cpp:407-408,596-605`; `engine/src/hy4flash/sycl/sy_graph.h:60-71`）。
- 書き込み先を開けない場合、NPY 保存関数は何も出力せず戻ります。`ofstream` の open/write 状態も確認されていません。このため、これらの書き込み失敗を報告するエラー経路はソース上で確認できません（`engine/src/hy4flash/sycl/sy_graph.h:60-71`; `engine/src/hy4flash/sycl/sy_main.cpp:407-408,596-605`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93,105-115,155` — 既定値、引数取得、オプション登録と値不足時の処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248` — serve 分岐と、`out_dir` を serve 用オプションに渡さない処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:283-288,363,379-408,596-605` — 通常実行への引き渡しと、推論・生成出力の保存箇所。
- `engine/src/hy4flash/sycl/sy_graph.h:52-71,797-807,1215-1227` — NPY 書き込み、`--dump` とデバッグダンプの適用条件。
