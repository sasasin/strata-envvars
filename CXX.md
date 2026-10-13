# `CXX`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。対象は Strata 所有ソースでの明示的な読み取りと利用。

## 役割

`CXX` は Strata の Python セットアップが CMake に渡す C++ コンパイラの指定です。エンジン実行中の動作は制御しません。セットアップがローカル CUDA エンジンをコンパイルするとき、およびその経路で画像エンコーダーをコンパイルするときに参照されます。エンジンが既に有効と判定されてビルドを省略する場合は、この値を使う処理まで進みません。

## 値と判定

`setup.py` は `os.environ.get("CXX", "").strip()` で値を読みます。

| `CXX` | Strata の処理 |
|---|---|
| 未設定 | 空文字列になるため、`CMAKE_CXX_COMPILER` の定義を追加しない |
| 空文字、または空白だけ | `strip()` 後に空文字列となり、定義を追加しない |
| 前後に空白がある値 | 前後の空白を除いた文字列を使う |
| それ以外 | 文字列を `-DCMAKE_CXX_COMPILER=<値>` として CMake に渡す。Strata 側で数値変換、値域検査、コンパイラの存在確認はしない |

値を分割して複数の引数にする処理はありません。CMake の configure または後続のビルドで指定を解決できない場合、そこで処理が失敗し得ます。

## 有効になる条件

- NVIDIA CUDA エンジンのローカルビルドでは `host_compiler_defs(True)` が呼ばれ、空でない `CXX` が C++ コンパイラとして渡されます。
- CUDA エンジンのビルド経路で画像エンコーダーをビルドするときも同じ helper を使います。GPU 画像エンコーダーなら `host_compiler_defs(True)`、CPU 画像エンコーダーなら `host_compiler_defs(False)` です。どちらも `CMAKE_CXX_COMPILER` を渡します。
- CUDA ビルドで `CUDAHOSTCXX` が未設定、空、または空白だけなら、`CXX` の値を `CMAKE_CUDA_HOST_COMPILER` にも渡します。`CUDAHOSTCXX` に空でない値がある場合は、そちらが CUDA ホストコンパイラ指定になります。
- Strata の HIP エンジンビルド経路は `host_compiler_defs()` を呼ばず、`CXX` を明示的に CMake 定義へ渡しません。CMake 自身が環境変数をどう扱うかは Strata の実装による処理としては扱いません。
- セットアップが既成エンジンを取得・使用するだけの場合、この値で Strata エンジンをコンパイルする処理はありません。

## 実行時の詳細

値は `host_compiler_defs()` の呼び出し時に Python の `os.environ` から読みます。起動済みエンジンや個々のリクエストでは読みません。helper が生成した `-D...` 引数は `cmake_build()` の configure コマンドに含まれ、CMake は続けて指定ターゲットをビルドします。エンジンと画像エンコーダーのビルド判定を通過しない限り helper は呼ばれないため、環境変数を設定しただけで既存バイナリが再ビルドされるわけではありません。

Strata のセットアップは configure/build コマンドの失敗を通常のエラーとして扱います。`CXX` 固有の警告文や無効値時の fallback は実装されていません。`docs/TROUBLESHOOTING.md` は Linux で CUDA と GCC の版が合わない場合の例として `CXX=g++-14 ./setup.sh` を案内しており、setup がコンパイラ指定を CMake に渡す説明は実装と一致しています。

## 根拠

- `setup.py:3338-3349` — `CC`、`CXX`、`CUDAHOSTCXX` の読み取り、`strip()`、CMake 定義の生成、CUDA ホストコンパイラの既定値。
- `setup.py:3289-3295` — 定義を configure コマンドへ追加し、続けて CMake build を呼ぶ処理。
- `setup.py:3402-3407,3418-3423,3425-3433` — ビルド要否の判定と、CUDA エンジン／画像エンコーダーから helper を呼ぶ箇所。
- `setup.py:2667-2673` — HIP エンジンの CMake 呼び出し。`host_compiler_defs()` は渡されていない。
- `docs/TROUBLESHOOTING.md:52-56` — GCC と CUDA の不整合時に `CXX` でコンパイラを指定する説明。
