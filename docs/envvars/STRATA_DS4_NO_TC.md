# `STRATA_DS4_NO_TC`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

`strata-dsv41` の DeepSeek V4.1 expert 計算で、対応 GPU 上の Tensor Core / WMMA カーネルを選ばず、通常の F32 カーネルへ切り替えるための開発・診断用フックです。GGUF の MXFP4 expert 経路では CUDA と HIP の両方に判定があります。IQ / K 型 expert 経路での判定は CUDA のみです。

対象は `src/dsv41/` 以下の DeepSeek エンジン実装です。

## 値と判定

環境変数を読む各 `tc_ok()` は文字列全体や数値を parse せず、先頭文字が `'1'` かだけを見ます。

| 値 | 判定 |
|---|---|
| 未設定 | Tensor Core 経路を禁止しない |
| 空文字 | Tensor Core 経路を禁止しない（先頭文字は終端文字） |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | Tensor Core / WMMA 経路を禁止する |
| それ以外（例: `0`, `true`, ` 1`, `2`） | Tensor Core 経路を禁止しない |

大文字小文字、空白、数値としての妥当性は判定しません。値が `1` 以外でも GPU 世代などの条件を満たせば高速カーネルが選ばれます。

## 有効になる条件

- **CUDA の GGUF MXFP4 経路**: 現在のデバイスの Compute Capability major が 7 以上で、変数の先頭文字が `1` でなければ `tc_ok()` が true になります。true の場合 `set_gate_up` と `set_down` は Tensor Core カーネルを起動し、false の場合は `mx_set_kernel` の F32 カーネルへ進みます。
- **HIP の GGUF MXFP4 経路**: `cudaGetDeviceProperties` が成功し、GPU の `gcnArchName` が `gfx1100`, `gfx1101`, `gfx1102`, `gfx1103`, `gfx1150`, `gfx1151`, `gfx1152`, `gfx1200`, `gfx1201` のいずれかで始まり、変数の先頭文字が `1` でなければ WMMA カーネルが選択されます。それ以外は `mx_set_kernel` を使います。
- **CUDA の IQ / K 型経路**: Compute Capability major が 7 以上で先頭文字が `1` でなければ `set_tc_kernel` を選びます。false なら行数に応じた `set_kernel` に進みます。デバイス番号が 0–15 の範囲外なら `tc_ok()` は false です。
- **HIP の IQ / K 型経路**: `tc_ok()` は常に false を返します。ただし `launch_set()` は先に `STRATA_DS4_HIPK` による `hipk::launch()` を試し、そこで起動に成功すれば戻ります。この HIPK 経路にも `STRATA_DS4_NO_TC` の参照はなく、この変数は IQ / K 型の HIP 経路を止めません。

DeepSeek の設計資料も、trellis expert は gfx12 では Tensor Core、その他の GPU では通常の FMA で実行すると説明しています（`docs/DEEPSEEK41.md:125-128`）。この説明は `STRATA_DS4_NO_TC` の全経路や値判定までは記述していません。

## 実行時の詳細

GGUF の `tc_ok()` は関数内 `static const bool` に結果を一度だけ保存します。最初の呼び出し時のデバイスと環境変数を使い、以後はプロセス中に環境を書き換えても再評価されません。複数 GPU でデバイスごとに値を変える仕組みではありません。

IQ / K 型の CUDA `tc_ok()` はデバイスごとの `state[16]` に結果を保存します。各デバイスで初めて呼ばれたときにデバイス属性と環境変数を読み、以後はその状態を使います。したがって、そのデバイスでの初回判定後の環境変更は反映されません。

この変数を読む箇所自体はログを出しません。CUDA の GGUF では `cudaDeviceGetAttribute` の戻り値を確認せず、major の初期値 0 のままなら Tensor Core 条件を満たしません。HIP の GGUF ではデバイスプロパティ取得に失敗すると false です。

## 根拠

- `src/dsv41/ds4_gguf.cu:932-956`: CUDA / HIP の GPU 判定、環境変数の先頭文字チェック、GGUF 側の静的キャッシュ。
- `src/dsv41/ds4_gguf.cu:1401-1409,1458-1466`: GGUF の gate-up / down で WMMA または Tensor Core カーネルと F32 カーネルを選択。
- `src/dsv41/ds4_iq.cu:1078-1096`: IQ / K 型の CUDA 判定、デバイス単位のキャッシュ、HIP では常に false。
- `src/dsv41/ds4_iq.cu:1178-1194`: HIPK の先行起動と CUDA Tensor Core / 通常カーネルの選択。
- `docs/DEEPSEEK41.md:123-128`: trellis expert の GPU / CPU 実行についての設計資料。
