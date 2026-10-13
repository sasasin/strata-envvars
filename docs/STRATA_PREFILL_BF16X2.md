# `STRATA_PREFILL_BF16X2`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

prefill 中に BF16 へ丸める活性値について、丸めで失われた下位成分も BF16 にして、同じ重みを使う追加 GEMM として出力に加えます。基準の GEMM が `W × hi`、追加分が `W × lo` となり、積算結果は `W × (hi + lo)` に相当します。コードコメントは約16 mantissa bitsを保持し、decode の FP32 入力に近づける意図を記しています。既定では無効で、プロンプト側の数値が変わる opt-in です。

対象は hyper-connection、SSM alpha/beta、indexer、router、shared gate、PLE key/value などの BF16 重み射影です。実際に下位成分を渡すかは射影ごとに実装され、重みが BF16 でない PLE key の経路などには適用されません。

## 値と判定

環境変数を `std::atoi` で整数化し、unset は `0` とします。空文字や数字で始まらない値も `atoi` の結果は `0` です。先頭空白と符号は `atoi` の規則で扱われ、数字列の後ろに続く文字列は判定に使われません（例: `1abc` は `1`、`2.5` は `2`）。

| `atoi` の結果 | BF16入力の通常の射影 | hyper-connection射影 |
|---:|---|---|
| `0` | 下位成分なし（既定） | 下位成分なし |
| `1` | 下位成分を加算 | 下位成分も加算 |
| `1` 以外の非ゼロ値 | 下位成分を加算 | 下位成分なし |

負の非ゼロ値も通常射影では有効です。hyper-connection の判定は整数値が厳密に `1` かどうかなので、`-1`、`2`、`3` などは通常射影だけに適用されます。数値変換結果が範囲外の場合の扱いは、コードで検査されていません。

## 有効になる条件

- prefill の当該 stage が BF16 活性値を使う場合に適用されます。stage の FP16 入出力経路 (`f16_io`) では、環境変数が非ゼロでもモードを `0` に上書きします。コードコメントはFP16入力にはこのBF16下位成分が適用されない理由として、FP16が11 mantissa bitsを持つ点を挙げています。
- 下位成分バッファは mode 1 のとき hyper-connection 用（`xn16_lo`, `lo16_lo`）も確保し、任意の非ゼロ値では通常射影用（`mixed_bf_lo`）を確保します。これらの配列がない経路では追加項は生成されません。
- PLE key projection は BF16 重みの経路で下位成分を加算します。native 重みの経路ではkey側の追加GEMMはありません。PLE value はBF16重みに対して下位成分を加算します。
- CUDA実装とSYCL実装に同じ値判定と射影ヘルパーがあります。HIP/CUDA/SYCLの具体的なGEMM実装はビルド経路ごとに異なりますが、環境変数のモード判定は共通の形です。

## 実行時の詳細

判定値は関数内 `static const int` に保存されるため、各実行ファイルで初めて `bf16x2_mode()` が呼ばれた後に環境を変更しても再評価されません。値は環境変数の有無ではなく `atoi` の整数結果で判断します。

通常射影では `bf16_proj()` がまず高位BF16入力で `beta=0` のGEMMを実行し、下位入力がある場合に同じBF16重み・出力を使って `beta=1` のGEMMを続けます。高位・下位の値は `to_bf16` 等のカーネルで作られ、下位値は元のFP32値から高位BF16値を戻した差をBF16化したものです。

追加バッファは通常のprefill作業領域の割り当てと必要領域見積りにも反映されます。追加演算によりprompt経路の数値は変わります。実装箇所にこの環境変数専用のログ出力はありません。

## 根拠

- `src/prefill/prefill.cpp:301-315,327` — 役割、`atoi`、既定値、FP16経路の無効化、mode 1 のhyper-connection条件。
- `sycl/src/prefill/prefill.cpp:235-249,261` — SYCL側にも同じ判定。
- `src/prefill/prefill.cpp:1227-1228,1863-1864` — 通常の実領域と必要サイズ計算での下位配列確保。
- `src/prefill/prefill.cpp:1948-1953` — 高位GEMM後に下位GEMMを `beta=1` で加算する処理。
- `src/prefill/prefill.cpp:2514-2538,2570-2626,2642-2643,2669-2670,2894-2899,2964` — PLE、hyper-connection、SSM、indexer、router/shared gate系の適用箇所と条件。
- `src/prefill/kernels.cu:40-42,1716-1722` — 下位BF16値の定義と生成。
- 同じロジックのSYCL版: `sycl/src/prefill/kernels.dp.cpp` および `sycl/src/prefill/prefill.cpp:2769-2781,2814-2834,2876-2900,2926-2927,3208-3217`。
