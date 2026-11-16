# `STRATA_GGML_DIR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

これはエンジン実行時の設定ではなく、Strata のセットアップ／ビルド用プロセスが読む環境変数である。値が有効なら、同梱の `third_party/strata-ggml` の代わりに、指定した llama.cpp checkout 内の `ggml` をエンジンのビルド元にする。ビルドされた後の `strata` がこの環境変数を読んで挙動を変える箇所は見つからなかった。セットアップでは同じ checkout を画像 reader のビルドにも渡す（`setup.py:3805-3819, 6364, 6379-6385`）。

設定の核は CMake cache variable `STRATA_GGML_DIR` であり、CMake 自身が同名のプロセス環境変数を自動で読むわけではない。セットアップや packaging script が環境値を読み、`-DSTRATA_GGML_DIR=<path>` に変換している（`setup.py:3805-3814`, `cmake/strata_ggml.cmake:7-13`）。直接 CMake を使う場合は `-DSTRATA_GGML_DIR=...` が必要。

## 値と判定

| 読み取り経路 | unset / 空文字 | 設定時に使われる値 | 無効値・結果 |
|---|---|---|---|
| `setup.py` のセットアップ | helper は `os.environ.get` の結果が空なら `None` を返し、同梱 ggml を使う | 値を `Path` にし、その直下に `ggml/CMakeLists.txt` が存在すればその checkout を返す | 空でないがそのファイルがない値も `None` になり、同梱 ggml へ黙って fallback（`setup.py:3805-3814`）。文字列の列挙値・大小文字・数値変換はない |
| Linux/macOS shell packaging（CUDA・SYCL・Metal・Spark） | `${STRATA_GGML_DIR:-}` を使うため未設定と空文字は同じ。SYCL はその場合 `LLAMA_CPP` に fallback | 空でない文字列を `-DSTRATA_GGML_DIR=...` として CMake に渡す。SYCL は `STRATA_GGML_DIR` が空でない場合 `LLAMA_CPP` より優先（`packaging/build_cuda_linux.sh:36, 41-43`; `packaging/build_sycl_linux.sh:46-50`; `packaging/mac/build_engine.sh:49-50, 64`; `spark/build_engine.sh:26-27`） | checkout の存在確認はこれらの shell では行わず、CMake の `add_subdirectory` に渡す。パスとして解決できない場合は configure が失敗する。shell での unquoted 展開のため、空白を含むパスの扱いは保証されない |
| Windows packaging / HIP build batch | `if defined` が偽なら override 引数を加えない | パスを CMake に渡す。Windows batch は `\` を `/` に置換（`packaging/build_cuda_windows.py:75-76, 173`; `tools/hip/build_windows.bat:71-80`） | Windows の画像 reader build では `tools/mtmd` がないと `llama.cpp with tools/mtmd not found in ... - check STRATA_GGML_DIR` を出して終了する（`packaging/build_vision_windows.bat:38-41`; `tools/hip/build_windows.bat:95-99`）。CUDA Python packaging の engine path には同様の事前検査はない |
| CMake に直接渡す cache variable | `cmake/strata_ggml.cmake` は空を default にし、同梱 tree を選ぶ | 空でなければその値を ggml root として選ぶ | 文字列の parse・正規化・checkout の版検査はここではしない。ggml subdirectory が使えなければ configure の `add_subdirectory` が失敗（`cmake/strata_ggml.cmake:7-13, 56`）。Metal は事前に確認し、`ggml sources not found in '...' (third_party/strata-ggml, or the -DSTRATA_GGML_DIR checkout)` で fatal error（`metal/CMakeLists.txt:80-84`） |

値に `true` / `false` や数字としての意味はない。setup helper は存在確認を行うが、shell wrapper と CMake の直接指定では同じ事前検証をしない。CLI option が環境変数を上書きする仕組みは確認できなかった。なお `STRATA_CMAKE_EXTRA` を受け取る packaging wrapper では、その文字列も CMake 引数として追加されるが、同名定義が重複した場合の選択はこの環境変数自体の parse 規則ではない（例: `packaging/build_cuda_linux.sh:38-43`）。

## 有効になる条件

- Strata のセットアップがソースからエンジンまたは reader を configure するときに有効。既に適合する prebuilt engine を選んでソース build を行わない経路では、この値はその binary を差し替えない（`setup.py:8493-8510`; source build の `llama_override()` 呼出しは `setup.py:6364, 6379-6385`）。
- CMake の root engine、SYCL、Metal の各 configure が `strata_ggml_resolve()` を呼ぶと、選択された root の `ggml` を subdirectory として構成する（`CMakeLists.txt:17`; `sycl/CMakeLists.txt:201-205`; `metal/CMakeLists.txt:78-84`; `cmake/strata_ggml.cmake:7-13, 56`）。バックエンドの有効化自体は別の build option で決まる。
- CUDA build では override のファイル構成も条件になる。`ggml-cuda/template-instances/mmq-instance-tqk6.cu` があれば trellis MMQ 型を追加し、さらに `mmq-instance-tqp5.cu` があれば pair-trellis 型を追加する（`cmake/strata_ggml.cmake:59-71`）。それがない場合、CUDA/HIP で overlay option が有効なら、Strata は configure 時に overlay を試みる。上流 ggml の必要ファイルや編集 anchor が合わないと overlay を無効にし、trellis prompt は FP16 経路に残る（`cmake/strata_ggml.cmake:72-100`; `cmake/strata_ggml_tq_overlay.cmake:15-28, 163-167`）。
- CUDA の `STRATA_MMQ_TAB` は vendored tree では ON にできる一方、override tree では `mmq.cuh` の特定 scheduler 区間の SHA256 が既知値に一致した場合のみ ON となる。不一致時は `STRATA_MMQ_TAB off: mmq.cuh differs from the mirrored scheduler (...)` を configure status に出す（`cmake/backends/cuda.cmake:171-203`）。
- Windows の packaging reader scripts は画像 reader build 時に override tree 内 `tools/mtmd` を要求する。reader を build しない設定ではそのチェック経路を通らない（`packaging/build_vision_windows.bat:38-41`; `tools/hip/build_windows.bat:92-103`）。

## 実行時の詳細

環境値を読むのはビルド側である。`setup.py:3808-3809` の `llama_override()` は呼び出しごとに `os.environ.get("STRATA_GGML_DIR")` を行い、static cache は持たない。helper は setup の main build、local engine 再構築、vision build、macOS setup から呼ばれる（`setup.py:3822-3831, 5932-5963, 6364, 6379-6385, 8495`; `metal/setup_mac.py:476`）。プロセス環境を変更してから次の helper 呼出しがあれば新しい値が評価されるが、既に開始済みの CMake configure へ後から変更を反映する処理はない。

有効な override は setup で `-DSTRATA_GGML_DIR=<path>` としてエンジン configure に渡され、vision configure では `-DLLAMA_DIR=<path>` になる（`setup.py:3812-3819, 6364, 6379-6385`; `metal/setup_mac.py:139-145, 184-189`）。CMake は非空 cache value を ggml root に採用し、`${root}/ggml` を追加する。unset / 空のときは `${repo_root}/third_party/strata-ggml` が選ばれる（`cmake/strata_ggml.cmake:7-13, 56`）。この選択はビルド時だけであり、ビルド後の生成処理、モデル状態、サーバー request ごとの動作への適用はない。

## ログと測定値

- Metal CMake で override tree に `ggml/CMakeLists.txt` がなければ configure を fatal error にする（`metal/CMakeLists.txt:80-84`）。
- Windows の画像 reader build は `tools/mtmd` がない override path を検出すると、上記のエラー文を出して終了する（`packaging/build_vision_windows.bat:38-41`; `tools/hip/build_windows.bat:95-99`）。
- trellis MMQ overlay の不一致時は不足ファイルまたは anchor/signature の理由を含む `trellis MMQ overlay: ...: off` / `trellis MMQ overlay off: ...` status を出し、overlay を無効にする（`cmake/strata_ggml_tq_overlay.cmake:25-28, 163-167`）。
- `docs/DETAILS.md` にこの build override の性能測定値は見つからなかったため、性能値は記載しない。

## 根拠

- `setup.py:3805-3819` — 環境値の取得、checkout 存在条件、CMake/vision への引数化。
- `setup.py:5932-5965, 6358-6385, 8493-8510` — 再ビルドと prebuilt 選択の経路。
- `packaging/build_cuda_linux.sh:35-59`, `packaging/build_sycl_linux.sh:42-50`, `packaging/mac/build_engine.sh:49-74`, `spark/build_engine.sh:26-27, 62-69` — POSIX packaging の環境値転送。
- `packaging/build_cuda_windows.py:68-77, 164-176`, `packaging/build_vision_windows.bat:38-64`, `tools/hip/build_windows.bat:71-80, 92-114` — Windows 経路の転送と reader path check。
- `cmake/strata_ggml.cmake:7-13, 56-100`, `cmake/backends/cuda.cmake:171-203`, `cmake/strata_ggml_tq_overlay.cmake:20-28, 163-167` — ggml root の選択と CUDA 専用 build 条件。
- `metal/CMakeLists.txt:74-84`, `sycl/CMakeLists.txt:201-205` — 他 backend の configure 経路と Metal の欠落エラー。
