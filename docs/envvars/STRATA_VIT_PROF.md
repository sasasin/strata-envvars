# `STRATA_VIT_PROF`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata が実装する `own` Vision reader の処理時間と、GPU reader の起動 retry を診断出力するスイッチ。画像の読み込み・前処理時間と、CPU/CUDA/HIP/Metal/SYCL encoder の各段階の時間、条件を満たす場合の GPU context / reader 起動 retry 数を出す。計算方式や token 選択を切り替える変数ではない。`own` reader を選ばない場合、encoder 段階の `vit-prof N=...` / `vit-cpu-prof ...` は出ない。主要な実装は `tools/vision/own/own_reader.cpp`、`tools/vision/own/vit_cpu.cpp`、`tools/vision/own/vit_gpu.cu`、`tools/vision/own/vit_metal.mm`、`tools/vision/own/vit_sycl.cpp`、および server の reader 起動処理 `serve/server.py` にある（例: `tools/vision/strata_vision.cpp:137-143,161-175`）。

## 値と判定

値の文字列を数値や真偽値に parse する箇所はない。C++ reader の判定は `getenv(...) != nullptr` またはポインタの真偽で、変数が存在すれば空文字を含め有効。Python server の判定は `bool(os.environ.get(...))` なので空文字は無効、空でない文字列は有効。したがって `0`、`false`、大文字小文字、前後の空白はいずれも文字列のまま扱われ、`0` や `false` も有効である。数値範囲・境界値はない。C++ の reader 起動 retry 表示も設定値の有無だけを見る（`tools/vision/own/own_reader.cpp:192-193`、`tools/vision/own/vit_cpu.cpp:204-205`、`tools/vision/own/vit_gpu.cu:839-840,1028-1029`、`tools/vision/own/vit_metal.mm:495-496`、`tools/vision/own/vit_sycl.cpp:499`、`serve/server.py:3291-3308`）。

| 読み取り経路 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| C++ own reader（画像前処理、encoder stage、CUDA context retry） | 無効 | 設定された任意の値。例: `1`、`0`、`false`、空文字 | なし（環境変数が存在する限り有効） |
| Python server の GPU reader 起動 retry 診断 | 無効 | 空でない任意の値。例: `1`、`0`、`false`、` true ` | unset、空文字 |

## 有効になる条件

- `tools/vision/strata_vision.cpp` が `--tower own` を実行するか、`--tower auto` で own reader を選ぶ必要がある。auto が `mtmd` を選んだ場合、または own reader の起動失敗後に mtmd reader へ切り替わった場合、own encoder の stage 計測は行われない（`tools/vision/strata_vision.cpp:137-143,161-175`）。
- CPU stage 計測は `vit_cpu.cpp` が組み込まれた own CPU reader の `VitCpu::encode` で有効。CPU 読み取り時に `STRATA_VIT_CPU=ref` で `VitRef` が選ばれた場合、この stage 計測コードを通らない（`tools/vision/own/own_reader.cpp:128-149`）。
- GPU stage 計測は build に含まれる backend に限る。CMake では CUDA/HIP は `vit_gpu.cu`、SYCL は `vit_sycl.cpp`、Metal は `vit_metal.mm` を個別条件で追加し、それぞれの build macro を設定する（`tools/vision/own/CMakeLists.txt:120-164`）。Metal は macOS 用の設定。該当 backend を含まない build ではその計測経路は存在しない。
- stage 計測の行は encode が成功し、各実装の末尾まで達したときに出る。CUDA/HIP の計測中は各 stage で `cudaDeviceSynchronize()`、Metal は `m.finish()`、SYCL は `q.wait()` を実行するため、計測を有効にすると計測区間ごとに同期を伴う（`tools/vision/own/vit_gpu.cu:1033-1038,1147-1159`、`tools/vision/own/vit_metal.mm:500-505,605-618`、`tools/vision/own/vit_sycl.cpp:503-508,591-599`）。CPU は stage の計測値を集計する（`tools/vision/own/vit_cpu.cpp:204-214,397-402`）。
- server の起動 retry 行は GPU reader の起動が一度以上失敗して retry し、最終的に起動した場合、または retry 上限・条件を満たさず起動失敗を返す場合に限る。Strata の server 側 retry は Linux Arm の NVIDIA reader に限られ、`ggml_cuda_init` / `cudaSetDevice` 等に関係する out-of-memory 起動失敗で、最大 12 回かつ初回から 18 秒未満で次の起動を開始できる場合だけ再試行する。HIP、他 OS/architecture、通常の `cudaMalloc failed`、他の起動失敗は対象外（`serve/server.py:3291-3311`、`strata_control/vision_reader.py:175-190`）。
- CUDA reader 内部の context retry 表示は Linux CUDA build の integrated GPU で `cudaSetDevice` が memory allocation error となり、12 回以内の retry が実際に起きた場合だけ出る。HIP と他 platform はこの retry 条件に入らない（`tools/vision/own/vit_gpu.h:48-58`、`tools/vision/own/vit_gpu.cu:831-853`）。
- HIP の fused attention 最長 launch 計測は `STRATA_VIT_PROF` だけでは有効にならず、HIP build で `m.fa` が有効な場合に限られる（`tools/vision/own/vit_gpu.cu:631-638,1080-1102,1155-1159`）。
- CLI に同名の値や優先順位を設定する引数はない。サーバー起動時には Python server 自身が親プロセスの `os.environ` を読む一方、reader 子プロセスは `child_env` が親環境を複製した後に profile の `cfg.env` を反映した環境を受け取る。よって `cfg.env.STRATA_VIT_PROF` は子 reader の C++ 診断値を上書きできるが、server 自身の retry 診断判定は上書きしない。vision 用 GPU visibility の変更はこの変数を変更しない（`serve/server.py:4431-4441,4608-4623,10208-10209`）。

