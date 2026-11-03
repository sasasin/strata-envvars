# `STRATA_OLD_Q80_SCALED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

CUDA の scaled Q8_0 activation quantizer が使う CUDA kernel の実装を切り替えます。未設定時は warp 単位で32要素 block を処理する kernel、設定値の先頭が `1` のときは従来の1 CUDA thread あたり1 block の kernel を起動します。Q8_0 block と fp32 scale を生成する処理の kernel 配置を選ぶ変数で、通常の `quantize_q8_0()` や Q8_K quantizer の選択には使われません。

この関数は expert hit 用の activation 量子化（`src/core/expert_source.cpp:5388-5406`、`src/core/session.cpp:884-891`）や verify / MTP / remote expert 経路（`src/core/verify.cpp:2322-2327`、`src/core/mtp.cpp:1283-1287`、`src/core/remote_experts.cpp:345-348`）から呼ばれます。scaled Q8_0 quantizer 自体は CUDA ソース `src/kernels/cuda/quantize_act.cu` に実装されています。

## 値と判定

値全体の parse や数値変換はせず、環境変数が存在し、先頭文字が `'1'` かどうかだけを判定します。

| 環境変数の状態 | 判定 | 起動する kernel |
|---|---|---|
| 未設定 | 無効 | warp 単位の新 kernel |
| 空文字 | 無効 | warp 単位の新 kernel |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 | 1 thread あたり1 block の旧 kernel |
| それ以外（例: `0`, `true`, ` 1`） | 無効 | warp 単位の新 kernel |

読み取り結果は関数内の `static const bool` に保存されます。`n <= 0` の呼び出しは読み取りより先に return するため、最初の有効な正の `n` の呼び出し時に判定され、その後プロセス内で環境を変更しても反映されません。CLI 引数、設定ファイル、他の環境変数による優先順位や上書きはありません。

## 有効になる条件

この変数を読むコードは CUDA 実装の `src/kernels/cuda/quantize_act.cu` にあります。したがって CUDA の scaled Q8_0 quantizer がビルドされ、実行経路から `quantize_q8_0_scaled()` が呼ばれた場合に限り参照されます。設定しても通常の `quantize_q8_0()`、Q8_K quantizer、scaled quantizer を通らない実行経路は切り替わりません。Linux / Windows の違い、CLI モード、モデル状態などによる追加の値判定はありません。

## 実行時の詳細

関数は `n <= 0` の場合は何もせず戻り、`n` が32の倍数でない場合や `scales` が null の場合は stderr にエラーを出して `exit(1)` します。その後に環境変数を一度評価します。旧 kernel は `ceil((n/32)/128)` CUDA blocks を起動し、各 thread が32要素を量子化します。既定の warp kernel は1 warp（32 thread）で1 block を処理し、`ceil((n/32)/4)` CUDA blocks を起動します。両経路は共通の scaled block 量子化規則に従い、Q8_0 の34-byte block と各 block の fp32 scale を書き込みます（`src/kernels/cuda/quantize_act.cu:78-114,338-369`、`include/strata/kernels/quantize_act_dev.cuh:59-78`）。

この環境変数専用のログや警告はありません。kernel launch に失敗した場合は `quantize_q8_0_scaled launch: <CUDA error>` を stderr に出し、`exit(1)` します。`stream == nullptr` の場合は launch 後に `cudaDeviceSynchronize()` を呼びますが、その戻り値はこの関数では検査しません（`src/kernels/cuda/quantize_act.cu:364-369`）。

## 根拠

- `src/kernels/cuda/quantize_act.cu:338-369` — scaled quantizer の引数検査、環境変数の判定・cache、旧 / warp kernel の選択、launch error の処理。
- `src/kernels/cuda/quantize_act.cu:78-114`、`include/strata/kernels/quantize_act_dev.cuh:59-78` — 旧 thread kernel と warp kernel が実行する量子化計算。
- `include/strata/kernels/quantize_act.hpp:24-30` — 出力 block と fp32 scale の契約。
- `src/core/expert_source.cpp:5388-5406`、`src/core/remote_experts.cpp:345-348`、`src/core/verify.cpp:2322-2327`、`src/core/mtp.cpp:1283-1287`、`src/core/session.cpp:884-891` — scaled quantizer の呼び出し経路。
