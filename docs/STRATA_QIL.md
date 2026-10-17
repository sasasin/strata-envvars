# `STRATA_QIL`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の batched verify/decode で、2〜4 token 分の projection 入力を Q8_1 へ量子化する際、同じ CUDA kernel launch 内で interleaved 形式のコピーも作るかを制御します。これにより、後段が interleaved MMVQ kernel を使う場合に別の interleave launch を省けます。通常の Q8_1 量子化結果と interleaved 形式を同時に生成します。

この変数は interleaved MMVQ 自体を有効化する設定ではありません。個別の interleaved matvec 経路は `STRATA_MMVQ_IL` と weight type・shape の対応条件にも従います。

## 値と判定

値は `std::atoi()` で整数に変換され、`qil_env >= 0` なら 0 を無効、それ以外を有効として扱います。`atoi` は数値全体の厳密な検証をせず、先頭の空白と符号を許し、数値の後ろの文字を無視します。

| 値 | 判定 |
|---|---|
| 未設定 | 既定判定へ進む |
| `0`、`0abc`、空文字、数値に変換できない文字列 | 無効（`atoi` の結果が 0） |
| 正の整数で始まる文字列（例: `1`, `2abc`） | 有効 |
| 負の整数で始まる文字列 | 既定判定へ進む（変換結果が 0 未満） |

明示値が負の場合も未設定時と同じ既定判定になります。値の判定は `quant_in` 内の関数ローカル `static const` に保存されるため、最初の評価後にプロセス環境を変更しても再評価されません。

根拠: `src/core/verify.cpp:1263-1270`。

## 有効になる条件

- 対象は CUDA build の verifier です。`STRATA_QIL` の読み取りと融合量子化への分岐は `#if !defined(STRATA_USE_HIP)` 内にあり、HIP build では使われません。
- 明示値が 0 以上なら、その値が優先されます。1 以上であれば Turing 以外でも融合量子化を要求します。
- 未設定または負値の場合は `device_is_sm75()` の結果を使います。これは現在 device の compute capability が 7.5 で、かつ `STRATA_SM75_PERF` が整数として非 0 の場合に true です。`STRATA_EMULATE_CC` が設定されていると compute capability 判定はその値で置き換わります。デバイス照会に失敗した場合は false です。したがって、単に Turing GPU であるだけでは既定で有効になりません。
- 既定判定が true でも、各 `quant_in` 呼び出しで token 数 `n` が 2〜4 の範囲にあり、`STRATA_MMVQ_IL` が有効でなければ融合経路へ入りません。`STRATA_MMVQ_IL` は未設定なら有効、設定値の先頭文字が `0` なら無効です。
- 融合生成した interleaved データを後段の MMVQ が使うかは、さらに `native_mmvq_il_supported()` の weight type・shape 判定に依存します。非対応時の matvec は通常の `native_mmvq` 経路へ進みます。

根拠: `src/core/verify.cpp:1266-1277,1279-1288`; `src/core/verify.cpp:276-291`; `include/strata/core/sm75_series.hpp:14-23`; `include/strata/core/emulate.hpp:12-18`。

## 実行時の詳細

`quant_in` が対象になる projection 入力は GDN の projection、GDN out projection、および QSA attention out projection を含みます。入力がすでに Q8_1 として作られている経路などでは、呼び出し自体が省かれる場合があります。融合条件を満たせば `native_quantize_q8_1_il()` を呼び、満たさなければ `native_quantize_q8_1()` で通常の Q8_1 だけを生成します。後段が interleaved MMVQ に対応しない場合でも、この値判定自体は量子化経路を選ぶ時点で行われます。

通常経路では interleaved MMVQ が必要な場合に Q8_1 量子化後、`mm` 側で `native_q8_1_interleave()` を呼ぶため、融合はその追加 launch をまとめます。実装コメントは Turing 系の batched decode で GDN layer ごと・QSA layer ごとに2 launch少なくなると説明しています。これは実装コメント上の説明で、ここでは独立した測定結果としては扱いません。`STRATA_QIL` による stdout/stderr ログ出力はありません。

ソースでは `STRATA_QIL` による結果の精度差や性能保証は示されていません。`docs/DETAILS.md` は Turing kernel series の一つとして QIL を挙げ、「少ない launch」と説明していますが、同資料の Turing 系は `STRATA_SM75_PERF=1` で有効になる系列です。

根拠: `src/core/verify.cpp:1263-1288,1316-1329,1418-1425,1471,1792-1794`; `src/kernels/cuda/native_mmvq.cu:2850-2865`; `docs/DETAILS.md:2244-2255`; `include/strata/core/sm75_series.hpp:3-15`。
