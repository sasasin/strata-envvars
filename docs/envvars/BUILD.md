# `BUILD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`BUILD` は Strata のエンジンをビルドする 4 本のパッケージスクリプトが、CMake のビルドツリーを置くパスとして読む環境変数です。対象は Linux x86_64 向け CUDA パッケージ、Linux x86_64 向け SYCL パッケージ、DGX Spark（Linux arm64）向け CUDA エンジン、Windows x86_64 向け CUDA パッケージです。各スクリプトは選んだパスを CMake の configure/build に渡し、ビルド後の `strata` などもその場所から読み出します。エンジン実行時の動作を変える設定ではありません。根拠: `tools/packaging/build_cuda_linux.sh:16-18,26-27,43-50,65-66`、`tools/packaging/build_sycl_linux.sh:18-19,25-29,49-51,57`、`engine/spark/build_engine.sh:17-23,48-51,63-65,78-79`、`tools/packaging/build_cuda_windows.py:15-19,151-177,181-185`。

## 値と判定

Linux のシェルスクリプトは `${BUILD:-既定値}` で読み、Windows の Python スクリプトは `os.environ.get("BUILD") or 既定値` で読みます。どちらも未設定または空文字なら既定値を使い、空でない値はビルドディレクトリのパスとして渡します。値の数値変換、文字列比較、範囲検査、clamp はありません。シェル版は引用符付きで後続コマンドに渡すため、空白を含む値も単一のパス引数です。絶対パス・相対パスのいずれも値として特別扱いされず、明示値のパスが使用されます。

| ビルドスクリプト | unset または空文字 | 設定時に使う値 | 値の検査 |
|---|---|---|---|
| `tools/packaging/build_cuda_linux.sh` | `$repo/build-$variant`（既定の `VARIANT=cuda13` なら `build-cuda13`） | 非空の `BUILD` | BUILD 自体の検査なし。`VARIANT` は `cuda12` / `cuda13` 以外だと別途終了コード 2 で終了 |
| `tools/packaging/build_sycl_linux.sh` | `$repo/engine/build-sycl` | 非空の `BUILD` | BUILD 自体の検査なし |
| `engine/spark/build_engine.sh` | `$repo/build-spark` | 非空の `BUILD` | BUILD 自体の検査なし |
| `tools/packaging/build_cuda_windows.py <cuda12|cuda13>` | `<repo>/build-win-<variant>` | 非空の `BUILD` | `os.environ.get("BUILD") or default` を `pathlib.Path` に渡す。数値等の検査なし |

Python の Windows スクリプトでは設定値を `Path` にし、CMake configure 用の `-B` と `cmake --build` に文字列化して渡します。OS 判定で Windows 以外は早期終了するため、その経路では `BUILD` は読みません。根拠: `tools/packaging/build_cuda_windows.py:151-177`、`tools/packaging/build_cuda_windows.py:68-72`。

根拠: `tools/packaging/build_cuda_linux.sh:17-27`、`tools/packaging/build_sycl_linux.sh:19-29`、`engine/spark/build_engine.sh:18-25`、`tools/packaging/build_cuda_windows.py:151-177`。

## 有効になる条件

- 変数を読むのは上記のビルドスクリプトを起動したときだけです。通常の Strata エンジンやサーバーを起動するときに読む実装は見つかりません。
- CUDA パッケージスクリプトは CUDA 12/13 の variant と一致する `nvcc` を要求し、違えば `build_cuda_linux.sh:30-33` のエラーメッセージを stderr に出して終了コード 2 で終了します。`BUILD` の値はこの判定に影響しません。
- SYCL パッケージスクリプトは `patchelf` と oneAPI の `icpx` を要求し、欠けていれば各確認箇所で stderr に理由を出し終了コード 2 で終了します（`tools/packaging/build_sycl_linux.sh:30-38`）。AOT 指定時の `ocloc` 要件も同様です。同変数はビルドディレクトリを変えるだけです。
- Spark スクリプトは Linux arm64 以外なら stderr に `build_engine.sh: this builds on arm64 Linux (the DGX Spark)` を出し、終了コード 2 で終了します。また CUDA 13 toolkit を要求します（`engine/spark/build_engine.sh:29-45`）。`BUILD` はこれらの条件を上書きしません。
- Windows CUDA パッケージスクリプトは Windows 以外では `BUILD` を読む前に `this builds the Windows engine; on Linux use tools/packaging/build_cuda_linux.sh` で失敗します（`tools/packaging/build_cuda_windows.py:151-162`）。Windows 上では variant が CLI 引数 `cuda12` / `cuda13` のいずれかであることが必要で、無効なら使い方を表示して戻り値 2 です（同:152-158）。
- これらのスクリプトに `BUILD` を上書きする CLI オプションはありません。`BUILD_VISION_DIR` は画像 reader 用の別ビルド先で、`BUILD` を置き換えません（`tools/packaging/build_cuda_linux.sh:54-59`、`engine/spark/build_engine.sh:21-23,67-72`）。

## 実行時の詳細

値は各スクリプトの起動時に一度読みます。シェル版は通常のシェル展開、Windows Python 版は `main` での `os.environ.get` で決め、スクリプト実行中に親環境の変更を再読込しません。選択したパスを CMake の configure/build に渡します。Linux 3 経路はリポジトリのルートへ移動してから CMake を呼び、CUDA と Spark ではさらに同じビルドツリーから実行ファイル等をコピーします（`tools/packaging/build_cuda_linux.sh:37,43-50,65-66`、`tools/packaging/build_sycl_linux.sh:40,49-51,57`、`engine/spark/build_engine.sh:50-51,63-65,75-79`）。Windows 版は `build` を configure args・target discovery・build command・成果物コピーに使います（`tools/packaging/build_cuda_windows.py:162,174-185`）。

この値を Strata の実行時にキャッシュする処理はありません。Windows 版は元の環境を含む `env` を CMake subprocess に渡しますが、選択したビルド先は別途コマンド引数でも指定します（`tools/packaging/build_cuda_windows.py:111-123,169-177`）。名前が似た `BUILD_DIR` は `engine/sycl/tools/build.sh:39` で読む別の環境変数です。

## ログと測定値

`BUILD` の値だけを表示するログや、値を検査して出す警告・エラーはありません。選んだパスを CMake に渡した後の configure/build の出力や失敗は各ツールから出ます。スクリプト側で明示している失敗メッセージは、CUDA variant/toolkit、SYCL の依存ツール、Spark の OS/architecture/toolkit など別条件のものです（`tools/packaging/build_cuda_linux.sh:24,32`、`tools/packaging/build_sycl_linux.sh:23,30,34,36-37`、`engine/spark/build_engine.sh:31,41-45`）。測定値の記載はありません。

## 根拠

- `tools/packaging/build_cuda_linux.sh:16-27,30-33,37-50,65-66`
- `tools/packaging/build_sycl_linux.sh:18-29,30-38,40-51,57`
- `engine/spark/build_engine.sh:17-25,29-45,50-51,63-79`
- `tools/packaging/build_cuda_windows.py:15-19,68-85,111-123,151-203`
- `engine/sycl/tools/build.sh:39`（異なる `BUILD_DIR` の読み取り）
