# `HY4_VIT_CPU`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`engine/src/hy4flash/run/hy4_vision.hip.h` の `VisionEncoder::load` で、Hy4-Flash の画像 ViT shard の重みを GPU メモリではなくホストメモリに読み込む経路を選ぶ。これにより画像エンコードは `encode_cpu` に進む。対象はこの HIP/CUDA 系 GPU 実装であり、Metal と SYCL の画像実装ではこの名前の読み取りを確認できなかった。テキストのみの実行では Vision shard をロードしないため、この設定の効果はない（`hy4_vision.hip.h:604-629, 888-894`; serve の画像要求経路は `hy4_serve.hip.h:389-436`）。

## 値と判定

実装は `getenv("HY4_VIT_CPU")` が null でないことに加え、`atoi` の戻り値が 0 でないことを条件にする。文字列全体の検証はしない。`atoi` は先頭の空白と符号を許し、先頭の10進整数部分を変換して後続の非数字を無視するため、空文字や数字で始まらない値は 0、`1tail` は 1、`0tail` は 0 と判定される。大文字小文字比較や true/false の解釈はない。範囲検査もないため、整数オーバーフロー値の扱いはこのコードから保証できない（`hy4_vision.hip.h:614-616`）。

| 条件 | 未設定 | CPU 強制になる値 | CPU 強制にならない値 |
|---|---|---|---|
| HIP/CUDA 系 `VisionEncoder::load` | 環境変数による強制なし | `1`, `-1`, ` 2`, `1tail` など `atoi` が非0 | 空文字、`0`, `0tail`, `true`, `false`, `x1` など `atoi` が0 |

「CPU 強制にならない」は GPU 利用を保証しない。低 VRAM 判定、または `hipMalloc` 失敗でも CPU 読み込みに切り替わる。内部から `load(..., true)` を呼ぶ場合も CPU が選択される（`hy4_vision.hip.h:615-626, 913-923`）。

## 有効になる条件

- Vision shard を使う画像処理で `VisionEncoder::load` が呼ばれること。serve は起動時に shard を probe するだけで、最初の画像要求で load する。オフライン画像実行も画像レコードがある場合に load する（`hy4_serve.hip.h:355-364, 389-436`; `hy4_main.hip.cpp:718-729`）。
- この変数は `engine/src/hy4flash/run/hy4_vision.hip.h` にある HIP/CUDA 系のロード判定にだけ現れる。コード上、Metal (`engine/src/hy4flash/metal/hy4_metal_vision.h`) と SYCL (`engine/src/hy4flash/sycl/sy_vision.h`) の同名環境変数読み取りは確認できず、そちらへの効果は確認できない。
- `--vision` は shard のパスを指定する引数であり、CPU/GPU 選択を上書きする処理はこの load 呼び出し経路にはない（`hy4_main.hip.cpp:448`; `hy4_serve.hip.h:431-436`）。
- `HY4_VIT_CPU` が未設定または `atoi` 結果 0 でも、GPU 総メモリが 6500 MiB 未満（総量が取得できた場合）、または空き VRAM が shard 用のページ丸め後サイズ + 384 MiB 未満（空き量が取得できた場合）なら CPU を使う。いずれにも該当せず CPU 強制もなければ GPU shard 割り当てを試み、`hipMalloc` が失敗した場合も CPU に切り替える（`hy4_vision.hip.h:611-626`）。

## 実行時の詳細

判定は `VisionEncoder::load` の呼び出しごとに行う。ただし shard がすでにロード済みなら、`force_cpu` が false の通常呼び出しは先に成功を返すため、環境変数を再評価しない（`hy4_vision.hip.h:604-616`）。オフライン画像実行では encoder を作って画像処理時に一度 load する（`hy4_main.hip.cpp:718-729`）。serve は encoder を保持し、各画像要求で load を呼ぶ。CPU モードなら画像エンコード後に unload するので次の画像要求で再ロード・再評価する。一方、CPU モードでなく、総 VRAM が 15 GiB 以上かつ空きが 4 GiB 以上なら unload 条件に当たらずロード状態を保つため、後続要求では環境変数を読み直さない（`hy4_serve.hip.h:357-358, 431-450`）。実行中に環境を変更した場合も、この再ロード条件を満たすまで反映されない。

CPU を選ぶと shard の重みをホスト側 `h_w` に読み込み、`cpu_mode` を立てる。`encode` はこのフラグを見て CPU encoder に処理を渡す。画像行の出力先は引き続き GPU 側の `rows_out` である（`hy4_vision.hip.h:624-629, 659-665, 888-894`）。この変数はモデル選択や画像の有無を変えず、画像エンコード時の重み配置と実行経路を選ぶ。

## ログと測定値

CPU load が成功すると stderr に `[vision] shard loaded on CPU (low-VRAM fallback): ...` が出る。この文言は `HY4_VIT_CPU` による強制選択でも同じで、低 VRAM が原因だったことを示すとは限らない。GPU load の場合は `[vision] shard loaded to the GPU: ... (wmma|fdot2|plain)` が出る。serve は画像エンコード後に別途 `[vision] ... (CPU)` を CPU モード時に出す。オフライン実行の成功ログには CPU/GPU の区別は付かない（`hy4_vision.hip.h:624-629, 646-648`; `hy4_serve.hip.h:445`）。

この変数について、ソース資料に条件付きで示された測定値は確認できなかった。

## 根拠

- `engine/src/hy4flash/run/hy4_vision.hip.h:604-648` — 環境値の判定、VRAM 条件、CPU/GPU load とログ。
- `engine/src/hy4flash/run/hy4_vision.hip.h:659-665, 888-923` — CPU encode 分岐と GPU workspace OOM 時の CPU fallback。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:448-450, 718-729` — `--vision` / `--image` とオフライン画像時の load。
- `engine/src/hy4flash/run/hy4_serve.hip.h:355-370, 431-450` — serve の probe、画像要求時 load、保持・解放とログ。
- `engine/src/hy4flash/metal/hy4_metal_vision.h:110-135, 149-151`; `engine/src/hy4flash/sycl/sy_vision.h:358-390` — 別 backend の Vision 実装。これらでは `HY4_VIT_CPU` の読み取りを確認できなかった。
