# `STRATA_LOGPOS_TOPK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_LOGPOS` の verify-window 測定出力に、logit が大きい上位 token の ID と、その token の log-probability を追加します。位置ごとのタブ区切り行に `id:logprob` 列が K 個増え、別エンジンとの top-k 比較に使えます。サンプリングや生成 token を変える処理ではありません。

## 値と判定

値は `std::atoi` で整数に変換し、その結果を `max(0, min(256, value))` で制限します。文字列全体の検証はありません。

| 環境変数の状態・値 | K と出力 |
|---|---|
| 未設定 | 0。追加列なし |
| 空文字、数字で始まらない文字列 | `atoi` が 0 を返し、追加列なし |
| 整数として 0 以下 | 0。追加列なし |
| 正の整数 1〜256 | その数だけ追加列を出力 |
| 256 より大きい正の整数 | 256 に clamp |
| 数字の後ろに文字が続く | `atoi` が読める先頭部分だけを使う。例: `20tail` は K=20 |

先頭空白や符号は `atoi` の変換規則に従います。整数として表現できないほど大きな文字列について、コードは変換エラーを検査していません。K は 256 までに制限されますが、語彙数 `n_vocab_` に対する制限はコード上ありません。

## 有効になる条件

この変数だけではファイル出力を開始しません。`--serve` のプロンプト処理が verify-window の `read_windows` 経路を通り、`STRATA_LOGPOS` で指定したファイルを `fopen(..., "ab")` できた場合に `Verifier::window_logprobs()` が呼ばれ、その行に追加列が出ます。`STRATA_LOGPOS` が未設定、空または開けないパスの場合、上位 token 列を含む出力はありません。パスを開けなかった場合の専用警告はこの処理にありません。

`STRATA_LOGPOS` が設定されていると、条件が合えば使われる pipelined prompt-read 経路を避けて serial verify-window loop に進みます。CUDA 側の分岐条件は `pipe && n_stages == 2 && pl_pw >= 1`、SYCL 側は `pipe && pl_pw >= 1` です。これは `STRATA_LOGPOS` 側の経路選択であり、`STRATA_LOGPOS_TOPK` 自体による条件ではありません。

## 実行時の詳細

値は `Verifier::window_logprobs()` 内の関数ローカル `static const int topk` として初回評価時に一度だけ読みます。したがって同一プロセスで初回評価後に環境を書き換えても K は変わりません。関数は `STRATA_LOGPOS` のファイルが開いている場合に呼ばれるため、通常は最初の該当 prompt verify window で評価されます。CUDA/HIP と SYCL はそれぞれの実装内に同じ初回読み取りがあります。

各出力行では語彙 ID 全体を index 配列に並べ、logit の降順で `partial_sort` して先頭 K 件を出力します。列は `id:logprob` 形式で、log-probability は全語彙に対して計算した `lse` を用いる `row[id] - lse`、小数 6 桁です。既存列の後ろにタブ区切りで追加されます。出力先は `STRATA_LOGPOS` のファイルで、各 window の処理後に flush されます。値の不正を知らせる専用ログや fallback はありません。

K が `n_vocab_` より大きい場合に K を語彙数へ clamp する処理は見当たりません。したがってその条件の扱いはソースで安全性を保証していません。

## 文書との照合

`docs/UNSLOTH_Q4.md` は同じ token 列を使った Strata と llama.cpp の分布比較で `STRATA_LOGPOS_TOPK=20` を指定しており、再現方法にも `STRATA_LOGPOS=<file>` と本変数の併用を記載しています。そこにある一致率・KL 等は同文書記載の測定条件で得られた値であり、本変数単独の性能・正確性を保証するものではありません（`docs/UNSLOTH_Q4.md:190-226`）。

## 根拠

- `src/core/verify.cpp:2438-2447,2471-2490`: `window_logprobs()` の入力確認、基本列、変数の変換/clamp、top-k 選択・出力、flush。
- `sycl/src/core/verify.cpp:2558-2568,2588-2607`: SYCL 側の同等処理。
- `src/program/generate.cpp:10647-10650,10679-10693`: `STRATA_LOGPOS` による経路分岐、ファイル open、`window_logprobs()` 呼び出し。
- `sycl/src/program/generate.cpp:9964-9966,9989-10003`: SYCL 側の同等呼び出し経路。
- `src/program/generate.cpp:6859,11053`: `--serve` の request 処理内と `read_windows` の呼び出し。
- `docs/UNSLOTH_Q4.md:192-198,224-226`: 測定の説明と `STRATA_LOGPOS_TOPK=20` を使う再現手順。
