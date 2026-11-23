# `strata-inkling --gpus`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--gpus` |
| 別名 | `--devices` |
| 値 | GPU 数、またはカンマ区切りの GPU ordinal。`--devices` は ordinal のリストとして解釈 |

## 役割

CUDA/HIP ビルドの Inkling エンジンで使う GPU 数、または使用 GPU ordinal のリストを指定します。複数 GPU を選ぶと、backend が対応する複数 GPU 推論経路を初期化します。CUDA backend は Dual-GPU Expert Parallelism または Pipeline Layer-Split を選択し、HIP backend は最大 2 GPU の Expert Parallelism を設定します。実際に利用できる数や経路は backend と可視デバイスに依存します（`engine/src/inkling2/ink_backend.h:150-168`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:104-131`、`engine/src/inkling2/cuda/ink_runner.cuh:835-885`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-615`）。

## 使い方

```sh
# GPU 0 と GPU 1 を指定してサーバーを起動
strata-inkling --serve --native /path/to/model.strata --gpus 0,1

# GPU 0 を先頭に、見つかった最大 2 台を使う（backend の対応範囲内）
strata-inkling --bench --native /path/to/model.strata --gpus 2
```

## 値と既定値

- 値は必須です。値を省略すると `missing value after --gpus` を標準エラーへ出し、終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:379-384`）。
- 既定値は GPU 数 `1`、GPU ordinal `0`、明示 ordinal リストなしです（`engine/src/inkling2/ink_backend.h:17-25`）。
- `--gpus N` は `atoi` で整数化し、1 未満は 1 に補正します。上限値の入力検証は parser にはありません。数値でない値も `atoi` の結果に従い、通常は 1 に補正されます（`engine/src/inkling2/ink_main.cpp:445-469`）。
- `--gpus 0,2` のようにカンマを含む値は ordinal のリストとして解析されます。空要素は飛ばし、各要素を `atoi` で変換し、負数と重複を除外します。`--devices` はカンマの有無にかかわらず常にリストとして解析されるため、`--devices 2` は「GPU ordinal 2」であり「2 台」ではありません（同:445-468）。
- 無効な文字列の厳密な検証はありません。たとえば数値に変換できないリスト要素は `atoi` により 0 になり、ordinal 0 として扱われ得ます。空リストになった場合は GPU 数 1 になります（同:447-468）。
- 同じオプションを複数回指定すると、後の指定が `gpu_ids` と `gpus` を置き換えます。`--gpu N` は別途 primary ordinal を設定しますが、明示的な ordinal リストがある場合は CUDA/HIP backend がそのリストの先頭有効 GPU を primary に使います（同:443-468、`engine/src/inkling2/cuda/ink_cuda_backend.cu:112-131`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:575-580`）。

## 実行時の動作

parser は `--gpus` の値を `BackendOpts.gpus` または `BackendOpts.gpu_ids` に格納します。明示リストでは先頭の非負 ordinal を `gpu_index` にも設定します（`engine/src/inkling2/ink_main.cpp:443-469`、`engine/src/inkling2/ink_backend.h:17-25`）。この設定は `--serve`、`--bench`、`--selfcheck`、KLD 評価、通常の生成など、backend を初期化する実行経路に渡されます（同:545-569、`engine/src/inkling2/ink_main.cpp:101-143`）。`--cpu` が指定されると既定 backend は CPU backend に切り替わるため、GPU 数の指定で GPU backend を強制することはできません（`engine/src/inkling2/ink_backend.h:150-168`）。

`IK2_GPUS` 環境変数は、CLI 解析後に `gpus == 1` かつ明示 ordinal リストが空の場合に読み込まれます。この条件では `--gpu` や `--gpus 1` だけを指定していても環境変数が適用され得ます。環境変数もカンマ区切りなら ordinal リスト、それ以外なら GPU 数として解釈されます（`engine/src/inkling2/ink_main.cpp:505-533`）。

CUDA backend は明示 ordinal リストから、可視範囲内の重複しない GPU を最大 4 台選びます。リスト指定がない場合、`--gpu` の primary を先頭に、要求数・可視数の小さい方（最大 4 台）まで ordinal 順で追加します。指定した台数を超える GPU が見えない場合も、parser では拒否せず可視 GPU 数に合わせます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:104-131`）。複数 GPU 時の方式は、GPU 数、architecture/VRAM 差、OS、P2P 可否、および `--layer-split` に応じて CUDA runner が選びます（`engine/src/inkling2/cuda/ink_runner.cuh:835-885`）。

HIP backend は primary ordinal を可視範囲に clamp し、複数 GPU 要求かつ 2 台以上が見える場合に 2 台目を選びます。ordinal リストがあればそこから primary と異なる有効 ordinal を探し、なければ ordinal 0 または 1 を補助 GPU として使います。3 台以上を明示しても HIP 実装ではこの初期化経路が扱うのは 2 台までです（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-615`）。

## 適用条件と副作用

- GPU を使う backend の選択はビルド条件に依存します。通常の優先順は CUDA、EP CUDA、HIP、Metal、SYCL で、`--cpu` は CPU backend を選択します。GPU が可視でない場合、CUDA/HIP backend の初期化は失敗します（`engine/src/inkling2/ink_backend.h:150-168`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:104-110`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-573`）。
- backend は選択 GPU の device/context、stream 等を初期化し、モデル読み込みに GPU 群を渡します。GPU ordinal がデバイス数を超えた場合の扱いは backend ごとに異なります（CUDA は有効リストを絞り、HIP は primary を clamp）ので、無効 ordinal が一律にエラーになるとは限りません（`engine/src/inkling2/cuda/ink_cuda_backend.cu:112-139`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-624`）。
- 複数 GPU の分割・転送方式や性能は GPU 間接続等に左右されます。このオプション単独で特定の分割方式や性能向上を保証するものではありません（`engine/src/inkling2/cuda/ink_runner.cuh:835-885`）。

## 出力とエラー

- 値の省略は `missing value after --gpus` を標準エラーに出して終了コード 2 です（`engine/src/inkling2/ink_main.cpp:379-384`）。
- GPU が見つからない場合、CUDA backend は `cudaGetDeviceCount failed: ...`、HIP backend は `[ink-hip] no HIP devices visible` を初期化エラーとして返します。通常実行経路は `init: ...` を標準エラーに出して終了コード 1 で終了します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:106-110`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-573`、`engine/src/inkling2/ink_main.cpp:564-569`）。
- ordinal の数値形式・範囲を CLI parser が検証して専用エラーを出す処理は確認できません。実デバイスに対する選別・clamp は各 backend の初期化時に行われます。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-384,443-469` — 値の取得、別名、リスト/数値分岐、変換、補正、欠落値エラー。
- `engine/src/inkling2/ink_main.cpp:505-533` — `IK2_GPUS` の適用条件と環境変数の解析。
- `engine/src/inkling2/ink_backend.h:17-25,150-168` — backend option の既定値と backend 選択順。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:104-139` — CUDA 可視 GPU の選択と初期化失敗。
- `engine/src/inkling2/cuda/ink_runner.cuh:835-885` — 複数 GPU の EP / Layer-Split 選択条件。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:570-624` — HIP 可視 GPU、primary/peer ordinal の選択と初期化。
- `engine/src/inkling2/ink_main.cpp:564-569` — backend 初期化失敗時の出力と終了コード。
