# `DS4_DBG_MEM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DeepSeek V4.1 エンジンのメモリ共有診断を実行します。`ensure()` が呼ばれるたびに、小さな device allocation に `host_view()` 経由で `42.0f` を書き、`cudaMemcpy` で読み戻した値を stderr に表示します。モデル計算の選択や結果を切り替える設定ではなく、診断用の追加 allocation・メモリ操作・ログを発生させます（`metal/src/engine/ds4_finish.cpp:62-78`）。

## 値と判定

| 値 | 判定・動作 |
|---|---|
| 未設定 | 診断を実行しない |
| 空文字を含む任意の設定値 | `std::getenv(...)` が非 null となるため診断を実行する |

値の文字列、数値、先頭文字は parse しません。無効値や境界値という区別もありません。設定有無以外の既定値や CLI 引数による上書きはありません（`metal/src/engine/ds4_finish.cpp:63`）。

割り当てサイズは別変数 `DS4_MEM_GB` の設定有無で分かれます。未設定なら 4096 bytes、設定されていれば値の内容にかかわらず 64 MiB です（同 `:65-66`）。

## 有効になる条件

このコードは macOS 専用の `metal/` CMake プロジェクトに含まれる `strata_ds4` ターゲットの一部です。CMake は Apple 以外では構成を停止し、Metal C++ headers と `STRATA_METAL_ENGINE` が有効で、指定された llama.cpp checkout がある場合に DeepSeek エンジンを追加します（`metal/CMakeLists.txt:13-17,51-79,132-169`）。通常の CUDA/HIP/SYCL ビルドや Metal の別ターゲットには、この読み取り経路は含まれません。

`ensure()` は DeepSeek の Metal host dispatch 用共通 Context を用意し、finish や各種演算の入口から呼ばれます。`finish()` は入力サイズが正の場合に `ensure()` を呼び、DeepSeek kernel 側からその finish 関数へ到達します（`metal/src/engine/ds4_finish.cpp:136-143`; `src/dsv41/ds4_kernels.cu:2196-2215`）。そのほかにも同ファイル内の複数の dispatch 入口が `ensure()` を呼びます（例: `metal/src/engine/ds4_finish.cpp:196,247,282,318,374,424,484,515,560,614,663,729`）。CLI、モデル固有状態、他の環境変数による `DS4_DBG_MEM` 自体の追加ゲートはありません。

## 実行時の詳細

`ensure()` は診断ブロックを `g_cx` の初期化済み確認より前に実行します。そのため値は関数呼び出しごとに読み直され、`static` cache されません。プロセス実行中に環境を変更できる呼び出し元がある場合、次の `ensure()` から設定有無が反映されます。DeepSeek の dispatch が繰り返し `ensure()` を通るため、変数を設定すると各呼び出しで allocation と診断を繰り返します（`metal/src/engine/ds4_finish.cpp:62-80`）。

割り当てに成功し `host_view(p)` が得られた場合、Strata は view の先頭へ `42.0f` を書き、`cudaMemcpy(&out, p, 4, cudaMemcpyDeviceToHost)` を呼んでから `DBG mem: gpu=%p view=%p  wrote 42 through the view, cudaMemcpy gives %g` を stderr に出します。`host_view()` が null なら `DBG mem: gpu=%p has no host view` を出します。`cudaMalloc` の失敗時はこのブロックからログを出さずに進みます。また `cudaMemcpy` と `cudaFree` の戻り値は検査されないため、この診断コード自身はコピー・解放の失敗を別途報告しません（`metal/src/engine/ds4_finish.cpp:65-77`）。

`ensure()` は続けて Context と Metal kernel library を初期化します。したがって診断ログの後で library compile が失敗した場合、呼び出し元の演算が失敗することがあります。これは `DS4_DBG_MEM` 固有の分岐ではなく、通常の `ensure()` の失敗経路です（`metal/src/engine/ds4_finish.cpp:79-85,141-149`）。

## 根拠

- 候補一覧には名前がありますが、直接読み取りは `metal/src/engine/ds4_finish.cpp:63` のみです。リポジトリ全体の候補名検索でも他の参照はありません。
- `DS4_DBG_BIND` は別の設定名で、`ensure()` 内に独立した追加診断があります（`metal/src/engine/ds4_finish.cpp:86-118`）。`DS4_DBG_MEM` を設定しただけではこの bind 診断は有効になりません。
- `DS4_DBG_MEM` の処理は Metal host 側の Strata コードに限って記述しています。`cudaMalloc` / `cudaMemcpy` が互換ヘッダーから Strata Metal runtime に接続されることは `metal/include/metal_compat/cuda_runtime.h:137-153` にありますが、GPU driver や外部 runtime の内部動作はここでは扱いません。
