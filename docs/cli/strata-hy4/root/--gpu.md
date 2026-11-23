# `strata-hy4 --gpu`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | `atoi` で整数に変換される GPU ordinal |

## 役割

CUDA/HIP 版 `strata-hy4` が使う主 GPU の ordinal を指定します。選ばれた ordinal は、device 選択、GPU 情報取得、モデル実行に使われます。未指定時の主 GPU は ordinal `0` です。`--gpus` または `HY4_GPUS` で GPU 群が指定される場合は、そちらの先頭 ID が主 GPU になり、このオプションの値より優先されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:360-362,515-543`）。

この文書のスコープは索引 `docs/cli/README.md` の `strata-hy4` CUDA/HIP root parser です。同じ表記の `--gpu` を持つ Metal 版と SYCL 版は別 parser で、値の扱いも異なるため対象外です。

## 使い方

```sh
# ordinal 1 を主 GPU にしてオフライン実行
strata-hy4 --model MODEL.strata --gpu 1 --tokens tokens.txt

# serve モードでも主 GPU を指定
strata-hy4 --serve --model MODEL.strata --gpu 1
```

## 値と既定値

- `--gpu` は値を1つ取り、`atoi` で `int` に変換します。Strata 側で数値全体の検証や GPU ordinal の範囲検証は行いません。したがって、不正な文字列を明示的に拒否する処理はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,401-404`）。
- 同じ `--gpu` を複数回指定した場合は、引数走査中に `gpu` へ順次代入するため最後の値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,403-404`）。
- 未指定時は `gpu = -1`、`primary_gpu = 0` です。`--gpu` に負数を指定しても `primary_gpu` は `0` にフォールバックし、負数の device ordinal は選択されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:360,515`）。
- 値の範囲は実行時の CUDA/HIP runtime が受理する device ordinal に依存します。ソースには事前の範囲確認がありません。

## 実行時の動作

初期化後、`--gpu N` は `gpu = atoi(N)` に格納されます。`HY4_GPUS` が設定されている場合、その値が `gpus_csv` の初期値になり、CLI の `--gpus` / `--devices` があればさらに置き換えます。`gpus_csv` が空でなければ、その指定から `primary_gpu` を設定して `gpu` にも代入するため、`--gpus`（または [`HY4_GPUS`](../../../envvars/HY4_GPUS.md)）が `--gpu` より優先されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:360-362,401-405,515-541`）。

選択された `gpu >= 0` に対して `hipSetDevice(gpu)` を呼びます。続いて通常実行では `primary_gpu` を `hipGetDeviceProperties` に渡し、GPU 名・アーキテクチャ・空き容量を標準エラーへ出力します。`--serve` の場合も `primary_gpu` を serve 設定へ渡し、serve 側で GPU 情報取得とモデルの主 GPU として使用します（`engine/src/hy4flash/run/hy4_main.hip.cpp:543-544,570-575,617-621`、`engine/src/hy4flash/run/hy4_serve.hip.h:262-274`）。

## 適用条件と副作用

- 対象は CMake の `strata-hy4` CUDA または HIP build です。CMake は CUDA/HIP のいずれかが有効であることを要求し、同じ実装を選択した backend でコンパイルします（`engine/CMakeLists.txt:846-852,884-908`）。
- 負数、未指定では `hipSetDevice` を呼ばず、主 GPU ordinal `0` を使います。非負の値はそのまま runtime に渡され、選択に失敗すれば後述の HCK エラー経路に入ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:515-543,617-618`）。
- `--gpus` / `HY4_GPUS` は複数 GPU の peer device 構成にも使われます。値が非空なら先頭 ID が主 GPU となるため、単一 GPU を選びたい用途ではこれらの指定も確認してください（`engine/src/hy4flash/run/hy4_main.hip.cpp:361-362,516-541`）。
- `--info FILE` を指定すると、引数の解析後に GPU 選択より先に情報表示して終了します。その呼び出しでは `--gpu` が処理へ反映されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:389-391,507`）。
- GPU 選択後に GPU 情報を照会し、その後モデルのロード・実行を行います。`--gpu` 自体がファイルを書き換える処理は確認できません（`engine/src/hy4flash/run/hy4_main.hip.cpp:617-659`）。

## 出力とエラー

- 値が欠けると `ERR --gpu needs a value` を標準出力へ出し、終了コード `2` で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382`）。
- 不正または利用できない ordinal によって `hipSetDevice` / `hipGetDeviceProperties` が失敗した場合、HCK macro は `HIP error <code> (<message>) at <file>:<line>` を標準エラーへ出し、終了コード `3` で終了します。CUDA build でもこの共通 macro の文言は `HIP error` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:543,618`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:360-362,375-405` — `gpu` の初期値、環境変数の初期値、引数値の取得と整数変換。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:515-543` — 既定 ordinal、`--gpus` による上書き、device 選択。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:570-575,617-659` — serve への ordinal 引き渡しと通常実行時の GPU 照会・モデルロード。
- `engine/src/hy4flash/run/hy4_serve.hip.h:262-274` — serve 経路で主 GPU を照会しモデルへ設定。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — CUDA/HIP runtime error の出力と終了コード。
- `engine/CMakeLists.txt:846-852,884-908` — CUDA/HIP 版 `strata-hy4` の build 条件。
