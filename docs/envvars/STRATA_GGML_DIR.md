# `STRATA_GGML_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

これは engine 起動後に読む実行時環境変数ではなく、llama.cpp の checkout から `ggml` を組み込む場所を指定する CMake の `PATH` 型キャッシュ変数です。通常の configure では `-DSTRATA_GGML_DIR=/path/to/llama.cpp` として渡します。Strata の C++ や Python の実行時コードに同名の `getenv` / `os.environ` 読み取りはありません。

Windows HIP 用 `tools/hip/build_windows.bat` だけは、同名のプロセス環境変数が定義されている場合に値を `-DSTRATA_GGML_DIR=...` へ明示変換して CMake に渡します。したがって通常の `cmake` 実行で `STRATA_GGML_DIR` を環境に設定しただけでは、このキャッシュ変数にはなりません。

## 値と判定

| 経路 | 未指定・空 | 値が指定された場合 |
|---|---|---|
| ルート CMake（CUDA/HIP 等） | キャッシュ変数の初期値は空。`STRATA_NATIVE_EXPERTS=ON` なら llama.cpp の pinned commit `3cf03257f219afbe7334045ff7c6a06ac68c627d` を FetchContent で取得し、その `ggml` を追加する | 指定された checkout の `${STRATA_GGML_DIR}/ggml` を `add_subdirectory` する。パスや checkout の版を一般的な形式で parse せず、`ggml` の CMake 構成とファイルが後続処理に必要 |
| SYCL CMake | ルート CMake と同じく空なら同じ pinned commit を取得。ただし native experts が有効な場合 | 指定 checkout の `ggml` を追加する |
| Metal CMake | `STRATA_METAL_ENGINE=ON` のとき空では検証に失敗する | `${STRATA_GGML_DIR}/ggml/CMakeLists.txt` の存在を検査し、なければ `STRATA_GGML_DIR='<値>' is not a llama.cpp checkout` で configure を停止する。存在すればその `ggml` を追加する |
| Windows HIP バッチの環境値 | `if defined` により CMake 引数を付けない。engine は CMake 側の既定 fetch を使う | パスを CMake 用のスラッシュへ置換し、engine configure 時に `-D` で渡す |

パス文字列の正規化、空白を含むパスへの一律の引用、checkout の commit SHA 検証は、この変数のルート/SYCL CMake 定義にはありません。指定ディレクトリが不適切な場合は `add_subdirectory` または後続の必須ソース確認で configure が失敗し得ます。Metal は上記の存在検査を先に行います。

## 有効になる条件

- ルート CMake と SYCL CMake で `STRATA_NATIVE_EXPERTS=OFF` の場合、基本の `ggml` 組み込み分岐は実行されません。既定は `ON` です。
- CUDA ビルドでは指定 checkout の `ggml-cuda` ソースから MMQ 関連コードを構成します。HIP では `STRATA_PREFILL_MMQ=ON` の経路で同じ checkout 内の `ggml-cuda` にある `common.cuh` と `quantize.cu` が必要で、欠けていると configure がエラーになります。
- trellis MMQ は、指定 checkout に `mmq-instance-tqk6.cu` があればその型の実装を使います。なければ CUDA/HIP かつ `STRATA_MMQ_TQ_OVERLAY=ON` の場合に overlay を試みます。overlay 可否は checkout のヘッダー構成にも依存し、指定しただけで trellis MMQ が必ず有効になるわけではありません。
- Metal の単独ビルドでは `STRATA_METAL_ENGINE=OFF` なら engine 構成が早期 return し、このパスの検証と `ggml` の追加は行いません。
- Windows HIP バッチは `build-hip-win\\build.ninja` がない場合だけ engine の CMake configure を実行します。既に build.ninja があると同バッチは再 configure しないため、環境変数を後から変更しても既存 engine build のキャッシュ値は更新されません。

## 実行時の詳細

通常のルート/SYCL ビルドでは、空でないキャッシュ値が `ggml` をソースツリーへ追加する場所を選びます。空の場合は FetchContent が upstream llama.cpp の pinned commit を取得し、その中の `ggml` を追加します。ビルド時に選ばれる依存ソースと GPU prompt 用 MMQ ソースの場所が変わるための設定で、起動済み engine の動作を切り替える機能ではありません。

CUDA の trellis MMQ は、指定先に trellis 用の MMQ instance file があればその実装を登録します。ファイルがなければ overlay 条件に進みます。CUDA/HIP の標準 MMQ ソース参照も指定先または FetchContent 先から組み立てられます。Metal は独立 CMake プロジェクトであり、engine をビルドする際には指定先が必須です。

Windows HIP バッチでは同じ環境値を engine 用の CMake 引数にするほか、vision reader 用の llama.cpp root としても参照します。未設定なら `BUILD_DIR\\_deps\\strata_llamacpp-src` を使い、`tools/mtmd` が見つからない場合は `llama.cpp with tools/mtmd not found in ... - set STRATA_GGML_DIR` と表示して終了します。vision 用 build directory に既に `build.ninja` があれば、そのバッチも再 configure しません。

## 文書との照合

`docs/AMD_HIP.md`、`docs/STRIX_HALO.md`、`docs/INTEL_ARC.md` は、offline build 時に pinned llama.cpp checkout を指定する用途として説明しています。これは CMake の既定 fetch と一致します。`docs/GYRO.md` は trellis 対応 fork を指定する build 例を示し、ソースではその checkout に trellis MMQ instance がある場合と upstream overlay 条件を分けています。

## 根拠

- `CMakeLists.txt:1515-1520,1527-1573` — キャッシュ変数の宣言、native experts 条件、ローカル checkout と pinned FetchContent の選択。
- `CMakeLists.txt:1670-1695,1702-1714,1895-1910` — trellis instance/overlay 判定、CUDA/HIP MMQ ソースの選択と必須ソース検査。
- `sycl/CMakeLists.txt:171-202` — SYCL 側の既定値と同じ pinned source 選択。
- `metal/CMakeLists.txt:70-88,108-113` — Metal engine 用の必須パス確認と ggml 追加。
- `tools/hip/build_windows.bat:13-23,69-80,87-109` — Windows HIP バッチだけが環境変数を CMake 引数と vision root に転送する処理。
- `packaging/build_cuda_linux.sh:33-37`, `packaging/build_hip_linux.sh:50-56`, `setup.py:4376-4382,5437-5443` — Linux build script と setup が環境変数ではなく CMake `-D` 引数を使う例。
- `docs/AMD_HIP.md:228-231`, `docs/STRIX_HALO.md:51-52`, `docs/INTEL_ARC.md:68-69`, `docs/GYRO.md:56-63,160-170` — pinned checkout、offline build、fork 利用についての既存説明。

上記以外の Strata 所有の本番ソースに、`STRATA_GGML_DIR` を実行時環境から読み取る箇所はありません。候補一覧に含まれる名称ですが、主たる実体は build-time の CMake 変数です。
