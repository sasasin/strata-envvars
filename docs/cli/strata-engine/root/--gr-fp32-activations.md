# `strata generate --gr-fp32-activations`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--gr-fp32-activations` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

GR（gated residual / hyper-connection mixer）の activation を BF16 に丸める既定経路から、FP32 activation を使う実験経路へ切り替える。推論 engine の単体生成コマンドに対するオプトイン設定で、CUDA/HIP 系と SYCL 系の parser に同じフラグがある。parser の説明文は「experimental CUDA-oracle」としている。

## 使い方

```sh
# pack から生成する際、GR activation に FP32 経路を指定する
strata generate --pack /path/to/pack --gr-fp32-activations
```

## 値と既定値

値は不要で、指定時に `gr_fp32_activations` を `true` にする。未指定時は構造体の初期値 `false`。parser 側に範囲検証はなく、同じフラグを複数回書いても `true` のまま。値を続けて書く形式ではないため、たとえば `--gr-fp32-activations yes` の `yes` は次の引数として未知引数エラーになる。

## 実行時の動作

起動時に parser の bool を GR kernel のグローバル設定へ渡す。通常の GR 経路では、この設定が有効だと RMS norm 後の activation と down / gate / injection 計算が FP32 を使う分岐を選ぶ。未指定時かつ native MMVF も無効なら、norm 結果・down 中間値を BF16 に丸める経路を使う。CUDA 実装では `gr_norm_kernel<true>` と float 型の down/gate kernel を選び、無効時は `<false>` と BF16 型を選択する。SYCL 実装にも同じ `use_fp32` 分岐がある。

`--gr-native-mmvf` を併用すると `use_native` が真になり、FP32 activation はこのオプション単独の分岐より優先して native MMVF 経路で使われる。native MMVF は kernel 側でも FP32 activation を含意する（`use_fp32 = fp32_activations || use_native`）。engine は両フラグを session configuration fingerprint に含める。

## 適用条件と副作用

このフラグ自体に backend 条件や専用の補正・拒否分岐は見つからず、各 engine の GR kernel 選択へ渡される。通常経路では activation の丸めと計算経路が変わる実験設定である。`--gr-native-mmvf` 併用時は native 経路になり、native kernel は `hc*n_embd` と `hc_lr` が偶数であることを要求し、満たさなければ `std::invalid_argument` を送出する。これは native MMVF 側の条件であり、本オプション単独の validation ではない。

## 出力とエラー

フラグ単独では専用の stdout/stderr 出力やファイル副作用を行わない。値を誤って後置した場合など、未知引数は `stderr` に `unknown argument: <引数>` を出し、usage を表示して終了コード 2 を返す。GR kernel 起動・同期時のエラーは通常の kernel エラー経路（`gr_read launch: ...` / `gr_read: ...`、終了）に進み、フラグ専用のエラー処理はない。

## 根拠

- `engine/src/program/generate.cpp:778` — オプション状態の初期値は `false`。
- `engine/src/program/generate.cpp:1244` — usage 上の説明。
- `engine/src/program/generate.cpp:3912` — CUDA/HIP 系 parser が値なしで `true` を設定。
- `engine/src/program/generate.cpp:4271-4273` — 未知引数の stderr、usage、終了コード 2。
- `engine/src/program/generate.cpp:6104-6105` — parser 結果と native MMVF 設定を kernel 側へ渡す。
- `engine/src/program/generate.cpp:14024` — 両設定を session configuration fingerprint の switches に含める。
- `engine/src/kernels/cuda/gr.cu:349-350,410-444` — 設定 setter、native MMVF が FP32 を含意する条件、FP32/BF16 の kernel 分岐。
- `engine/src/kernels/cuda/gr.cu:415-416` — native MMVF の偶数形状条件。
- `engine/sycl/src/program/generate.cpp:462,832,1951,2217-2219,3219-3220,8203` — SYCL 系の初期値、usage、parser、未知引数エラー、kernel 設定、fingerprint。
- `engine/sycl/src/kernels/cuda/gr.dp.cpp:427,488-501,560-584,622-645` — SYCL kernel の setter、FP32/BF16 分岐と native MMVF の FP32 適用。
