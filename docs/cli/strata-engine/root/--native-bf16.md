# `--native-bf16`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--native-bf16` |
| 別名 | なし |
| 値 | 値なしの真偽フラグ。指定すると有効 |

## 役割

BF16 重みを使う SSM gate、MoE router、QSA indexer の投影で、活性値を事前に BF16 へ丸める従来経路から、FP32 活性値を受け取る native BF16 GEMV 経路へ切り替えます。実験用の CUDA-oracle 系オプションとして説明されています。parser の既定値は無効です（`engine/src/program/generate.cpp:780,1246`）。

## 使い方

```sh
strata generate --pack <pack-dir> --tokens "1,2,3" --native-bf16
```

`--pack` と `--tokens` は generate の必須入力です。例の位置引数は説明用です（`engine/src/program/generate.cpp:1210-1214,3850-3855,5002-5007`）。

## 値と既定値

- 値を取りません。parser は引数が `--native-bf16` と一致した場合に bool を `true` にします。値の範囲や数値 validation はありません（`engine/src/program/generate.cpp:3914`）。
- 省略時は `false`。同じフラグを複数回指定しても `true` を再設定するだけです（`engine/src/program/generate.cpp:780,3914`）。
- `--native-bf16=<値>` の形式は登録されていません。未知の引数は stderr に `unknown argument: ...` と usage を出し、終了コード 2 で失敗します（`engine/src/program/generate.cpp:4268-4273`）。

## 実行時の動作

parser が受理した値は起動時に `layer_set_native_bf16` へ渡されます。`project_bf16` は有効時に `bf16_gemv_fp32_mmvf` を呼び、無効時は BF16 化済み活性値を使う既存 GEMV 経路を選びます（`engine/src/program/generate.cpp:6114`; `engine/src/core/layer.cpp:100-108,202`）。具体的には SSM の alpha/beta gate（同 `:313-330`）、MoE router（同 `:405-417`）、QSA indexer の key/query projection（同 `:1204-1217,1268-1272`）で使われます。通常経路ではこれらの投影に備えた FP32→BF16 活性値変換を省く箇所があります（同 `:325-327,401-407,1181-1187`）。

このフラグは `--native-bf16-extra` とは独立です。後者は PLE value と shared expert scalar gate に渡されます（`engine/src/program/generate.cpp:781,6116-6117`; `engine/src/kernels/cuda/ple.cu:327-335`; `engine/src/kernels/cuda/shared_expert.cu:264-277`）。一方、`--native` の native preset 経路では `native_bf16` と `native_bf16_extra` の両方を有効にします（`engine/src/program/generate.cpp:5160-5164`）。

## 適用条件と副作用

- このフラグ自体にデバイス・モデル形状の validation や fallback 分岐はありません。各対象 projection が実行されると切替が使われます。実装は CUDA native BF16 kernel を用い、SYCL 側 parser も同じフラグを bool にして同じ設定 API に渡します（`engine/src/program/generate.cpp:3914,6114`; `engine/sycl/src/program/generate.cpp:1953,3229`; `engine/src/kernels/cuda/native_bf16.cu:478-504`）。利用可能な build/backend の組み合わせはこの引数処理だけからは確定できません。
- MoE の複数 token router はこの設定を使って batch 経路を選びますが、`STRATA_ROUTE_PER_TOKEN` が設定されている場合は per-token 経路に戻ります。native router が有効で expert 数 512、`k=10` の場合も batch 条件から除外されます（`engine/src/core/layer.cpp:446-465`）。
- このフラグは計算経路を変更します。ソースから速度や出力差の定量値は確認できないため、性能効果は断定しません。

## 出力とエラー

オプション受理時に専用メッセージはありません。native GEMV は `n_in` が正の偶数であること、`n_out` が正で `INT_MAX` 以下であること、各ポインターの非 null・alignment 条件を確認し、違反時に `std::invalid_argument` を投げます。CUDA kernel launch エラーも `std::runtime_error` になります（`engine/src/kernels/cuda/native_bf16.cu:478-504`）。この native GEMV 例外が最終的に CLI のどの終了コードや標準出力・標準エラーへ変換されるかは、ここで追跡した呼び出し範囲からは確定できません。このオプション専用の警告経路も確認できません。

## 根拠

- `engine/src/program/generate.cpp:780,1246,3914` — 既定値、help 表示、parser 登録。
- `engine/src/program/generate.cpp:5160-5164,6114-6117` — `--native` preset による有効化と実行時設定の反映。
- `engine/src/core/layer.cpp:100-108,313-330,405-417,1204-1217,1268-1272` — 投影切替と SSM/router/indexer の使用箇所。
- `engine/src/kernels/cuda/native_bf16.cu:478-504` — native GEMV の入力条件と launch error。
- `engine/sycl/src/program/generate.cpp:1953,3229` — SYCL parser と設定反映。
