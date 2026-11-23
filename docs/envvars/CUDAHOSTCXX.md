# `CUDAHOSTCXX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`terminal/setup.py` のローカル CUDA ビルドで、CMake に渡す CUDA host compiler の値を選ぶ環境変数。Strata は `CUDAHOSTCXX` をコマンド実行時の環境としてそのまま使うのではなく、CMake configure 用の `-DCMAKE_CUDA_HOST_COMPILER=...` 引数に変換する。非空の値があれば `CXX` より優先し、空なら `CXX` にフォールバックする。CUDA を使うエンジンのビルドと CUDA 画像エンコーダーのビルドで使われる。通常の既製エンジン取得・実行や HIP、CPU、Vulkan ビルドを切り替える変数ではない（`terminal/setup.py:6763-6775, 6837-6881, 9513-9542`）。

## 値と判定

`host_compiler_defs()` が `os.environ.get("CUDAHOSTCXX", "").strip()` で読み、前後の空白を除去する。除去後が空なら同じ関数で取得・空白除去した `CXX` を使う。値を数値や真偽値として parse したり、実行可能ファイルの存在をここで検査したりはしない。非空文字列は CUDA ビルド時に CMake 定義へそのまま埋め込まれる（`terminal/setup.py:6763-6775`）。

| 条件（build など） | unset | 設定時に有効になる値 | 無効・fallback になる値 |
|---|---|---|---|
| CUDA エンジンまたは CUDA 画像エンコーダーのローカルビルド | `CXX` が非空ならその値を使用。`CXX` も空なら `-DCMAKE_CUDA_HOST_COMPILER` を追加しない | 前後空白を除いた任意の非空文字列。例: `/usr/bin/g++-14`、`g++-14` | 空文字、空白だけの値は `CXX` にフォールバック。`CXX` も空なら定義なし |
| 非 CUDA ビルド、またはコンパイルしない経路 | CUDA host compiler 定義なし | なし | 値があってもこの関数の呼出しが `cuda=False` なら定義に含まれない |

`" g++-14 "` は `g++-14` として渡る一方、`g++-14 ` などの前後空白は除去される。大文字小文字比較、`true` / `false` 判定、先頭文字判定、数値変換、値域制限はありません。たとえば `0`、`false`、`0anything` も空でないので、文字列のまま渡されます。値の妥当性やコンパイラとしての受理可否は Strata のこの選択処理では判定しません（`terminal/setup.py:6769-6775`）。

## 有効になる条件

- セットアップがエンジンのローカルビルドへ進む必要があります。`--build` を指定すると既製エンジンを選ばず、HIP でない場合は `build_engine()` に進みます。既製エンジンがない場合や既製エンジンに必要な画像エンコーダーがない場合もローカルビルド経路があります（`terminal/setup.py:9513-9542`）。
- `build_engine()` が既存ローカルビルドを再利用せず、CMake を実行する必要があります。エンジンと画像エンコーダーがすでに有効と判定されると早期 return するため、その実行では環境変数をビルド定義へ反映する段階に到達しません（`terminal/setup.py:6818-6847`）。
- CUDA エンジンでは `host_compiler_defs(True)` の結果を CMake 引数に追加します。画像エンコーダーは `vision == "gpu"` の場合に限って CUDA 定義とともに `host_compiler_defs(True)` を使います。`vision != "gpu"` では `host_compiler_defs(False)` となり、この変数は定義に使われません（`terminal/setup.py:6857-6881`）。
- `--cuda 12` / `--cuda 13` や GPU 世代による CUDA toolkit 選択は、ビルドディレクトリや toolkit を選びますが、この値の判定規則は変えません（`terminal/setup.py:6821-6826, 6850-6863`）。
- `CC` は C compiler の定義、`CXX` は C++ compiler の定義にも使われます。CUDA host compiler の選択では、空白除去後の非空 `CUDAHOSTCXX` が `CXX` より優先され、空なら `CXX` が代替になります（`terminal/setup.py:6769-6775`）。CLI に `CUDAHOSTCXX` 専用の引数はありません。
- Nix 開発シェルの `shellHook` は `${stdenv.cc}/bin/c++` を `CUDAHOSTCXX` に設定します。そのシェル内からセットアップが CUDA ビルドを行う場合に、上記の Strata 読取経路へ値が渡ります（`tools/nix/flake.nix:39-44`）。

## 実行時の詳細

この変数は Strata エンジンの実行時設定ではなく、セットアップによる configure 時の選択です。`host_compiler_defs()` は呼び出されるたびに Python の環境を読み、関数内 static cache はありません。エンジン用と画像エンコーダー用で別々に呼ばれる可能性があります。プロセス起動後に環境が変更された場合は、その後の呼出しで取得時点の値が使われます（`terminal/setup.py:6763-6775, 6857-6881`）。

Strata は選択結果を `-DCMAKE_CUDA_HOST_COMPILER=...` として `cmake_build()` に渡します。これは CMake configure コマンドに含まれ、続けてビルドコマンドが実行されます。Windows では同じ configure / build をバッチファイルに書き出して実行し、他の OS ではコマンドを直接実行します（`terminal/setup.py:6709-6735, 6857-6881`）。Strata はこの環境変数を子プロセス環境へ追加・上書きするのではなく、configure 引数へ転送します。

## ログと測定値

`CUDAHOSTCXX` 固有のログ、警告、測定値は見つかりません。configure / build が失敗した場合は通常の CMake 実行失敗経路になります。Strata は初回 configure だけでなくビルドが必要なときに定義を含む configure コマンドを組み立てますが、CMake が既存キャッシュと変更された compiler 定義をどう扱うかは Strata 所有コードの範囲外です（`terminal/setup.py:6709-6735, 6763-6775`）。`docs/DETAILS.md` に本変数の説明または条件付き測定値は見当たりません。

## 根拠

- `terminal/setup.py:6763-6775` — 環境からの読み取り、strip、`CXX` fallback、CUDA 条件つきの CMake 定義生成。
- `terminal/setup.py:6709-6735` — configure / build コマンド実行。
- `terminal/setup.py:6818-6881` — 既存ビルドの判定、CUDA engine / image encoder からの呼び出し。
- `terminal/setup.py:9513-9542` — ready-made engine とローカル build の選択。
- `tools/nix/flake.nix:39-44` — Nix 開発シェル内での値の設定。
