# `--dump-residual`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root 引数） |
| オプション | `--dump-residual` |
| 別名 | なし |
| 値 | 必須の出力パス（`PATH`） |

## 役割

通常の生成実行の終了時に、GPU 上の最終 residual `R` をホストへ読み戻し、head と各層の計算を切り分ける調査用データとして保存する。CUDA/HIP 系 parser と SYCL 系 parser の両方に同じオプションがある。索引上は `strata-engine/root` のスコープである。

## 使い方

```sh
# トークン ID 1 個を入力し、実行後に residual を /tmp/final-r.bin へ保存
strata --tokens 1 --dump-residual /tmp/final-r.bin
```

`--tokens` は通常実行で必要な入力であり、`--dump-residual` 自身は出力パスを受け取る。ソースの usage 表示は `strata generate ...` と記す一方、確認した parser は `argv[1]` からオプションを読むため、ここでは parser が受理する root 引数の形を例示した。エンジンの呼び出しラッパーが `generate` を付加するかどうかは、この調査範囲では確認していない（`engine/src/program/generate.cpp:1208-1214,3842-3852`）。

## 値と既定値

- `PATH` は必須。省略すると共通の値取得処理が `--dump-residual needs a value` を標準エラーへ出して終了コード `2` で終了する（`engine/src/program/generate.cpp:3844-3846`）。
- 既定値は空文字列で、指定しなければダンプしない（`engine/src/program/generate.cpp:827,25437-25438`）。空文字列を明示した場合も同じ条件で出力処理をスキップする。
- パス文字列自体の形式検証はない。重複指定は拒否されず、parser の単純代入により最後の指定値が使われる（`engine/src/program/generate.cpp:3894`）。

## 実行時の動作

生成処理の後、`ss.R` の `hc * n_embd` 個の `float` をデバイスからホストへコピーし、指定パスを `fopen(..., "wb")` で開く。ファイルには先頭に `int32_t` 2 個（`hc`, `n_embd`）を続けて書き、その後に residual の `float` 配列を続ける。コード上の形状は `hc x n_embd` で、データ長はヘッダー 8 バイトと `hc * n_embd` 個の float 分である。ファイルはバイナリモードで開かれ、同名ファイルがあれば切り詰めて上書きする（`engine/src/program/generate.cpp:25436-25451`）。

この出力ブロックは通常生成経路の後処理にある。サーバー経路は要求処理ループ後に先に `return 0` するため、このオプションによるダンプはサーバー要求ごとには行われない（`engine/src/program/generate.cpp:23958-23972`）。

## 適用条件と副作用

- CUDA/HIP 系では CUDA のデバイス間コピー、SYCL 系では SYCL の in-order queue でのコピーを待ってから書き出す。各実装の parser・出力処理はそれぞれ `engine/src/program/generate.cpp:1285,3894,25437-25459` と `engine/sycl/src/program/generate.cpp:873,1933,14417-14443` にある。
- 出力先の既存ファイルは上書きされる。値にディレクトリだけを指定した場合など、開けないパスでは失敗する。
- ファイル形式はソースが `int32_t` と `float` をそのまま書き込むところまで確認した。バイト順や float 表現を別環境間で交換するための規約は、このソース箇所からは確認できない。

## 出力とエラー

- コピー失敗時は `strata generate: reading R back failed` を標準エラーに出して終了コード `1` を返す。出力先を開けない場合は `strata generate: cannot write <PATH>` を出して `1` を返す（CUDA/HIP: `engine/src/program/generate.cpp:25439-25446`、SYCL: `engine/sycl/src/program/generate.cpp:14420-14430`）。
- 成功時は標準出力に出力パス、形状、非有限値数、平均絶対値、最大絶対値を表示する（CUDA/HIP: `engine/src/program/generate.cpp:25452-25459`、SYCL: `engine/sycl/src/program/generate.cpp:14436-14443`）。
- `fwrite` と `fclose` の戻り値はこのブロックで検査されないため、書き込み後の遅延 I/O エラーを検出するかはソースから保証できない（同上）。

## 根拠

- `engine/src/program/generate.cpp:827,1285,3894` — CUDA/HIP 系の値保持、help 表示、parser。
- `engine/src/program/generate.cpp:25436-25459` — residual の読み戻し、バイナリ形式、ファイル作成、成功表示。
- `engine/src/program/generate.cpp:23958-23972` — サーバー経路の終了位置と通常生成後処理の開始。
- `engine/sycl/src/program/generate.cpp:511,873,1933,14417-14443` — SYCL 系の値保持、help 表示、parser、読み戻しと書き出し。
