# `--layer-split`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--layer-split` |
| 別名 | なし |
| 値 | `auto`、または GPU ごとの層数をカンマで区切った整数列（例: `24,18`） |

## 役割

複数GPUで Hy4 の expert をロードするとき、モデル層ごとの配置先GPUを指定します。`auto` は各GPUの expert 用 VRAM 容量を重みに42層を配分し、整数列はGPUの選択順に各GPUが担当する層数を指定します。これは `--gpus`（別名 `--devices`）で選択したGPUの expert 常駐配置に作用し、1 GPUだけの実行では有効になりません。

## 使い方

```sh
# 2 GPUへ42層を24層・18層に分けて配置し、モデルのロードまで確認する
strata-hy4 --model MODEL.strata --gpus 0,1 --layer-split 24,18 --load-only

# 選択GPUの容量に応じて層数を自動配分する
strata-hy4 --serve --model MODEL.strata --gpus 0,1 --layer-split auto
```

## 値と既定値

- `--layer-split` は値を1つ取ります。CLIで省略したときの初期値は環境変数 `HY4_LAYER_SPLIT` の値で、同変数も未設定なら空文字列です。コマンドラインで指定すると、その値で初期値を置き換えます。繰り返し指定した場合は引数走査中に後から代入された値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:362,375-383,405`）。
- 空文字列は無効値として扱われ、分割指定なしと同じです。
- `auto` は、GPUごとの expert 用 VRAM 容量 `vcap` を GiB 単位の重み（最低 `0.25`）にして42層を比例配分し、各GPUに最低1層を割り当てる方法です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:958-981`）。
- 手動指定は選択GPUの順に層数を並べ、読み取られた値の合計が42である必要があります。不足列または合計不一致では警告を出して指定を無視します。parser はGPU数分までしか値を読み取らないため、それより後ろに余分なカンマ区切り値があっても判定対象になりません。各数値は `atoi` で読み、負数は0に補正されます。したがって厳密な数値文法・桁全体の検査はなく、数値で始まる文字列の後続文字が検証されない場合があります（同ファイル `:982-996`）。

## 実行時の動作

選択GPUが2台以上で、指定値が空でないときだけ層分割を計算します。手動値または `auto` から連続する層範囲をGPUごとに作り、その層を担当するGPUのVRAMに余裕がある場合は、その層の expert を優先配置します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:954-1009,1012-1041`）。優先GPUに空きがない expert はその時点では割り当てられず、2回目の走査で残りの空き容量へ配置されます（同ファイル `:1045-1071`）。

通常実行では `GpuModel` に値を設定してモデルをロードし、`--serve` では `ServeOpts` に渡した後、serve 側で同じく `GpuModel` に設定してロードします。そのため、どちらの実行モードでもモデル読み込み時の配置に適用されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-577,649-659`; `engine/src/hy4flash/run/hy4_serve.hip.h:268-295`）。

有効な指定は標準エラーに `[load] --layer-split active across ...` とGPU別の層数・範囲を出力します。指定値が空の場合、またはGPUが1台だけの場合はこの分割処理に入りません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:958-959,998-1009`）。

## 適用条件と副作用

- CUDA/HIP 向け `strata-hy4` のオプションです。GPU数は `--gpus` / `--devices` から組み立てられ、2台以上を選択している必要があります。`--gpu` だけを指定した単一GPU実行では、値を受理しても分割指定は使われません（`engine/src/hy4flash/run/hy4_main.hip.cpp:401-405,514-543`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:958-959`）。
- GPUごとの層数は配置の優先先を決めます。優先先のVRAM不足時には残り expert が2回目の配置に回るため、層数が最終的なGPU別 expert 数やVRAM使用量を保証するものではありません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1012-1071`）。
- モデル読み込み時にGPUメモリへexpertを配置し、peer GPU がある場合はそれらのデバイスでもロード処理を行います（同ファイル `:1194-1215,1233-1249`）。

## 出力とエラー

- 値を省いて `--layer-split` を末尾に置くと、parser の `nxt()` が標準出力へ `ERR --layer-split needs a value` を出し、終了コード2で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,405`）。
- 手動値のGPU数または合計が不適合の場合、標準エラーへ `[load] --layer-split ... invalid for ... GPUs (must sum to 42); ignoring` を出し、オプション自体では終了しません。その後は通常の expert 配置経路になります（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:982-996,1012-1043`）。
- 不明な引数は標準エラーへ `unknown arg ...` を出し、終了コード2です（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:362,375-405` — 環境変数初期値、値取得、引数欠落時のエラー、CLI登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:514-543,555-577,649-659` — GPU選択と通常実行・serve実行への値の引き渡し。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:147-150,954-1009` — 42層のモデル状態、`auto` / 手動値の検査と層範囲作成。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1012-1071,1194-1215,1233-1249` — 層優先のexpert配置、残り配置、およびGPUへのロード。
- `engine/src/hy4flash/run/hy4_serve.hip.h:268-295` — serve 経路での `GpuModel` 設定とロード。

調査範囲は指定 commit の Strata ソースに限ります。実GPU上での最終配置や性能差はこの調査では実行・測定していません。
