# `STRATA_QSA_SPLIT_ATTN`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA の decode attention を、int8 KV 向け tensor-core kernel で query ごとに複数 block へ分割して計算する opt-in スイッチです。分割部分の attention 結果を log-sum-exp の再スケールで merge します。通常の `qsa_decode_attn_batch` とは演算順序が異なるため、ビット単位では一致しません。

この環境変数を読むのは verifier の通常 QSA decode 経路と MTP drafter の attention 経路です。分割 kernel が利用できない場合、呼び出し元は従来の `qsa_decode_attn_batch` に戻ります（`src/core/verify.cpp:1771-1778`, `src/core/mtp.cpp:1030-1033`）。

## 値と判定

両方の読み取り箇所で `std::getenv` の結果を `std::atoi` に渡し、未設定でなく、変換結果が 0 以外なら要求を有効とします。文字列全体の妥当性検査やエラー処理はありません。

| 値の例 | 判定 | 理由 |
|---|---|---|
| 未設定、空文字、`0`、`0tail`、`true` | 無効 | 未設定は false。`atoi` の変換結果が 0 |
| `1`、`2`、`-1`、`1tail` | 有効 | 先頭の整数変換結果が 0 以外 |
| 空白の後に整数がある文字列（例: ` 1x`） | 有効 | `atoi` は先頭空白を読み飛ばし、整数部分を変換 |

したがって `=1` だけが有効値ではなく、`atoi` が非ゼロに変換する文字列も有効です。`true` のような数値で始まらない文字列は有効になりません。既定値は無効です。

## 有効になる条件

環境変数が有効でも、分割 kernel が実行されるには次の条件を満たす必要があります。

- CUDA 経路であること。`qsa_decode_attn_split` は HIP コンパイル時には直ちに `false` を返し、SYCL 実装からこの関数を呼ぶ箇所は確認できません（`src/kernels/cuda/qsa_prompt_attn.cu:2206-2208`）。
- GPU compute capability が sm_80 以上であること（同 `:2214-2224`）。
- 対象の形状が `head_dim == HD` かつ `n_head == G * n_head_kv` で、KV pool が通常の int8 K/V と両方の scale を持つこと。Q4 KV は対象外です。`cap` は正数で、`ids`、`steps`、`page_table` も必要です（同 `:2209-2213`）。
- 分割結果を格納する caller の scratch が必要量を満たすこと。必要量を超える場合は `false` を返して従来 kernel に戻ります（同 `:2234-2238`）。
- CUDA kernel attribute の設定に失敗しないこと。失敗時も `false` となり、呼び出し元は従来 kernel を使います（同 `:2225-2232`）。

verifier では batch-rec の slot 経路（`src/core/verify.cpp:1709-1753`）はこのスイッチを通さず、従来の attention 関数を呼びます。MTP では `record_rest` 内の drafter attention が対象です。

## 実行時の詳細

各読み取り箇所は関数内の `static const bool` に値を保存します。そのため各箇所は最初に実行されたときだけ環境を読み、その後の環境変更はその箇所に反映されません。2か所の static は独立しているため、一方の初回評価後、もう一方が初めて評価される前に環境が変われば、評価結果が異なる可能性があります（`src/core/verify.cpp:1772`, `src/core/mtp.cpp:1031`）。

分割数は GPU の SM 数と query 数から算出され、少なくとも1、最大20、さらに `cap` の chunk 数以下に制限されます。scratch 容量が足りなければ分割を使いません。条件が整うと split kernel と merge kernel を同じ CUDA stream に launch します。launch 後の CUDA error は `qsa_decode_attn_split: <CUDA error>` を stderr に出して `exit(1)` し、従来 kernel への fallback にはなりません（`src/kernels/cuda/qsa_prompt_attn.cu:2234-2249`）。この環境変数自体の有効・無効を知らせるログはありません。

## 文書・測定値との照合

`docs/DETAILS.md:2220-2235` は本スイッチを sm_80 以上かつ int8 KV の decode attention 向けと説明しています。表には RTX 3060 / RTX A4000（sm_86）、IQ3_XXS、各5ペアの全体 engine 比較として、それぞれ +2.8% / +3.5% と記載されています。同節の説明では decode は30K token prompt 後、各ペアの中央値を使っています。表は精度を「rounding-level」とし、teacher-forced KL 0.0016、floor 0.0012 と記載します。これらは同資料が報告する測定値であり、この調査で再測定した値ではありません。

## 根拠

- 値の読み取りと fallback: `src/core/verify.cpp:1771-1778`, `src/core/mtp.cpp:1030-1033`
- 対応 geometry / KV / backend / GPU / scratch / launch: `src/kernels/cuda/qsa_prompt_attn.cu:2203-2250`
- kernel の役割と非 bitwise 一致: `include/strata/kernels/qsa_prompt_attn.hpp:32-38`
- 既存の測定記録: `docs/DETAILS.md:2220-2235`
