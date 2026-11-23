# `HY4_LAYER_SPLIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP 版 `strata-hy4` において、Hy4-Flash の 42 層の expert 配置を複数 GPU 間で層ごとに分ける指定です。空でなければ、モデルロード時に各層の担当 GPU を作り、その層の expert をまず担当 GPU に置きます。担当 GPU に収まらない expert は通常の空き容量ベース配置に回り、さらに split 後の空き VRAM に hottest experts を追加配置します。そのため、値は層ごとの優先担当を指定しますが、GPU 上の expert を層だけに完全限定する指定ではありません。`strata-hy4` の CUDA/HIP ターゲットがこの環境変数を読みます。`engine/src/hy4flash/metal/hy4_metal_main.cpp` と `engine/src/hy4flash/sycl/sy_main.cpp` にはこの名前の読込がなく、Metal/SYCL 実装には適用されません（`engine/CMakeLists.txt:846-890`）。

## 値と判定

`main` の引数処理開始時に `getenv("HY4_LAYER_SPLIT")` を呼び、未設定なら空文字列にします。明示的な空文字列も同じ扱いです。値は環境変数読み取り時には変換されず `std::string` に保持され、CLI の `--layer-split` があればその引数で置き換えられます。環境変数値は `--layer-split` と同じ仕様でモデルロード時に解釈されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:361-362,375-405,577,656-657`）。

| 条件 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP `strata-hy4`、選択 GPU が 2 台以上 | split 指定なし。デフォルトの expert 配置 | 大文字小文字を区別して正確に `auto`。または各 GPU 用の数値列で、読まれた個数が GPU 数と一致し合計が 42（2 GPU なら `20,22`、`0,42` など） | `AUTO` は `auto` ではなく数値列扱い。2 GPU で `42` は個数不足、`20,20` は合計不足となり無効。 |
| CUDA/HIP `strata-hy4`、GPU が 1 台 | split 指定なし | なし（この条件では値を使わない） | 値の妥当性確認も行われず、無視される |

数値列は各カンマ位置から `atoi` で変換し、各数値を `max(0, 値)` にします。文字列全体の厳密な数値検査はありません。したがって空要素や数字で始まらない要素は `0`、負数も `0` になり、先頭の空白・符号や数値後ろの文字は `atoi` の変換規則に従います（例: `1x,41` は2 GPUで合計42として受理されます）。GPU 数分を読み終えた後の余分な要素は走査されません。`auto` 以外では、この変換後の要素数が GPU 数と一致し、合計が42の場合だけ有効です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:958-997`）。

## 有効になる条件

- `strata-hy4` の CUDA または HIP ビルドを使うこと。CMake は `STRATA_BUILD_HY4` を有効にし CUDA/HIP のいずれかを有効にした場合に、この runner ソースをターゲットへ組み込みます。Metal と SYCL は専用の別ソースです（`engine/CMakeLists.txt:846-890`）。
- モデルロード時に primary GPU に加えて peer GPU が少なくとも1台あり、環境値または `--layer-split` の値が空でないこと。GPU リストは `HY4_GPUS` または `--gpus` / `--devices` から組み立てられ、peer がいなければ split 指定は使用されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:361-405,514-543,649-659`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:958`）。
- server モードと offline CLI のどちらでも、runner は設定値を GPU model に渡します。server は `ServeOpts` 経由、offline 実行は `GpuModel` へ直接渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,613-659`; `engine/src/hy4flash/run/hy4_serve.hip.h:262-295`）。ただし server の複数 GPU 構成が `layer_split` 設定を `--layer-split` として渡す場合、その CLI 値が環境変数を上書きします（`terminal/serve/hy4_kind.py:134-140`）。
- 分散 expert モード `--mpi-experts` は単一の可視 CUDA GPU/host を要求し、`HY4_GPUS` が空でない場合などは引数検査で終了するため、複数 GPU のこの split 経路とは併用できません（`engine/src/hy4flash/run/hy4_main.hip.cpp:508-512,578-611`）。

## 実行時の詳細

環境変数は `main` 内で引数解析より前に読み取られ、その実行中は `std::string layer_split` に保持されます。関数内 `static` やリクエスト単位の再読込はなく、プロセス起動後にプロセス環境を変えても、この値の再評価はありません。`--layer-split VALUE` を指定すると、引数解析順に代入され、最後に処理された指定が使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:361-405`）。

`auto` は各 GPU の expert 用 VRAM 容量を GiB 単位で重み（最低0.25）にし、その重みで42層を按分します。丸めの結果を調整して合計42にします。明示列は GPU 数と要素数が一致し、合計42なら層数として採用します。split が採用されると stderr に GPU ごとの層数と範囲を `[load] --layer-split active across ...` の形式で出し、ロード処理は各層の担当 GPU を優先して expert を配置します。容量に収まらない場合の通常配置と、空き容量に対する第2配置もあります（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:958-1009,1012-1071`）。

## ログと測定値

明示値が無効なら、stderr に `[load] --layer-split %s invalid for %zu GPUs (must sum to 42); ignoring` を出し、split 指定を捨てて既定の配置へ進みます。これはプロセス終了エラーではありません。受理された split は stderr に `[load] --layer-split active across %zu GPUs:` に続けて `GPU%d=%d layers[%d..%d]` を GPU ごとに出します。値が空、または GPU が1台の場合は、この split 計算・ログはありません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:958-1009`）。この変数に関する測定値は該当資料で確認できません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:361-362,375-405,507-543,544-577,613-659` — 環境読込、CLI 上書き、GPU リスト、serve/offline への伝達。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:147-150,954-1009,1012-1071` — split 判定、値変換、ログ、配置。
- `engine/src/hy4flash/run/hy4_serve.hip.h:262-295` — serve 時の model load へ設定を渡す経路。
- `terminal/serve/hy4_kind.py:134-140` — server が複数 GPU 用 CLI 引数を追加する条件。
- `engine/CMakeLists.txt:846-890` — CUDA/HIP ターゲットと専用 Metal/SYCL 実装の区別。
