# `STRATA_TC_SM75`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリと GPU ドライバー自身の環境変数動作は対象外。

## 役割

CUDA の BF16 dequantization で、出力先が16バイト境界に整列している場合に、Turing（compute capability 7.5）用のベクトル化ストア経路を選ぶかを制御します。有効時は32要素を一旦レジスタ上の配列に計算し、`uint4` による16バイト単位のストアで出力します。通常経路は各要素を計算時に書き込みます。対象コードは `src/kernels/cuda/dequant_bf16.cu` です。

## 値と判定

変数は `sm75_switch()` から `std::getenv(name)` で読み、設定されている場合は `std::atoi(value) != 0` で判定します。文字列全体の検証はありません。

| `STRATA_TC_SM75` | 判定 |
|---|---|
| 未設定 | `STRATA_SM75_PERF` の判定に従う。これも未設定なら無効 |
| 空文字 | `atoi("") == 0` のため無効（親変数の既定には戻らない） |
| `0` または数値変換結果が0 | 無効 |
| `1`、`-1`、`2` など数値変換結果が0以外 | 有効 |
| `true`、`false`、数字で始まらない文字列 | `atoi` の変換結果が0のため無効 |
| `1abc`、` 1tail` など | `atoi` が先頭の整数部分を変換し、結果が0以外なら有効 |

符号と先頭空白は `atoi` の変換規則に従います。`STRATA_SM75_PERF` も未設定時の親設定として参照され、こちらは `sm75_series()` 内の `static const bool` に初回評価結果が保存されます。

## 有効になる条件

- CUDA BF16 dequantization の `launch()` 経路であること。
- 出力先アドレスが16バイト境界に整列し、行 stride（`ld * sizeof(T)`）が16バイトの倍数であること。
- 実 GPU の compute capability が7.5であるか、`STRATA_EMULATE_CC` により7.5として扱われていること。
- 上記に加え、環境変数の判定が有効であること。

7.0/7.2や8.x以降の GPU はこの切替の対象外です。環境変数で別世代の GPU にこの経路を有効化することはできません。ただし `STRATA_EMULATE_CC=75` はホスト側の capability 判定を7.5に置き換えるため、テスト目的で対象判定を通せます。CUDA device 属性の取得に失敗した場合も `vec` は false になり、通常経路へ進みます。

## 実行時の詳細

`launch()` は BF16 dequantization の形状を検証し、Q8_0 の専用経路と、条件を満たす場合の `STRATA_DEQUANT_WIDE` 経路を先に試します。それらで return しなかった後、出力の alignment と stride を調べて GPU capability を取得し、`tc_sm75_enabled()` を呼びます。条件が揃えば各対応データ型で `dequant_kernel<TYPE, T, true>`、そうでなければ `dequant_kernel<TYPE, T, false>` を起動します。ベクトル化版は32要素の同じ dequant 計算結果をバッファに作り、その後 `uint4` で書き出します。

`STRATA_TC_SM75` 自体は呼び出しごとに `getenv()` されるため、未設定から設定済みに変わった場合も次の判定で読み直されます。未設定時に参照される `STRATA_SM75_PERF` は `static` に一度だけ評価されるため、その値は初回評価後に再読込されません。環境変数を評価する時点は capability 7.5 の場合に限られます。

この変数によるログ出力は実装にありません。起動失敗時は、通常の CUDA dequant launch error として `dequant launch: %s` を stderr に出して終了します。環境変数の値自体に対する警告やエラーはありません。

## 根拠

- `include/strata/core/tc_sm75.hpp:21-23` — `STRATA_TC_SM75` を `sm75_switch()` に渡す。
- `include/strata/core/sm75_series.hpp:24-44` — 親設定の一度だけの読み取り、整数変換、compute capability 7.5 限定、設定値の優先順位。
- `include/strata/core/emulate.hpp:14-24` — `STRATA_EMULATE_CC` による capability 判定の置換。
- `src/kernels/cuda/dequant_bf16.cu:170-192,341-406` — ベクトル化版のストア、適用条件、先行経路、kernel dispatch とエラー処理。
- `CMakeLists.txt:418` — `dequant_bf16.cu` が CUDA kernel source として列挙される。
- `docs/DETAILS.md:2526-2539` — Turing kernel 群は opt-in とされ、同文書でこの変数を BF16 dequant の16バイトストアとして分類。ここにある性能値は kernel 群についての記載であり、この変数単独の効果を示すものとしては扱わない。