## 実行時の詳細

- `own_reader.cpp` は各画像について画像読み込み・decode・prepare の後、encoder 呼び出し前に `getenv` を確認し、設定されていればその区間の経過時間を stderr に出す。この確認は画像ごとで、プロセス起動後に環境を変更した場合も次の画像で再評価される（`tools/vision/own/own_reader.cpp:171-194`）。
- `VitCpu::encode`、CUDA/HIP `VitGpu::encode`、Metal `VitGpu::encode`、SYCL `VitGpu::encode` は関数内の `static const bool prof` に値の有無を初回評価時に保存する。以後同じ reader process 内では環境の変更が反映されない（`tools/vision/own/vit_cpu.cpp:194-205`、`tools/vision/own/vit_gpu.cu:1011-1029`、`tools/vision/own/vit_metal.mm:482-496`、`tools/vision/own/vit_sycl.cpp:486-499`）。
- GPU own reader は `READY` を返す前に warm-up encode を行うため、設定時は warm-up の stage 行も出る（`tools/vision/own/own_reader.cpp:150-168`）。その後も encode が成功するたび stage 行を出す。前処理時間の行は encode の成否判定より前に出力されるため、encoder が失敗した画像にも前処理時間行はあり得る（`tools/vision/own/own_reader.cpp:190-204`）。
- CUDA/HIP の `set_device_retrying` は context retry が成功した直後に getenv を確認する。環境値は retry 成功時点で読み、起動中の retry 前に値を変更すればその時点の値が使われる（`tools/vision/own/vit_gpu.cu:833-853`）。
- Python server は `_start_gpu_reader` の呼び出しごとに `prof` を一度読み、その reader start loop 内で固定して使う。GPU reader の再起動は新しい呼び出しで再評価する。retry 待ちは各回 1 秒で、初回からの時間予算・回数制限で打ち切られる（`serve/server.py:3286-3311`、`strata_control/vision_reader.py:175-190`）。
- server 起動時は `child_env` の環境が vision reader に渡される。親環境の値は通常引き継がれるが、profile `cfg.env` の同名キーが子プロセス側の値を上書きする（`serve/server.py:4431-4441,4608-4623,10208-10209`）。単独 CLI 起動時は通常のプロセス環境が reader に使われる。子プロセスでの継承後の変更・上書きは、C++ reader 内で直接設定されていない。

## ログと測定値

- `own_reader.cpp` は stderr に `vit-prof: read + decode + prepare %.2f ms` を画像ごとに出す（`tools/vision/own/own_reader.cpp:190-194`）。
- CPU encoder は stderr に `vit-cpu-prof N=... threads=... isa=...` と各計測 stage の時間を出す（`tools/vision/own/vit_cpu.cpp:398-401`）。GPU encoder は stderr に `vit-prof N=...` と stage 時間を出し、SYCL では PV product の時間も含む（CUDA/HIP: `tools/vision/own/vit_gpu.cu:1152-1159`、Metal: `tools/vision/own/vit_metal.mm:614-618`、SYCL: `tools/vision/own/vit_sycl.cpp:596-599`）。HIP fused attention が有効なら追加で `vit-prof fa: longest fused-attention launch ...` を出す。
- 条件に該当した CUDA reader context retry 成功時は stderr に `vit-prof: GPU context made after %d retries, %.2f s` を出す（`tools/vision/own/vit_gpu.cu:837-841`）。server は stdout に成功時 `vit-prof: GPU reader started after {retries} retries, {seconds:.2f} s`、retry 後の最終失敗時 `vit-prof: GPU reader did not start after {retries} retries, {seconds:.2f} s` を出す（`serve/server.py:3298-3309`）。
- server 配下では子 reader の stderr は指定ログファイル、ログ指定がなければ `subprocess.DEVNULL` に接続される。server 自身の `print` による retry 行は stdout（`serve/server.py:3341-3348`）。
- これらは診断時間の出力であり、この文書では測定性能値や速度向上を主張しない。

## 根拠

- 読み取りと画像処理の計測: `tools/vision/own/own_reader.cpp:89-94,128-168,171-204`
- CPU encoder 計測: `tools/vision/own/vit_cpu.cpp:194-214,397-402`
- CUDA/HIP stage 計測と context retry: `tools/vision/own/vit_gpu.cu:831-853,1011-1039,1147-1161`; retry 条件: `tools/vision/own/vit_gpu.h:48-58`
- Metal / SYCL 計測: `tools/vision/own/vit_metal.mm:482-505,605-618`; `tools/vision/own/vit_sycl.cpp:486-512,591-603`
- Backend build 条件: `tools/vision/own/CMakeLists.txt:120-164`
- server の retry 判定・ログ・子環境: `serve/server.py:3286-3311,3341-3348,4428-4441,4608-4623,10208-10209`; retry 条件 helper: `strata_control/vision_reader.py:175-190`
