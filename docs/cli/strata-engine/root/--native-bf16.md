# `--native-bf16`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--native-bf16` |
| 別名 | なし |
| 値 | 値を取らないフラグ |
| 既定値 | 無効 |

## 役割

CUDA の一部 BF16 重み射影で、入力活性を先に BF16 化する経路から、FP32 活性を直接受ける native CUDA GEMV 経路へ切り替えます。対象は SSM の alpha/beta 射影、MoE router 射影、QSA indexer の key/query 射影です。全 BF16 演算を一括で切り替える指定ではありません。ヘルプもこの範囲を SSM/router/indexer と説明しています（`src/program/generate.cpp:442-443, 844-845`）。

## 使い方

```sh
strata generate --pack ./model.pack --tokens "1,2,3" --native-bf16
```

この例の `--pack` と `--tokens` は `generate` の必須引数です（`src/program/generate.cpp:808-809, 3174-3179`）。

## 値と既定値

値は不要です。parser は指定されると内部の `native_bf16` を `true` にし、オプション構造体での初期値は `false` です。同じフラグを複数回指定しても同じ bool を再度 `true` にするだけで、重複指定エラーはありません（`src/program/generate.cpp:442, 2488-2489`）。専用の値 validation はありません。

## 実行時の動作

有効時、`layer_set_native_bf16` が射影ヘルパーの切替状態を設定します。helper は native 経路で `bf16_gemv_fp32_mmvf(x, weights, ...)` を呼び、無効時にはまず FP32 入力を BF16 に変換し、BF16 活性を使う split または通常 GEMV を呼びます（`src/program/generate.cpp:3932`; `src/core/layer.cpp:103-108, 202-203`）。native GEMV は FP32 入力と BF16 重みを読み、積和を行います（`src/kernels/cuda/native_bf16.cu:47-63`）。そのため通常経路と数値丸めの条件が異なります。

この helper は SSM の alpha/beta（`src/core/layer.cpp:325-334`）、router（同 `406-417`）、indexer key と query（同 `1181-1195, 1245-1249`）で使われます。バッチ verify の router 射影もこの設定を見て native 複数列 GEMV を使うか決めます（同 `446-465`）。

相互作用:

- `--native` プリセットは `--native-bf16` と [`--native-bf16-extra`](--native-bf16-extra.md) の両方を有効にします。プリセットの後段で両 bool が設定されます（`src/program/generate.cpp:3263-3267`）。
- `--native-bf16-extra` は別スイッチで、PLE value と shared expert scalar gate 用です。`--native-bf16` 単独ではそれらを切り替えません（`src/program/generate.cpp:443, 3932-3935`; `src/kernels/cuda/ple.cu:327-331`; `src/kernels/cuda/shared_expert.cu:248-260`）。
- この指定による標準入力、ファイル出力、ネットワークアクセスの追加は見つかりませんでした。推論時に選択される CUDA 射影 kernel と計算経路を変えます。

## 適用条件と副作用

対象処理は CUDA カーネル実装です。プロジェクトの CMake では `native_bf16.cu` が CUDA エンジンのソースとして登録されています（`CMakeLists.txt:395-399`）。この調査ではビルド構成別の配布バイナリを確認していないため、特定の配布物で当該経路が有効かは断定しません。

parser 上は他のオプションとの必須組み合わせやモデル別 validation はありません。indexer の射影重み自体は呼び出し側で engine form 1（BF16）か確認され、不一致なら `qsa_layer` が失敗します（`src/core/layer.cpp:1148`）。また native GEMV 関数は正の偶数 `n_in`、正の `n_out`、整数範囲、非 null かつ整列したポインタを要求します（`src/kernels/cuda/native_bf16.cu:340-349`）。

## 出力とエラー

フラグ固有の成功メッセージや出力ファイルはありません。未知の引数は stderr に `unknown argument` と usage を出して終了コード 2 になります（`src/program/generate.cpp:2787-2793`）。native GEMV の寸法・ポインタ条件違反は `std::invalid_argument`、CUDA kernel launch 失敗は `std::runtime_error` になります（`src/kernels/cuda/native_bf16.cu:342-366`）。それらの上位での表示形式・終了コードは呼出し文脈依存であり、このフラグ専用の CLI エラー経路としては確認できませんでした。

## 根拠

- `src/program/generate.cpp:442-443, 844-845` — 初期値とヘルプ上の用途。
- `src/program/generate.cpp:2488-2489, 3263-3267, 3932-3935` — parser、`--native` との相互作用、内部設定。
- `src/core/layer.cpp:103-108, 202-203, 325-334, 406-417, 1181-1195, 1245-1249` — 経路切替と対象射影。
- `src/kernels/cuda/native_bf16.cu:47-63, 340-366` — CUDA 計算と実行時 validation / launch error。
- `src/program/generate.cpp:2787-2793` — 未知引数の失敗経路。

調査は指定 revision のソースと索引に基づきます。同一 revision のビルド済み CLI help や Release artifact は利用せず、ソース内の usage と parser を照合しました。
