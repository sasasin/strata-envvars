# `--check`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-gguf` |
| コマンド | `strata-gguf`（サブコマンドなし） |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らない指定。GGUF ファイルのパスを先に指定する |

## 役割

GGUF ファイルの基本情報に加えて、テンソル型から算出したバイト数とテンソル間の配置間隔の整合性、および Strata エンジン向けのアーキテクチャ適合性を診断表示します。`strata-gguf` は CMake target で、通常の Terminal CLI のサブコマンドではありません（`CMakeLists.txt:253-262`）。

## 使い方

```sh
strata-gguf ./model.gguf --check
```

ファイルパスは必須の第1引数です。ソース中の usage 表示は `gguf_reader <file.gguf> [--check]` です（`src/artifact/gguf_reader.cpp:7-12`）。

## 値と既定値

`--check` 自体は値を取りません。第2引数が `--check` と完全一致した場合に検査を有効にし、省略時は基本情報のみを表示します。第2引数だけを比較し、それ以降の引数は検査条件に使いません。したがって、`strata-gguf --check ./model.gguf` は `--check` として解釈されず、`./model.gguf` もファイル引数にはなりません。また、別の第2引数を置いた後に `--check` を付けても検査されません（`src/artifact/gguf_reader.cpp:8-14`）。

独立した未知オプションの検証や重複指定の処理はありません。ファイル引数がない場合は usage を表示して終了コード 2 です（同 `:8-10`）。

## 実行時の動作

まず `GgufFile` がファイルを読み取り専用で開き、GGUF ヘッダーとメタデータ、テンソル情報を読み取ります。Windows では読み取り専用マッピング、その他では `O_RDONLY` と `PROT_READ` のマッピングを使います（`include/strata/artifact/gguf_reader.hpp:414-446`）。成功すると、ファイル名、GGUF version、テンソル数、metadata 数、データ開始位置、ファイルサイズを標準出力へ表示します（`src/artifact/gguf_reader.cpp:14-18`）。

`--check` 指定時はさらに次を表示します（同 `:20-58`）。

- `blk.` で始まる名前のテンソル数と、それ以外の数。
- `Q2_0`、`BF16`、`F32` のテンソル数。
- 対応するブロック形状が分かるテンソルについて、形状から算出したバイト数が次テンソルまでの offset 間隔（最後のテンソルではデータ末尾まで）に収まるかを確認した結果。要素数がブロックの要素数で割り切れない場合も不正数に加算します。ブロック形状が未知の型はこの確認を飛ばし、未知型数として数えます（同 `:29-56`; `include/strata/artifact/gguf_reader.hpp:132-185`）。
- `check_architecture` によるアーキテクチャ・メタデータの適合結果。現行コードでは Qwen3.6 MoE 用の必須メタデータ確認、または Qwen4Exp の形状とコンパイル済みカーネル形状との照合などを行います（`include/strata/artifact/gguf_reader.hpp:624-646`, `:783-839`）。

## 適用条件と副作用

入力ファイルはこのプログラムによって書き換えられません。検査は読み取り専用マッピング上のヘッダー・テンソル情報から実行されます（`include/strata/artifact/gguf_reader.hpp:414-446`）。`--check` はテンソル payload 全体のチェックサム検証を行うものではなく、ここで確認できるのは表示された配置境界とアーキテクチャ guard の処理です。

## 出力とエラー

出力は `printf` による標準出力です。ファイルを開けない、GGUF magic が違う、version が v3 ではない、ヘッダーが途中で終わるなど `GgufFile` の読み取りで例外が起きると、`ERROR: <例外メッセージ>` を出して終了コード 1 になります（`src/artifact/gguf_reader.cpp:62-65`; `include/strata/artifact/gguf_reader.hpp:279-280`, `:414-465`）。

`--check` では配置不正数 `bad` が 1 以上なら終了コード 1、そうでなければ 0 です（`src/artifact/gguf_reader.cpp:56-61`）。アーキテクチャ guard の結果は `FAIL` と表示されても終了コードを変えません。また、未知型数も表示されますが、それ自体では失敗扱いになりません（同 `:56-59`）。

## 根拠

- CLI の引数位置、基本出力、検査分岐、終了コード、例外表示: `src/artifact/gguf_reader.cpp:7-65`
- `strata-gguf` の生成 target: `CMakeLists.txt:253-262`
- ファイルを読み取り専用で開く処理と GGUF v3 の読み取り: `include/strata/artifact/gguf_reader.hpp:414-465`
- 対応するブロック形状: `include/strata/artifact/gguf_reader.hpp:132-185`
- アーキテクチャ適合性 guard: `include/strata/artifact/gguf_reader.hpp:624-646`, `:783-839`
- 索引上の所属 scope: `docs/cli/README.md:1454-1458`。この文書作成時点でリンクと `strata-gguf` の scope は対象 parser と一致しています。

ビルド済み CLI の `--help` は実行していません。ソースに独立した help parser はなく、usage 表示と引数処理を直接確認しました。公式 Release 配布物における当該診断 CLI の有無・差異はこの調査では確認していません。
