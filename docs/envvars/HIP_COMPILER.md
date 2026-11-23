# `HIP_COMPILER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のエンジン構築用 `terminal/setup.py` と HIP パッケージ構築用 shell スクリプトが、HIP のビルド環境を準備するときに `HIP_COMPILER=clang` を環境へ設定します。`terminal/setup.py` はエンジン再構築時に設定して CMake 実行へ渡し（`terminal/setup.py:5589-5617`）、画像用 HIP reader の一部の再構築経路でも設定します（`terminal/setup.py:5670-5690`）。パッケージ用スクリプトも同じ値を export します（`tools/packaging/build_hip_linux.sh:52-67`、`tools/packaging/build_split_hip.sh:27-35`）。

Strata のソースには、利用者があらかじめ設定した `HIP_COMPILER` の値を取得・比較・変換する箇所はありません。上記の設定経路では、もとの値にかかわらず `clang` に置き換えます。エンジンの compiler パス自体は別途 `-DCMAKE_HIP_COMPILER=...` として CMake に渡しています（`terminal/setup.py:5611-5617`）。この環境変数によって CMake や HIP ランタイム側がどう動作するかは、Strata の挙動としては断定できません。

## 値と判定

Strata はこの名前の値を入力として判定しません。以下の構築経路では値を文字列 `clang` に設定するため、事前に未設定、空文字、`clang`、別の文字列のどれであっても、子プロセスへ渡す値は `clang` です。数値変換、大小文字比較、空白除去、範囲判定、無効値時の fallback はありません（`terminal/setup.py:5601-5604, 5670-5675`）。

| 経路 | 条件 | 設定値 | 事前の値の扱い |
|---|---|---|---|
| AMD エンジン再構築 | `build_engine_hip()` が既存エンジンを再利用せず、ROCm root を決定して構築へ進む | `clang` | 無条件に上書き |
| 画像用 HIP reader | `vision == "gpu"` かつ `hipconfig` が PATH に無く、`ROCM_PATH` も未設定のとき | `clang` | 無条件に上書き |
| Linux HIP パッケージ構築 | `build_hip_linux.sh` を実行 | `clang` | shell の `export` で設定 |
| HIP split パッケージ構築 | `build_split_hip.sh` を実行 | `clang` | shell の `export` で設定 |

エンジンが既に有効なビルドとして再利用される場合、`build_engine_hip()` は環境設定より前に戻るため、この関数は `HIP_COMPILER` を変更しません（`terminal/setup.py:5585-5604`）。

## 有効になる条件

- `HIP_COMPILER` を設定するのは Strata の構築・パッケージ作成経路です。通常のエンジン起動やサーバーの実行時にこの名前を読む箇所はありません。
- エンジン再構築では、AMD GPU 用の `build_engine_hip()` が既存 build を再利用せず、ROCm を解決して CMake build に進む必要があります。CMake compiler は `-DCMAKE_HIP_COMPILER={rocm_clang(root)}` でも指定されます（`terminal/setup.py:5585-5617`）。
- 画像用 HIP reader の経路では `vision == "gpu"` である必要があります。環境設定の追加自体は `hipconfig` が見つからず、かつ `ROCM_PATH` が未設定のときだけ行います。GPU reader の CMake configure にも compiler のパスを `-DCMAKE_HIP_COMPILER=...` で指定します（`terminal/setup.py:5670-5690`）。
- `build_engine_hip()` が build 済みエンジンと必要な画像 reader を再利用できる場合は早期 return し、環境値を設定しません（`terminal/setup.py:5585-5593`）。
- `build_image` の HIP 経路は `HIP_PLATFORM`、`ROCM_PATH`、`HIP_PATH` を設定しますが、`HIP_COMPILER` は設定しません。qimage の CMake 引数には別途 compiler path があります（`terminal/setup.py:5850-5855`、`terminal/tools/image/qimage.py:124-135`）。

## 実行時の詳細

`terminal/setup.py` では各 build 関数が実行された時点で `os.environ.update()` により親 Python プロセスの環境を変更します。`run()` は `env` を省略した場合に現在の `os.environ` を複製し、その環境で `subprocess.run()` を呼びます。そのためエンジン build で設定した `HIP_COMPILER=clang` は CMake configure / build の子プロセスへ渡ります（`terminal/setup.py:5601-5604, 1131-1152, 6716-6735`）。値を読み取って cache する処理はなく、設定はその Python プロセスの環境に残ります。

画像用 HIP reader 経路では条件付きで同様に環境を設定してから `cmake_build()` を呼びます（`terminal/setup.py:5670-5690`）。HIP パッケージ用 shell script では `export` 後の `cmake` と build コマンドへ環境が継承されます（`tools/packaging/build_hip_linux.sh:52-67`、`tools/packaging/build_split_hip.sh:27-35`）。実行中に外から環境を変更した場合の反映を Strata が監視する仕組みはありません。

## 根拠

- `terminal/setup.py:5585-5617` — engine build の再利用判定、`HIP_COMPILER` を含む環境設定、明示的な CMake compiler 引数。
- `terminal/setup.py:1131-1152, 6716-6735` — 既定の子プロセス環境が `os.environ` から複製され、CMake がその環境で実行される経路。
- `terminal/setup.py:5670-5690` — vision GPU reader の環境設定条件と CMake build。
- `terminal/setup.py:5850-5855`、`terminal/tools/image/qimage.py:124-135` — image HIP build 経路の環境設定と compiler の別指定。
- `tools/packaging/build_hip_linux.sh:52-67`、`tools/packaging/build_split_hip.sh:27-35` — packaging shell script による export と CMake 実行。
