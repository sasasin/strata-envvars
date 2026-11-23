# `strata-hy4-metal --kernels`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--kernels` |
| 別名 | なし |
| 値 | 次の引数を Metal カーネルのメインソース `hy4.metal` のパスとして受け取る。 |

## 役割

Metal runner が実行時にコンパイルする Hy4 のカーネルソースの場所を指定する。値はディレクトリではなく、`hy4.metal` 自体のパスである。同じディレクトリにある関連 `.metal` ファイルも読み込まれるため、別のソース一式を試す場合や、実行ファイル・作業ディレクトリとは異なる場所にソースを置く場合に使う。オフライン実行と `--serve` のどちらにも適用される。

## 使い方

```sh
# カーネルソース一式の hy4.metal を指定してオフライン実行
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --kernels ./kernels/hy4.metal

# 同じカーネルソースをサーバーモードで使用
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --serve --kernels ./kernels/hy4.metal
```

## 値と既定値

- 値は `--kernels` の直後の引数を文字列として受け取る。拡張子や存在確認を parser で検証する処理はない。複数回指定した場合は `kernels = nxt()` により最後の値が残る（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1512`）。
- 明示値が空文字列なら `kernels.empty()` と判定され、指定値としては使われず既定の探索経路へ進む（同 `:1661-1670`, `:1708-1712`）。
- `--kernels` を省略した場合、まず環境変数 `STRATA_HY4_KERNELS` を参照し、未設定ならビルド時にカーネルが埋め込まれている場合は一時ディレクトリへ展開した `hy4.metal` を使う。これらがない場合の既定パスは実行モードで異なる（同 `:1661-1670`, `:1708-1712`）。

## 実行時の動作

- 明示した値が空でない場合は、環境変数や埋め込みソースより優先される。値が存在するパスなら `realpath` で絶対パス化を試み、成功しなければ入力文字列のまま後続処理へ渡す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1672-1674`, `:1717-1720`）。
- `Runner::init` は指定ファイルを先頭に、同じディレクトリの `hy4_split.metal`、`hy4_hcp.metal`、`hy4_flash.metal`、`hy4_kvb.metal`、`hy4_dfly2.metal`、`hy4_lin2.metal`、`hy4_moe2.metal`、`hy4_lin3.metal`、`hy4_dfly2b.metal` を基本ソースとしてコンパイルする。`--kernels` のファイル名自体は `hy4.metal` でなくても parser は拒否しないが、ソース群の構成を満たす必要がある（`engine/src/hy4flash/metal/hy4_metal_main.cpp:522-528`）。
- `--serve` では、未指定時に `STRATA_HY4_KERNELS`、埋め込みソースの順で使い、どちらもなければ実行ファイルと同じディレクトリの `hy4.metal` を探し、読めなければカレントディレクトリの `hy4.metal` に切り替える（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1661-1674`）。
- オフライン実行では、未指定時に `STRATA_HY4_KERNELS`、埋め込みソースの順で使い、どちらもなければカレントディレクトリの `hy4.metal` を使う。実行ファイルの隣を探す分岐はない（同 `:1708-1720`）。
- ビルドにソースが埋め込まれている場合、未指定時は `<TMPDIR>/strata-hy4-kernels-<hash>/`（`TMPDIR` 未設定・空なら `/tmp`）にソース群を書き出し、その `hy4.metal` を選ぶ。既に同名ファイルが期待サイズで存在すれば再利用し、書き込み失敗時はエラーを stderr に出して展開失敗を返す（同 `:1398-1432`）。
- Metal runtime はファイル群を読み込んでソースを結合し、実行時コンパイルする。画像入力を伴う場合も同じディレクトリを画像用カーネル `hy4_vision.metal` の探索元として渡す（`engine/metal/src/mtl_rt.mm:183-193`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1776-1779`）。

## 適用条件と副作用

- Apple Silicon 向け `strata-hy4-metal` の Metal runner に適用される。索引上のスコープは `strata-hy4-metal`（Metal; `engine/src/hy4flash/metal/hy4_metal_main.cpp`）である（`docs/cli/README.md:1358-1387`）。
- パスの相対解決は `realpath` が成功するかに依存する。コンパイラ側では絶対パスの各ファイルをそのまま読み、相対パスは `Context::kernel_dir` を基準に解決する。これは `STRATA_METAL_KERNELS` 等で選ばれるディレクトリである（`engine/metal/src/mtl_rt.mm:148-150, 190-193`）。したがって相対値の解決元は、`--kernels` のパスが `realpath` で絶対化できたかによって変わり得る。
- `STRATA_HY4_KERNELS` は CLI 値が空のときの fallback であり、両モードとも非空の明示値が優先される。埋め込みソースが選ばれる構成では `/tmp` または `TMPDIR` 配下にファイルを作成する副作用がある（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1402-1429, 1661-1674, 1708-1720`）。
- `--serve` で画像を扱う場合、指定した `hy4.metal` と同じディレクトリに画像用のソースも必要になる。画像側は `hy4_vision.metal` を含むファイル群をコンパイルする（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1776-1779`, `engine/src/hy4flash/metal/hy4_metal_vision.h:90-105`）。

## 出力とエラー

- 指定パスや関連ファイルを読み込めない場合、Metal runtime の `read_file` が `mtl: cannot read <path>` を stderr に出して終了コード 2 でプロセスを終了する（`engine/metal/src/mtl_rt.mm:26-34`）。
- Metal ソースのコンパイルに失敗した場合、基本ソース群のコンパイル経路ではデバイス・macOS・ファイル名とコンパイラ診断を stderr に出して終了コード 3 で終了する（`engine/metal/src/mtl_rt.mm:170-179`）。MPP 用の追加ソース群のコンパイル失敗は `compile_try` が失敗を返し、runner は MPP なしの基本ソース群で再試行する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:533-555`, `engine/metal/src/mtl_rt.mm:182-226`）。
- 引数の欠落・空値以外の妥当性検証は parser に見当たらない。特に値を伴わない `--kernels` の挙動は parser が次の `argv` を無条件に読む実装であり、正常なエラー表示や終了コードはソースから確認できない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1512`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1512` — 値の格納と parser。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1661-1674, 1708-1720` — serve / offline それぞれの優先順、fallback、絶対パス化と Runner への引き渡し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:522-556` — 基本ソース群と MPP ソースの読み込み・コンパイル経路。
- `engine/metal/src/mtl_rt.mm:26-34, 170-226` — ファイル読み込み失敗と Metal コンパイルの処理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1398-1432` — 埋め込みソースの展開先・再利用・書き込み失敗。
- `docs/cli/README.md:1358-1387` — `strata-hy4-metal` のコマンド階層と `--kernels` の索引リンク。

調査制約: 同一 revision の CLI `--help` は実行せず、parser とソース上の利用箇所を確認した。GPU・Metal 実行時における OS やコンパイラ固有の診断内容・復旧可否は確認していない。
