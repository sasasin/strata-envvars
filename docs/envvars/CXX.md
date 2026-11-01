# `CXX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

## 役割

`CXX` は Strata の本番エンジンが実行時に読む設定ではなく、ソースからビルドするときに C++ コンパイラを指定する入力です。`setup.py` は値を CMake の `CMAKE_CXX_COMPILER` 定義にして渡します。CUDA ビルドで `CUDAHOSTCXX` が未設定または空なら、同じ `CXX` の値を CUDA host compiler の定義にも使います。別経路として、同梱の Trellis ビルドスクリプトが `CXX` をコンパイラコマンドとして展開します。

## 値と判定

| 読み取り箇所 | 未設定 | 空文字 | 設定値 |
|---|---|---|---|
| `setup.py` の `host_compiler_defs()` | `os.environ.get` の既定 `""` を `.strip()` し、`CMAKE_CXX_COMPILER` を渡さない | `.strip()` 後も空なので渡さない | 前後の空白を除いた文字列を `-DCMAKE_CXX_COMPILER=<値>` として渡す。数値・実在性・実行可能性の検査はない |
| `tools/trellis/build.sh` | `${CXX:-g++}` により `g++` を使う | `:-` のため `g++` を使う | 変数の値をコマンド語として展開する |

`setup.py` では空白だけの値も `.strip()` 後に空となり、省略されます。内部の空白や引用符を独自に parse する処理はありません。Trellis スクリプトでは代入値を引用符で囲まずにコマンド位置へ展開するため、シェルの word splitting と pathname expansion が適用されます。値の有効性とコンパイル結果は後続の CMake・コンパイラ呼び出しで決まり、Strata 独自の fallback や値域制限はありません。

## 有効になる条件

- `setup.py` では、既製エンジンを使わずソースビルドが必要になり、対応する CMake configure に進んだときに読み取られます。エンジンの configure では CUDA ビルド用に `host_compiler_defs(True)` が使われます。CUDA の画像エンコーダを configure する場合にも同じ helper が使われます。既存のビルド成果物が最新で configure を省略する経路では、この値はその実行で使われません。
- CPU の画像エンコーダでは `host_compiler_defs(False)` が呼ばれますが、同関数は `CXX` に対応する `CMAKE_CXX_COMPILER` を渡し、CUDA host compiler 定義は作りません。
- CUDA host compiler は `CUDAHOSTCXX` が `.strip()` 後に空でなければそちらが優先されます。空なら `CXX` が使われます。`CXX` と `CUDAHOSTCXX` は C 言語 compiler 用の `CC` とは別に処理されます。
- Trellis 用スクリプトは Linux x86-64 向けの standalone build で、`test`（引数省略時）、`lib` の各経路で `CXX` を使います。`hip` 経路の host 側・HIP 側コンパイルはそれぞれ `g++` / `hipcc` を直書きしており、この分岐では `CXX` を使いません。

## 実行時の詳細

`setup.py` の helper は呼び出されるたびに `os.environ` を参照するため、そのビルド実行内では configure 引数を組み立てる時点の値が使われます。値は CMake の `-D` 引数へ渡され、Strata 実行ファイルに保存される runtime setting ではありません。CMake configure と build は `cmake_build()` が順に実行します。configure または build が失敗すれば、その呼び出しの失敗が setup の失敗経路になります。`CXX` 固有の警告やログ、無効値の fallback は実装されていません。

Trellis スクリプトは起動時に `CXX` を `CXX` shell variable に設定し、コンパイル各コマンドで展開します。スクリプト冒頭の `set -e` により失敗したコンパイルコマンドでスクリプトが停止し、成功時は最後に `built <出力先>` を表示します。

## 根拠

- `setup.py:5850-5861` — `CC`、`CXX`、`CUDAHOSTCXX` の読み取り、空白除去、CMake 定義の生成。
- `setup.py:5927-5968` — ビルド済み判定後のエンジン configure、およびエンジン・画像エンコーダで helper を使う箇所。
- `setup.py:5800-5824` — CMake configure と build の実行および失敗時の扱い。
- `tools/trellis/build.sh:1-28` — `CXX` の `g++` fallback、使用する build 分岐、`hip` 分岐。
- `docs/TROUBLESHOOTING.md:211-218` — Linux の CUDA source build で `CXX=g++-14` を指定する案内と setup の説明。

候補一覧には `CXX` が含まれており、上記の Strata 所有コードで実際に参照されることを確認しました。`bench/test_gfx906_qsa_query_swizzle_guard.py:126` にもコンパイラ選択の参照がありますが、これはテスト専用コードのため、調査基準に従い挙動の根拠にはしていません。ビルド・テスト・GPU 実行は行っていません。
