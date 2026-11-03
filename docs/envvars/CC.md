# `CC`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`CC` は Strata のセットアップがローカルビルドを構成するとき、CMake の `CMAKE_C_COMPILER` 定義に渡すホスト C コンパイラを指定します。モデル実行時の環境変数ではなく、主に NVIDIA CUDA エンジンのビルド時に使われます。CUDA イメージ生成器を再ビルドするときにも参照されます。通常の既製エンジンを使い、ローカルビルドが発生しない経路では、この指定を使うビルド構成処理は通りません。

## 値と判定

`setup.py` は `os.environ.get("CC", "").strip()` で値を読みます。未設定と空文字、空白文字だけの値は同じ空文字になり、`-DCMAKE_C_COMPILER=...` を生成しません。それ以外は前後の空白を除いた文字列をそのまま CMake の `-D` 引数に加えます。Strata 側で実行ファイルの存在確認、値の形式検査、分割、既定コンパイラの選択、値域制限はしません。

| `CC` の値 | Strata の処理 |
|---|---|
| 未設定、`""`、空白だけ | `CMAKE_C_COMPILER` を指定しない |
| 例: `gcc`, `/usr/bin/clang` | 前後空白を除いた値を `-DCMAKE_C_COMPILER=<値>` として渡す |

`CXX` は別に `CMAKE_CXX_COMPILER` へ渡されます。`CUDAHOSTCXX` は CUDA 用ホスト C++ コンパイラとして渡され、空または未設定なら `CXX` の値にフォールバックします。`CC` が `CXX` や `CUDAHOSTCXX` の既定値になる処理はありません。これらの値が同時に指定された場合も、Strata は独立した CMake 定義を生成します。

## 有効になる条件

- CUDA エンジンをローカルで構成する場合、`build_engine()` が `host_compiler_defs(True)` を呼び、`CC` を含む定義を CMake に渡します。エンジンがすでに有効でビジョン生成器も最新と判定されると早期 return するため、その回はこの読み取りに到達しません。
- CUDA を使う画像生成器をビルドし直す場合も同じ定義を使います。ビルド済み画像生成器が再利用される場合はビルド処理を通りません。
- HIP エンジンの構成経路であることだけでは `CC` は渡されません。HIP 画像生成器の定義も `host_compiler_defs(False)` を使わず、`CC` を含みません。
- `CC` に対応するモデル CLI 引数やサーバー実行時の分岐はありません。`--build` などでローカルビルドが必要なセットアップ経路かどうかが適用を左右します。

## 実行時の詳細

値は `host_compiler_defs()` の呼び出し時に読み取られ、関数内・プロセス内のキャッシュはありません。CUDA エンジンと CUDA 画像生成器では、セットアップが `cmake_build()` に渡す `defs` の一要素になります。`cmake_build()` は CMake の configure コマンドにそれを追加して実行し、その後 CMake build を実行します。既存 build directory でも configure コマンドに定義を含めますが、CMake が既存キャッシュとどう扱うかは CMake 側の動作であり、Strata はコンパイラ変更の成功を保証する独自処理をしていません。

CMake configure または build が失敗すると、セットアップは失敗コマンドの終了コードを含む `command failed (exit N): ...` を報告して終了します。更新時のローカルエンジン再ビルドには例外経路があり、失敗を警告 `could not compile the updated engine...` として扱い、インストール済みエンジンで起動を続けます。`CC` 自体に関する Strata 固有の警告や無効値メッセージはありません。

## 根拠

- `setup.py:6001-6012` — `CC`、`CXX`、`CUDAHOSTCXX` の読み取り、空白除去、独立した CMake 定義の生成。
- `setup.py:5951-5975` — configure/build コマンドの組み立てと実行、および失敗時の再試行。
- `setup.py:6079-6084,6090-6101` — ローカルエンジン再利用の早期 return と、CUDA エンジン構成に定義を渡す箇所。
- `setup.py:6111-6119` — ビジョン生成器を再ビルドするときの定義と `host_compiler_defs()` 呼び出し。
- `setup.py:5172-5181` — CUDA 画像生成器の configure 定義に `host_compiler_defs(True)` を加える箇所。
- `setup.py:5183-5188` — HIP 画像生成器では別の定義経路を使う箇所。
- `setup.py:1032-1041` — 子コマンド出力と非ゼロ終了時のセットアップ失敗報告。
- `setup.py:5733-5743` — 更新時のローカルエンジン再ビルド失敗を警告にして既存エンジンを使う経路。
