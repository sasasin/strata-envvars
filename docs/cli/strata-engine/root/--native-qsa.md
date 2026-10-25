# `--native-qsa`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--native-qsa` |
| 別名 | なし |
| 値 | 取らない真偽フラグ |

## 役割

QSA 層の RMS 正規化と attention 出力ゲートに、実験的な native 演算実装を選びます。`strata generate` の usage もこの option を「QSA normalization and output gate」と説明しています（`src/program/generate.cpp:849-852`）。

## 使い方

```sh
strata generate --pack DIR --tokens "1,2,3" --native-qsa
```

`--pack` と `--tokens` は engine の基本入力です。QSA を持つモデルでない場合、このフラグだけでは QSA 演算は呼び出されません。

## 値と既定値

値は不要です。parser は `--native-qsa` を見つけると `o.native_qsa = true` にし、`Options` の初期値は `false` です。繰り返し指定しても同じ真値を設定します。option 自体に値範囲や追加 validation はありません（`src/program/generate.cpp:448-450,2494-2497`）。値を続けて別引数として渡すと、その引数は別 option として解析され、未知の引数なら usage を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2787-2792`）。

## 実行時の動作

parser の値は session 構築前に `native_qsa_set_enabled` へ渡されます（`src/program/generate.cpp:3936-3941`）。有効時、QSA 層の正規化では通常の `rms_norm_weighted` の代わりに native weighted RMS norm を選択します（`src/core/layer.cpp:1131-1140`）。この実装は各行の二乗平均から `rsqrt(mean + epsilon)` を求め、入力・重み `gamma` を乗じて出力します（`src/kernels/cuda/native_qsa.cu:45-68,133-143`）。

attention の出力ゲートでは、native 実装が `q_full` の各 head の後半 gate 値に sigmoid を適用し、attention 値に乗じます。無効時は既存の `qsa_gate_apply_f32` を使います（`src/core/layer.cpp:1294-1301`; native 演算は `src/kernels/cuda/native_qsa.cu:94-101,160-165`）。バッチ verify の QSA 経路にも同じ切替があり、適用箇所の一つです（`src/core/verify.cpp:1559-1565,1902-1910`）。

## 適用条件と副作用

- 影響するのはモデル実行中に通る QSA 層の正規化・出力ゲートです。ほかの層や QSA indexer の key cache / pooling はこのフラグの対象外です。indexer は別の `--native-qsa-indexer` で切り替えます（`src/core/layer.cpp:1131-1140,1294-1301`; `src/program/generate.cpp:2494-2497`）。
- `--native` で native model を選ぶ経路では、この option も含む一連の native 経路がまとめて有効になります（`src/program/generate.cpp:3258-3268`）。個別 option は A/B 用に残すと usage にあります（`src/program/generate.cpp:856-859`）。
- `--native-rope` は独立した切替です。通常の QSA 正規化後の RoPE は別の native/fallback 分岐を持ち、batch verify では `--native-qsa` と `--native-rope` の両方が有効で、形状が利用条件を満たす場合に norm と RoPE の融合経路を選ぶことがあります（`src/core/layer.cpp:1133-1136`; `src/core/verify.cpp:1566-1575`）。`--native-qsa` 単独では RoPE の実装を切り替えません。
- CUDA 実装は GPU kernel を起動します。ヘッダーでは、この helper 群は呼び出し元所有の stream を使い、helper 自身は同期・メモリ確保をしないとしています（`include/strata/kernels/native_qsa.hpp:10-20`）。
- Metal engine の stub には setter/getter がある一方、native QSA 演算は `missing(...)` を呼び出す実装です。そのため Metal build でこのフラグが parser に受理されても、該当演算が呼ばれれば失敗し得ます。parser に backend 別の拒否条件はありません（`metal/src/engine/setup_host.cpp:53-55`; `metal/src/engine/stubs.cpp:275,279-281`）。この調査では各 backend の実行確認はしていません。

## 出力とエラー

CUDA native helper は次元が正で要素数が上限内であること、epsilon が有限かつ非負であること、stream・buffer の整列と重なり条件などを検査し、不正なら例外を投げます。また kernel 起動エラーも例外になります（`src/kernels/cuda/native_qsa.cu:103-126,133-165`）。QSA 層の正規化・gate 呼び出しは例外を捕捉して層名付きのエラー文字列を返し、上位の層実行を失敗させます（`src/core/layer.cpp:1131-1141,1297-1301,1547-1549`）。このフラグ固有の成功時メッセージや終了コード変更は確認できません。

## 根拠

- `src/program/generate.cpp:448-450,849-859,2494-2497,3258-3268,3936-3941` — 既定値、usage、parser、`--native` との相互作用、setter 呼び出し。
- `src/core/layer.cpp:1131-1141,1294-1308` — QSA 層での正規化と出力ゲートの切替・例外処理。
- `src/core/verify.cpp:1559-1575,1902-1910` — batch verify 経路と native RoPE との条件付き融合。
- `src/kernels/cuda/native_qsa.cu:45-68,94-126,130-165`、`include/strata/kernels/native_qsa.hpp:5-33` — CUDA 演算、検査、helper 契約。
- `metal/src/engine/setup_host.cpp:53-55`、`metal/src/engine/stubs.cpp:275,279-281` — Metal 側の enable 状態と未実装 stub。
