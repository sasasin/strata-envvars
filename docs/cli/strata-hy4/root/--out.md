# `strata-hy4 --out`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root、CUDA/HIP runner） |
| オプション | `--out` |
| 別名 | なし |
| 値 | 出力ディレクトリのパス文字列。parser に型・範囲検証はない |

## 役割

通常のオフライン実行で生成結果や診断用データを書き出すディレクトリを指定する。既定値は `.`（実行時のカレントディレクトリ）で、生成した token ID、top-5 結果、指定時の logits や中間 tensor dump などの保存先になる。`strata-hy4 --serve` のサーバー経路では `--out` は出力先に反映されない。

## 使い方

出力先ディレクトリをあらかじめ作成してから指定する。

```sh
mkdir -p ./hy4-results
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --gen 32 --out ./hy4-results
```

## 値と既定値

- `--out` の直後の引数をそのまま保存先文字列として受け取る。省略時は `.`。パスの存在確認、作成、正規化は通常実行の parser では行わない（`engine/src/hy4flash/run/hy4_main.hip.cpp:347`, `:377-384`, `:485`）。
- 複数回指定した場合は、引数を順に処理して同じ変数へ代入するため最後の値が使われる（同 `:375-384`, `:485`）。
- 値を省略すると `ERR --out needs a value` を stdout に出して終了コード 2 で終了する（同 `:377-382`）。値が空文字列の場合の拒否処理はない。出力パスは `out_dir + "/ファイル名"` の形で組み立てられるため、空文字列を指定すると `/ファイル名` が対象になり得る（同 `:1010-1016`, `:1097-1108`）。

## 実行時の動作

- 通常実行では `--out` の値を `Runner::dump_dir` にも渡す。`--dump` が有効なときは中間 tensor の `.npy` dump がこのディレクトリを基準に保存される（`engine/src/hy4flash/run/hy4_main.hip.cpp:692-695`; `engine/src/hy4flash/run/hy4_graph.hip.h:209-217`, `:1934-1942`）。
- prefill 後、`--dump` または `--save-logits` を指定すると `logits.npy` を保存する（`engine/src/hy4flash/run/hy4_main.hip.cpp:769-777`）。生成数が 1 以上なら `gen_ids.txt`、常に `top5.txt` が同じディレクトリに書かれ、`--margins` を併用すると `margins.txt` と `hashes.txt` も出力される（同 `:1000-1016`, `:1097-1108`）。
- `--dump-dfly-batch` と併用すると、バッチ出力先は `--dump-dfly-out` が空でない場合そちらが優先され、空なら `--out` が使われる。この経路では出力ディレクトリを作成してから `seq_0000.bin` 形式のファイルを書き出す（同 `:421-424`, `:707-708`; `:183-190`, `:309-324`）。
- `--serve` の場合は `ServeOpts` を組み立てて `hy4_serve_main` に進み、その際 `out_dir` は渡されないため、サーバー経路の出力先指定としては作用しない（同 `:544-611`）。また `--load-only` はモデル読み込み後、通常の出力処理より前に終了する（同 `:658-665`）。

## 適用条件と副作用

- 通常の生成・診断出力先を変更するオプションであり、パス指定自体によるネットワークや GPU の設定変更はない。
- 通常経路は指定ディレクトリを自動作成しない。`--dump` 時の `.npy` 保存関数は `fopen` 失敗時に戻るだけでエラーを伝えず（`engine/src/hy4flash/run/hy4_graph.hip.h:77-97`）、通常経路の `std::ofstream` 書き込みも成功状態を検査しない（`engine/src/hy4flash/run/hy4_main.hip.cpp:1010-1016`, `:1097-1108`）。したがって、ディレクトリがない・書き込み権限がない場合でも、これらの出力について明示的な失敗表示や非ゼロ終了が行われるとはソースから確認できない。
- 通常のファイル出力は既存の同名ファイルを置き換える書き込みモードで開かれる（`fopen(..., "wb")` は同 `hy4_graph.hip.h:85-96`; `std::ofstream` は同 `hy4_main.hip.cpp:1010-1016`, `:1097-1108`）。既存結果を残す場合は別ディレクトリを指定する。
- `--dump-dfly-batch` 経路ではディレクトリ作成または `seq_*.bin` のオープンに失敗すると stderr に `cannot write` を出し、終了コード 1 を返す（`engine/src/hy4flash/run/hy4_main.hip.cpp:183-190`, `:309-315`）。

## 出力とエラー

`--out` 自体に対する値の validation error は実装されていない。値不足の場合の stdout メッセージと終了コード 2 は「値と既定値」のとおり。出力ファイルを作成できない場合の扱いは経路ごとに異なり、通常出力・`.npy` dump ではエラーが無視される一方、`--dump-dfly-batch` は stderr に失敗パスを表示して 1 で終了する（上記「適用条件と副作用」参照）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:347,375-384,483-489` — 既定値、値取得、`--out` の parser 分岐。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-611,658-665,692-708` — serve 経路、load-only の早期終了、通常経路および batch 出力先の伝播。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:769-777,1000-1016,1097-1108` — logits、生成 ID、top-5、margin/hash の出力箇所。
- `engine/src/hy4flash/run/hy4_graph.hip.h:77-97,209-217,1934-1942` — `.npy` 書き込み失敗時の処理と runner dump の保存先。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:183-190,309-324` — batch 出力先のディレクトリ作成、ファイル書き込みと失敗処理。

## 調査範囲と制約

索引 `docs/cli/README.md` の `strata-hy4` の root scope と、`docs/cli/000_cli_tools.md` が示す CUDA/HIP parser `engine/src/hy4flash/run/hy4_main.hip.cpp` を対象とした。Metal と SYCL は別コマンド階層（`metal/`、`sycl/`）であり、この文書の対象外。実行可能バイナリの help は実行していない。出力ファイルの個別内容・失敗時の OS 依存動作は、ここに引用した Strata ソースの範囲を超えて断定しない。
