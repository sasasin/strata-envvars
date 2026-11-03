# `GEMV_F16`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal の `metal/tests/gemv_parity.cpp` にある GEMV の性能・数値比較用プログラムで、FP16 GEMV カーネルをコンパイルして実行するかを切り替えます。Strata の通常の Metal 推論エンジンが読む変数ではありません。エンジン側の FP16 経路は別の環境変数 `STRATA_METAL_F16` で判定されます（`metal/src/engine/window.cpp:119-124,693-694`）。

## 値と判定

`std::getenv("GEMV_F16")` の null 判定だけを使います。値の変換や文字列比較はありません。

| 状態 | `gemv_parity` での結果 |
|---|---|
| 未設定 | FP16 用の `STRATA_METAL_F16` 定義を付けずに Metal ライブラリをコンパイルし、FP32 GEMV の比較を行う |
| 設定あり | 空文字、`0`、`false` を含む任意の値で FP16 用の定義を付けてコンパイルし、FP16 GEMV の比較も行う |

値が `1` かどうか、数値として有効か、大文字小文字、空白は検査されません。CLI 引数がこの判定を上書きする処理もありません。

## 有効になる条件

- Metal の `gemv_parity` 診断プログラムを実行する場合にだけ参照されます。推論エンジン、サーバー、他 backend の実行条件を切り替える用途ではありません（`metal/tests/gemv_parity.cpp:1-7,76-100`）。
- 設定時、同プログラムは `quant.metal`、`units.metal`、`gemv.metal` を `STRATA_METAL_F16` 定義付きでコンパイルします。FP16 カーネルはこの定義がある場合に限り `gemv.metal` に含まれます（`metal/tests/gemv_parity.cpp:98-100`; `metal/kernels/gemv.metal:162-165,218-223`）。
- FP16 の出力比較と最終 PASS/FAIL は、FP16 経路で測定対象 shape が実行され `worst16` が更新されたときに行われます。対象の shape や `--one`、`--bench` などは CLI 引数で選びます（`metal/tests/gemv_parity.cpp:83-97,289-328,347-360,373-376`）。

## 実行時の詳細

起動後、Metal ライブラリをコンパイルする時点で `GEMV_F16` の有無を読み、その結果をコンパイル文字列へ反映します。各 shape の処理でも同じ環境変数の有無を読み直し、設定時は半精度入力バッファを作り、FP32 の参照結果を取り、候補タイルの `gemv16_*` 出力との相対 L2 誤差を計算します（`metal/tests/gemv_parity.cpp:98-100,289-309,322-328,347-357`）。プログラム内に環境を書き換える処理はなく、外部から起動中プロセスの環境を変更して反映させる経路もありません。

FP16 経路を実行した場合、最後に `fp16: worst rel L2 vs fp32 ... PASS` または `... FAIL` を stdout に出します。誤差が `4e-3` 未満なら終了コード 0、それ以外は 1 です。FP16 経路を実行しない場合、この行は出ず、通常の終端は 0 です（`metal/tests/gemv_parity.cpp:373-377`）。

## 根拠

- `metal/tests/gemv_parity.cpp:1-7,76-100` — 対象が GEMV parity 診断プログラムであること、環境変数の直接読み取りと Metal ソースのコンパイル。
- `metal/tests/gemv_parity.cpp:289-309,322-328,347-360,373-377` — FP16 用バッファ、カーネル選択、誤差比較、観測可能な出力と終了コード。
- `metal/kernels/gemv.metal:162-165,218-223` — `STRATA_METAL_F16` による FP16 GEMV カーネルの条件付き定義。
- `metal/src/engine/window.cpp:119-124,693-694` — 通常の Metal 推論エンジンが別名 `STRATA_METAL_F16` を読むこと。
