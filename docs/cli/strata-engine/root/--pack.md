# `--pack`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--pack` |
| 別名 | なし |
| 値 | パックのディレクトリを表す文字列（`DIR`）。parser に型・形式・範囲の検査はない |

## 役割

推論エンジンが重みパックと expert layout を読むディレクトリを指定する。`strata generate` はパック内の `native_experts.txt` を調べて expert の形式を決め、`index.txt` とそこに記された重みファイルを読み込む。`native_experts.txt` がないパックは標準形式として扱われる。`--serve` で会話キャッシュの SSD spill を有効にした場合は、パックの場所からデータディレクトリを推定する用途にも使われる。

## 使い方

```sh
# パックと事前トークン化した入力を指定して生成する
strata generate --pack /data/packs/model-a --tokens "1,2,3"
```

## 値と既定値

- 省略時は `pack/full`。相対パスの場合、ソースは与えられた文字列に `/native_experts.txt` や `/index.txt` を連結して開くため、実行時の作業ディレクトリを基準に解決される（`engine/src/program/generate.cpp:755`、`engine/src/kernels/cpu/expert_layout.cpp:505`、`engine/src/core/weights.cpp:95-97`）。
- `--pack` の値は次の argv 要素をそのまま文字列として代入する。空文字列や重複指定を parser 自身は拒否せず、複数指定時は後の値が残る。パックの存在・構造は後段の読み込み処理で確認される（`engine/src/program/generate.cpp:3837-3846`）。
- 値がない場合は `--pack needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:3839-3841`）。

## 実行時の動作

1. 起動時に `native_experts.txt` を読み、存在しなければ標準形式の expert layout を設定する。存在する場合は native expert layout として解析する。native パックでは、さらに `--native SHARD1`、`--spec T`（`T >= 2`）などが必要で、条件を満たさなければ終了コード 2 で拒否される（`engine/src/kernels/cpu/expert_layout.cpp:501-516`、`engine/src/program/generate.cpp:5355-5363,5753-5760`）。
2. `index.txt` の pool サイズを使って重み領域を確保し、`WeightTable` が index とそこに記された重みファイルを読み込む。ファイルが存在しない、index のヘッダーや行が不正、読み込みに失敗する場合はエラーを stderr に出して終了コード 1 となる（`engine/src/program/generate.cpp:5965-5969,6016-6029`、`engine/src/core/weights.cpp:93-122,176-223,308-313`）。
3. `--serve` と会話キャッシュ SSD spill の組み合わせでは、明示的な spill ディレクトリがなければ、`--pack` の親ディレクトリ名が `packs` の場合にその親をデータディレクトリとみなし、`conversation-spill` を作成する。条件を満たさない場合は SSD tier を有効にせず、その理由を stderr に出す（`engine/src/program/generate.cpp:13965-13987,14001-14012`）。

## 適用条件と副作用

- このオプションは `strata-engine` の `strata generate` parser のもの。Terminal CLI の同名オプションとは別スコープである。索引では `strata-engine` のトップレベル `root` に掲載されている（`docs/cli/README.md` の `strata-engine` 節、`engine/src/program/generate.cpp:1206-1212,3844-3846`）。
- `native_experts.txt` があるパックは、native expert 対応なしでビルドされたエンジンでは拒否される。layout のバージョンや行形式、量子化形式に問題がある場合も読み込みに失敗する（`engine/src/kernels/cpu/expert_layout.cpp:512-534,545-557`）。
- パックの重み読み込みは GPU 重み領域を確保し、重みデータを読み込む。`--pack` 自体が通常のパックファイルを書き換える処理は確認できない（`engine/src/program/generate.cpp:5970-6008,6016-6030`）。一方、前述の serve spill 条件では `conversation-spill` ディレクトリを作成し、SSD tier の session ファイルを扱う（`engine/src/program/generate.cpp:13965-14012`）。
- 位置引数相当の値の検証は parser では行わず、実ファイルの読み込み時に失敗する。`--tokens` も通常の `generate` では必要だが、これは `--pack` とは別の必須条件である（`engine/src/program/generate.cpp:4991-5002`）。

## 出力とエラー

- パックの `native_experts.txt` を解析できない場合、エラー文を stderr に出し、呼び出し元で終了コード 1 となる（`engine/src/program/generate.cpp:5358-5362`）。
- 重み index やそのデータファイルを開けない場合、`WeightTable` のエラー文を stderr に出して終了コード 1 となる。index に有効な pool ヘッダーがない場合や行の形式が不正な場合も同様に失敗する（`engine/src/core/weights.cpp:93-122,176-223,308-313`、`engine/src/program/generate.cpp:5965-5969,6016-6019`）。
- `--pack` に値が続かない場合は parser が終了コード 2 で終了する。未知のオプションも stderr に表示して usage を出し、コード 2 で終了する（`engine/src/program/generate.cpp:3839-3841,4263-4268`）。

## 根拠

- `engine/src/program/generate.cpp:754-755` — `Options::pack` の型と既定値。
- `engine/src/program/generate.cpp:1206-1212,3837-3846` — usage 表示と parser 登録。
- `engine/src/kernels/cpu/expert_layout.cpp:501-516` — パックの native expert layout 判定と native build 条件。
- `engine/src/program/generate.cpp:5355-5363,5753-5760` — layout 読み込みと native パックの適用条件。
- `engine/src/core/weights.cpp:93-122,176-223,308-313` および `engine/src/program/generate.cpp:5965-6030` — index の検査、重み読み込み、失敗経路。
- `engine/src/program/generate.cpp:13965-14012` — serve の conversation spill が `--pack` の位置を使う条件とディレクトリ作成。
