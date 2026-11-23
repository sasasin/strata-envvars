# `--gpu`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU ordinal を表す整数。既定値は `0` |

## 役割

CUDA/HIP 共通の Inkling CLI で使用する GPU ordinal を指定します。値は backend の初期化設定に入り、CUDA/HIP のデバイス選択に使われます。`--cpu` を指定すると CPU backend が選ばれるため、この値は GPU 選択に使われません。

## 使い方

```sh
# GPU ordinal 1 を使ってモデルを直接実行する
strata-inkling --native model.strata --gpu 1

# GPU ordinal 1 を使って serve モードで起動する
strata-inkling --serve --native model.strata --gpu 1
```

## 値と既定値

- 値は `std::atoi` で整数に変換されます。整数としての形式・非負範囲・デバイス数との整合性を parser は検証しません。数値に変換できない文字列は `atoi` の結果 `0` になります（`engine/src/inkling2/ink_main.cpp:443-444`）。
- 値を省略すると、共通 backend 設定の `gpu_index` 初期値 `0` が使われます（`engine/src/inkling2/ink_backend.h:17-24`）。値が不足した場合は `missing value after --gpu` を stderr に出して終了コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:380-383`）。
- 同じオプションを複数回指定したときは、引数を順に処理するため、最後に指定した整数が `gpu_index` に残ります（`engine/src/inkling2/ink_main.cpp:379-385,443-444`）。

## 実行時の動作

`--gpu N` は `BackendOpts.gpu_index` を設定します。通常の生成、serve、benchmark、selfcheck（モデル指定時）、KLD 評価、reference dump はこの設定を持つ backend を選択・初期化します。`--info` と tokenizer export は backend 初期化より先に処理されるため、これらのモードでは GPU ordinal を選ぶ処理に到達しません（`engine/src/inkling2/ink_main.cpp:544-568`）。

CUDA backend は、指定値が可視 device 数の範囲内ならその ordinal を主 GPU とし、範囲外（負値を含む）なら `0` に置き換えます。その後 `cudaSetDevice` を呼び、失敗時は初期化エラーにします。`--gpus` 等で複数 GPU を指定した場合も `--gpu` の値が主 GPU の候補です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:104-136`）。HIP backend も `gpu_index`（明示 GPU ID があればその先頭）を主 GPU 候補として使い、可視 device 範囲に clamp してから `hipSetDevice` を呼びます（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-583`）。

backend の選択はビルド条件に依存します。`--cpu` がない場合は有効な CUDA、EP-CUDA、HIP、Metal、SYCL backend のうちビルド時に選ばれた実装を使い、`--cpu` がある場合は CPU backend を使います（`engine/src/inkling2/ink_backend.h:150-168`）。この文書の parser は CUDA/HIP 共通の `ink_main.cpp` を対象にしています。Metal と SYCL の専用実行ファイルは別 parser scope です（索引 `docs/cli/README.md:1549-1592`）。

## 適用条件と副作用

- `--gpu` は parser に受理されるだけで、`--cpu` を付けた実行では GPU backend が選ばれません（`engine/src/inkling2/ink_main.cpp:476-477`; `engine/src/inkling2/ink_backend.h:150-168`）。
- `--gpus` / `--devices` と組み合わせる場合、数値形式の `--gpus N` は GPU 数のみを更新します。CSV 形式または `--devices` は GPU ID リストを作り、その先頭 ID で `gpu_index` を上書きします。明示 ID リストがある場合、CUDA/HIP backend はその先頭 ID を主 GPU に使うため、`--gpu` の値より ID リストが優先されます（`engine/src/inkling2/ink_main.cpp:443-469`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:112-131`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:575-576`）。
- `IK2_GPUS` は、CLI 処理後に GPU 数が 1 かつ ID リストが空の場合に読み込まれます。単一数値なら GPU 数を変更し、CSV なら GPU ID リストと先頭 GPU を設定します。この条件では `--gpu` の値が既定値 `0` のままか、明示的に指定されたかを区別しないため、環境変数側の CSV 指定が主 GPU を上書きする場合があります（`engine/src/inkling2/ink_main.cpp:505-533`）。
- CUDA/HIP backend がない環境、可視 GPU がない環境、またはデバイス選択 API が失敗する環境では初期化が失敗します。モデル実行経路では `init: <理由>`（serve では protocol の `ERR init`）を出して終了コード `1` になります（`engine/src/inkling2/ink_main.cpp:564-568`）。GPU の割当・計算を伴う副作用は backend 初期化後に生じます。

## 出力とエラー

`--gpu` の値自体に対する範囲エラーや警告は parser からは出ません。CUDA は範囲外値を ordinal `0` に置き換え、HIP は可視範囲に clamp します。実際に選択された backend の device 初期化が失敗した場合、通常実行では stderr に `init: ...`、serve では `ERR init: ...` を出し、終了コード `1` になります。値を省略した場合の parser 終了コードは `2` です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:107-136`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-583`; `engine/src/inkling2/ink_main.cpp:380-383,564-568`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-385,443-444` — CLI 引数の走査、値の取得、`atoi` による `gpu_index` 設定、値不足時のエラー。
- `engine/src/inkling2/ink_backend.h:17-24,150-168` — GPU ordinal の既定値と `--cpu` を含む backend 選択。
- `engine/src/inkling2/ink_main.cpp:505-533` — `IK2_GPUS` の適用条件と CLI 設定との相互作用。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:104-136` — CUDA の ordinal 解決、`cudaSetDevice` と失敗経路。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-583` — HIP の ordinal 解決、範囲補正と `hipSetDevice`。
- `engine/src/inkling2/ink_main.cpp:544-568` — 先行モード分岐、backend 初期化とエラー出力。
