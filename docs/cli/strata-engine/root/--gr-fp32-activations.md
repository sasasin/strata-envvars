# `--gr-fp32-activations`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジンのトップレベル CLI） |
| オプション | `--gr-fp32-activations` |
| 別名 | なし |
| 値 | 値を取らないスイッチ |

## 役割

GR（gated residual / hyper-connection）の読み出し計算で、中間 activation を BF16 に丸めず FP32 のまま射影へ渡します。Strata の help は CUDA oracle 向けの実験オプションと説明しています。これは activation の精度経路を選ぶもので、単独では射影の reduction tree を変更しません（`src/program/generate.cpp:842`、`include/strata/kernels/gr.hpp:27-31`）。

## 使い方

通常の必須入力と併用します。たとえば pack と token ID を指定する場合:

```sh
strata generate --pack pack/full --tokens "1,2,3" --gr-fp32-activations
```

`strata generate` は `--tokens` または代替の `--tokens-file` を要求します（`src/program/generate.cpp:806-812`）。

## 値と既定値

- 既定値は無効（`false`）です。指定すると `true` になり、値を続けて渡す形式ではありません（`src/program/generate.cpp:440,2486`）。
- 数値や列挙値の validation はありません。重複指定も同じ bool を再度 `true` にするだけです。
- 余分な値を続けると、その値は次の引数として解釈され、未知の引数なら usage を表示して終了コード `2` になります（`src/program/generate.cpp:2787-2792`）。

## 実行時の動作

起動処理で `o.gr_fp32_activations` が GR kernel の設定関数に渡され、以後の GR 読み出しで参照されます（`src/program/generate.cpp:3922-3923`）。通常の CUDA 実装では `fp32_activations || native_mmvf` が FP32 経路を選び、無効時は BF16 経路を選びます。FP32 経路では正規化後の値 `xn` と down projection の `lo` を BF16 に丸めず使います（`src/kernels/cuda/gr.cu:410-443`、計算上の契約は `include/strata/kernels/gr.hpp:88-93`）。SYCL 側の生成実装にも同じスイッチ判定があります（`sycl/src/kernels/cuda/gr.dp.cpp:487-500`）。

設定は session 作成・graph capture より前に行う前提です。capture 済み graph は capture 時の kernel variant を保持するため、実行中に設定を変えても既存 graph の経路は変わりません（`include/strata/kernels/gr.hpp:27-30`）。このオプション自体が GR 読み出しに使われる一方、`gr_read` による output 側 GR 読み出しも同じ設定を参照します（`src/core/layer.cpp:1391-1394`）。

## 相互作用

- `--gr-native-mmvf` は別のスイッチで、FP32 activation を暗黙に有効にします。これに加えて pinned MMVF 射影、weighted FP32 RMSNorm、native combine/write arithmetic も選択するため、activation 精度だけを変える本オプションとは効果範囲が異なります（`src/program/generate.cpp:843,2487`、`include/strata/kernels/gr.hpp:33-38`、`src/kernels/cuda/gr.cu:411-423`）。
- `--native SHARD1` を受理して前提検査を通ると、エンジンが `gr_native_mmvf = true` を設定します。そのためこの場合も FP32 activation 経路になります（`src/program/generate.cpp:3232-3265`）。
- session 設定 fingerprint に `gr_fp32_activations` と `gr_native_mmvf` の両方が含まれます（`src/program/generate.cpp:9450-9462`）。

## 適用条件と副作用

GR GPU kernel の FP32 activation 経路を選ぶ設定です。help と実装コメントは CUDA oracle を対象としており、CUDA 実装と SYCL 生成実装を確認しました。全 backend・全モデル形状での数値的一致や速度向上は、このソース調査だけでは確認できません。性能測定は行っていません。

このフラグ単独によるファイル・ネットワーク操作や専用の stdout/stderr 出力はありません。設定は process 内の kernel 選択状態に作用します。`--gr-native-mmvf` 併用時にはそちら固有の形状条件（`hc*n_embd` と `hc_lr` が偶数）があり、違反時は `gr_read` が `std::invalid_argument` を送出します。この条件は `--gr-fp32-activations` 単独には適用されません（`src/kernels/cuda/gr.cu:414-416`、`include/strata/kernels/gr.hpp:33-38`）。

## 出力とエラー

本オプション自身の値に対する拒否・警告・専用エラー経路はありません。未知の引数は `stderr` に `unknown argument: ...` と usage を出して終了コード `2` です（`src/program/generate.cpp:2787-2792`）。FP32 kernel の launch または同期エラーが発生した場合、GR 実装は `gr_read launch: ...` または `gr_read: ...` を `stderr` に出し、終了します（`src/kernels/cuda/gr.cu:452-462`）。これは一般の GR 実行失敗経路であり、このフラグ専用の validation ではありません。

## 根拠

- parser の既定値・受理: `src/program/generate.cpp:440,842,2486`
- FP32/BF16 の実際の分岐と適用条件: `src/kernels/cuda/gr.cu:410-443`、`include/strata/kernels/gr.hpp:27-38,88-93`
- SYCL 側の同等分岐: `sycl/src/kernels/cuda/gr.dp.cpp:487-500`
- 起動時設定・native preset の相互作用・session fingerprint: `src/program/generate.cpp:3922-3931,3232-3265,9450-9462`
- parser エラーと GR kernel の失敗出力: `src/program/generate.cpp:2787-2792`、`src/kernels/cuda/gr.cu:452-462`
