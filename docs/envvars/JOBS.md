# `JOBS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `main` で未コミット変更なし。調査対象は Strata 所有のソースと同梱ビルドスクリプト。

## 役割

`JOBS` は一部のビルドスクリプトがビルドツールへ渡す並列ジョブ数です。Strata エンジンの実行時設定として値を読む箇所は、この commit では見つかりませんでした。対象は Linux の CUDA/HIP/SYCL ビルドスクリプト、DGX Spark ビルド、SYCL 開発用スクリプト、および Windows HIP の DSV41 ビルドスクリプトです。

## 値と判定

| スクリプト | 未設定または空文字 | 設定時の処理 |
|---|---:|---|
| `packaging/build_dsv41_cuda.sh` | `6` | 値を `ninja -j` に引用符付きで渡す |
| `packaging/build_hip_linux.sh` | `16` | 各 `cmake --build ... -j` に引用符付きで渡す |
| `packaging/build_sycl_linux.sh` | `nproc` の出力 | `cmake --build ... -j` に引用符付きで渡す |
| `tools/dsv41/build_hip_linux.sh` | `nproc` の出力 | `cmake --build ... -j` に引用符付きで渡す |
| `spark/build_engine.sh` | `nproc` の出力 | エンジンおよび有効な vision build の `cmake --build ... -j` に引用符付きで渡す |
| `sycl/tools/build.sh` | `12` | `cmake --build` の `-j` の後へ未引用で展開する |
| `tools/dsv41/win/build_hip_win.bat` | `6`（`if not defined JOBS` の場合） | `cmake --build -j %JOBS%` に展開する |

シェルスクリプトの `${JOBS:-既定値}` は未設定と空文字のどちらにも既定値を使います。整数への変換、範囲確認、clamp、無効値時の独自 fallback はスクリプト内にありません。値はビルドツールにそのまま渡され、受理可能な形式や範囲はこのコードからは保証できません。特に `sycl/tools/build.sh` は未引用展開なので、空でない値に空白や glob 文字が含まれるとシェルの語分割・パス名展開を受けます。Windows バッチでは `if not defined` により未定義時に既定値を設定し、その後 `%JOBS%` をコマンド行に展開します。

## 有効になる条件

スクリプトが実行され、対応する build コマンドに到達した場合に限り効きます。対象は Linux CUDA DSV41 (`packaging/build_dsv41_cuda.sh`)、Linux HIP パッケージ (`packaging/build_hip_linux.sh`)、Linux SYCL パッケージ (`packaging/build_sycl_linux.sh`)、DGX Spark CUDA (`spark/build_engine.sh`)、Linux HIP DSV41 (`tools/dsv41/build_hip_linux.sh`)、Windows HIP DSV41 (`tools/dsv41/win/build_hip_win.bat`)、および SYCL 開発環境 (`sycl/tools/build.sh`) です。

適用される build target や回数は各スクリプトの他の条件にも従います。たとえば HIP パッケージでは `VISION_ONLY`、`DSV41` の条件に応じて build 段階が省略されます（`packaging/build_hip_linux.sh:59-75`）。Spark では `BUILD_DSV41` と `BUILD_VISION` によって target が変わります（`spark/build_engine.sh:50,64-75`）。`JOBS` を指定してもスクリプトが実行されない場合や build コマンドに到達しない場合に動作はありません。

## 実行時の詳細

これらのスクリプトは呼び出し時に環境をシェル展開し、build コマンドの `-j` 引数に渡します。Strata のエンジンプロセスへ値を渡す処理は確認できません。値をキャッシュする処理もなく、スクリプトの変数へ代入した後に同じ実行中の環境変数を読み直す箇所もありません。

スクリプト自身が `JOBS` の値を表示・警告する処理はありません。値が不正で build ツールが失敗した場合、CUDA DSV41、Linux SYCL、Linux HIP DSV41、Spark、SYCL 開発スクリプトは build コマンドの失敗をスクリプトの失敗として伝えます（`packaging/build_dsv41_cuda.sh:13,32-33`、`packaging/build_sycl_linux.sh:17,46`、`tools/dsv41/build_hip_linux.sh:9,27`、`spark/build_engine.sh:16,65-68,74`、`sycl/tools/build.sh:43-50`）。Linux HIP パッケージは build の終了コードを `chk` に渡し、失敗を `build.status` に記録して終了します（`packaging/build_hip_linux.sh:44-47,64-72,80-88`）。Windows バッチは build の後に `BUILD-EXIT %errorlevel%` を表示します（`tools/dsv41/win/build_hip_win.bat:43-45`）。具体的な診断文や終了コードは、実行された build ツールとスクリプト経路によります。

## 根拠

- すべての直接参照を `rg` で検索し確認。既定値と引き渡し: `packaging/build_dsv41_cuda.sh:13,19,32`、`packaging/build_hip_linux.sh:21,31,64,71,80,87`、`packaging/build_sycl_linux.sh:17,28-29,44-46`、`tools/dsv41/build_hip_linux.sh:9,14,27`、`tools/dsv41/win/build_hip_win.bat:10-16,43-45`、`spark/build_engine.sh:16,22,64-75`、`sycl/tools/build.sh:6,37-46`。
- ドキュメント内の使用例: `docs/DGX_SPARK_LINUX.md:59`。これは `JOBS=16` をビルドスクリプトへ渡す例であり、実装上の挙動は上記のスクリプトを根拠としています。
