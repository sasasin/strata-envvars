# `STRATA_DEQUANT_WIDE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。作業ツリーは `main...origin/main` で clean。外部ライブラリの環境変数は対象外。

## 役割

CUDA 実装の dense-weight dequantization で、Q4_K / Q5_K / Q6_K / IQ4_XS 用の wide kernel を使うかを制御します。通常 kernel は32値ごとのグループを1 thread が処理し、wide kernel は8値ずつ処理して連続した出力を書きます。これは prompt の量子化重みを GEMM 用 scratch に展開する経路で使われます（`src/prefill/gemm.cu:901-952`）。

この環境変数は CUDA 実装 `src/kernels/cuda/dequant_bf16.cu` にだけ実装されています。SYCL 用の対応ソース `sycl/src/kernels/cuda/dequant_bf16.dp.cpp` には wide kernel とこの変数の読み取りがありません。したがって、その経路の動作をこの変数で切り替えることはできません。

## 値と判定

| 値 | wide kernel の選択 |
| --- | --- |
| 未設定 | GPU の compute capability が 6.1 の場合だけ既定で有効。それ以外は無効 |
| 空文字 | 未設定と同じ既定判定 |
| 空でない文字列で `atoi(value) != 0` | 有効 |
| 空でない文字列で `atoi(value) == 0` | 無効 |

文字列全体の厳密な数値検証はありません。`atoi` の規則により、先頭の空白と符号は数値変換に使われ、数値部分の後ろにある文字は無視されます。先頭が数値として読めない文字列は 0 になり無効です（例: `2junk` は有効、`junk2` は無効、`-1` は有効）。空文字だけは `atoi` に渡さず、既定判定へ進みます。読み取り結果は関数内の `static const int` に保存されるため、初回判定後にプロセス環境を変更しても反映されません（`src/kernels/cuda/dequant_bf16.cu:267-281`）。

## 有効になる条件

値判定が有効でも、次の条件をすべて満たす場合に限り wide kernel が起動します。

- 対象型が Q4_K / Q5_K / Q6_K / IQ4_XS（内部 type 12 / 13 / 14 / 23）。
- 入力ブロックのアドレスが2バイト境界、出力アドレスが16バイト境界に揃っている。
- 出力行 stride が `T` 型のバイト数で16の倍数。
- `4 * rows * groups_per_row < 2^31`。

いずれかを満たさない場合は通常の dequant kernel に進みます。wide 判定が無効の場合も同じです。CUDA device の取得または capability 属性の取得に失敗した場合、あるいは device index が 0–63 の範囲外の場合も無効として扱います。取得失敗時の CUDA error は `cudaGetLastError()` でクリアされます（`src/kernels/cuda/dequant_bf16.cu:268-281,325-379`）。

## 実行時の詳細

判定は wide kernel を選ぶ必要が生じた時に評価され、環境値と既定時の GPU capability 判定がキャッシュされます。既定時は GPU ごとに capability を調べ、major 6 / minor 1 の GPU だけ有効化します。明示的な空でない値があれば、この GPU 判定より優先します。

wide kernel を使うのは対象4形式だけで、Q4_0、Q5_0、Q8_0、Q3_K、IQ4_NL、Q2_0 などはこの分岐に入りません。BF16 / FP16 / FP32 の出力経路はいずれも共通 `launch()` を通りますが、形式・アラインメント・stride などが合わなければ通常 kernel に戻ります（`src/kernels/cuda/dequant_bf16.cu:325-379,395-425`）。環境変数による警告や状態ログはありません。

公開関数 `dequant_set_wide(int)` は parity 検査用の上書きです。値が 0 以上なら環境値と GPU 既定値より優先し、負値なら環境値の判定へ戻します（`include/strata/kernels/dequant_bf16.hpp:32-34`; `src/kernels/cuda/dequant_bf16.cu:267-271,383`）。

## 文書との照合

`docs/OLDER_GPUS.md:103-121` は Tesla P40（compute capability 6.1）での測定を記載し、wide dequantization を既定有効、`STRATA_DEQUANT_WIDE=0` を無効化方法として示しています。Q6_K の記載値は 10240 x 2560 形状で 7.2 ms から 0.33 ms、他の3形式についても倍率を記載しています。これは同文書が示す P40 と測定条件に限定された報告値であり、別 GPU での性能を示すものではありません。ソースコメントにも同じ P40 測定と `=0` / `=1` の切替が記載されています（`src/kernels/cuda/dequant_bf16.cu:178-187`）。

## 根拠

- `src/kernels/cuda/dequant_bf16.cu:178-187,254-282` — wide kernel、環境値の parse、既定の capability 判定。
- `src/kernels/cuda/dequant_bf16.cu:325-379,395-425` — 起動条件、fallback、出力型ごとの共通経路。
- `src/prefill/gemm.cu:901-952` — prompt GEMM 用の dense weight 展開呼び出し。
- `sycl/src/kernels/cuda/dequant_bf16.dp.cpp:219-283` — SYCL 実装は通常 dequant kernel のみ。
- `include/strata/kernels/dequant_bf16.hpp:32-34` — parity 用の上書き API。
- `docs/OLDER_GPUS.md:103-121` — P40 の条件付き測定と利用者向け説明。
