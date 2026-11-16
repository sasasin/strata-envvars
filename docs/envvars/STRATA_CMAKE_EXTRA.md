# `STRATA_CMAKE_EXTRA`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

これは Strata の実行バイナリが読む設定ではなく、Strata のビルド・パッケージ用スクリプトが CMake の engine configure 引数へ追加する環境変数です。Linux の CUDA / HIP / SYCL ビルド、DGX Spark 用 CUDA ビルド、Windows CUDA Python ビルド、Windows HIP バッチビルドで参照されます。各スクリプトは値を設定値として検証・解釈せず、追加引数として CMake に渡します（`packaging/build_cuda_linux.sh:38-43`、`packaging/build_hip_linux.sh:61-65`、`packaging/build_sycl_linux.sh:48-51`、`spark/build_engine.sh:51-56`、`packaging/build_cuda_windows.py:165-173`、`tools/hip/build_windows.bat:73-80`）。

値の例は `-DSTRATA_GEOMETRY_FILE=/abs/path/geometry.hpp` や `-DSTRATA_MMQ=ON` です。実際に変わるビルド設定は渡した CMake 引数によります。Strata のソースはこの変数自体をアプリ実行時に読まず、生成されたプログラムへの設定転送もしません。

名前の他の出現箇所は、ビルドスクリプト内の説明コメントや、`packaging/make_model_release.py:148` が生成する手順文です。これらは追加の読み取り経路ではありません。全読み取り・判定箇所は上記ビルドスクリプト群と `packaging/shape_build.sh:23-24` の helper 判定です。

## 値と判定

この変数に共通の値パーサーはありません。値の扱いはビルドスクリプトごとに次のとおりです。

| ビルド経路 | unset / 空文字 | 設定値の扱いと境界 |
|---|---|---|
| Linux CUDA / HIP / SYCL、DGX Spark CUDA | `${STRATA_CMAKE_EXTRA:-}` により未設定と空文字はいずれも空。空なら追加引数なし。 | シェルで展開後、引用されていないので空白で単語分割され、各単語が CMake の引数になる。値全体の parse、真偽値判定、数値検査はしない。ワイルドカードはシェルの pathname expansion の対象になる。引数に空白を含むパスなどを一つの値として保つ処理はない（`packaging/build_cuda_linux.sh:40-43`、`packaging/build_hip_linux.sh:62-65`、`packaging/build_sycl_linux.sh:48-51`、`spark/build_engine.sh:51-54`）。 |
| Windows CUDA (`build_cuda_windows.py`) | `os.environ.get(...)` が `None` または空文字なら `or ""` により空になり、追加引数なし。 | Python の `.split()` で空白区切りの文字列リストにし、CMake を `subprocess` で起動する。空白以外の引用・escape 規則や値の検証はない（`packaging/build_cuda_windows.py:165,173`）。 |
| Windows HIP (`build_windows.bat`) | 未定義なら `%STRATA_CMAKE_EXTRA%` は空展開となり追加引数なし。 | `cmake` コマンド行へ環境変数をそのまま展開する。Strata 側で値の parse や検証はしない（`tools/hip/build_windows.bat:73-80`）。 |

このため `1`、`true`、`false`、`0anything`、空白だけの値にも共通の on/off 意味はありません。値は引数文字列として渡されるだけで、意味や有効・無効の判定は個々の渡し先設定と configure 経路に依存します。空白だけの場合は Linux と Python Windows 経路で分割後の引数がなくなります。大小文字や数値境界の検査もこの環境変数に対してはありません（同上）。

## 有効になる条件

- 対応する Strata ビルドスクリプトを実行し、そこで engine の CMake configure が呼ばれること。通常のアプリ実行時にはこの変数の読み取り箇所はありません（上記各読み取り箇所）。
- Windows HIP は `BUILD_DIR` 内に `build.ninja` が既にあると configure ブロックをスキップするため、その実行では値が CMake に渡されません。既存ビルドツリーに変数だけ変更しても反映されません（`tools/hip/build_windows.bat:73-81`）。
- Linux CUDA / HIP / SYCL と DGX Spark は共通 `shape_build.sh` を読み込みます。`SHAPE` が設定されると helper は値を空白で囲んだ文字列に `-DSTRATA_GEOMETRY` を含む部分文字列があるかだけを調べます。一致すれば `-DSTRATA_GEOMETRY=<SHAPE>` の自動追加を抑止し、一致しなければ geometry header の存在を確認してから自動引数を追加します。この検査は CMake 引数の構文解析ではありません（`packaging/shape_build.sh:12-29`）。
- `SHAPE` が設定され、上記部分文字列に一致せず `include/strata/core/geometries/$SHAPE.hpp` が存在しないと、stderr に `shape_build.sh: no header include/strata/core/geometries/$SHAPE.hpp; name the model's header with STRATA_CMAKE_EXTRA=-DSTRATA_GEOMETRY_FILE=<abs path>` を出して終了コード 2 で停止します（`packaging/shape_build.sh:23-27`）。
- Linux CUDA / HIP / SYCL と Spark では、追加値は固定 configure 引数の後、`shape_cmake` の前に配置されています。CUDA Windows Python 経路も基本引数（および `STRATA_GGML_DIR` 指定があればその引数）の後ろへ追加リストを連結します。Windows HIP では `-DSTRATA_MMQ=OFF` と `%GGML%` の後に展開します（`packaging/build_cuda_linux.sh:41-43`、`packaging/build_hip_linux.sh:63-65`、`packaging/build_sycl_linux.sh:49-50`、`spark/build_engine.sh:51-54`、`packaging/build_cuda_windows.py:66-77`、`tools/hip/build_windows.bat:74-80`）。この文書では CMake 自体の重複定義の扱いを Strata の挙動としては扱いません。
- `STRATA_CMAKE_EXTRA` による configure はそれぞれ engine 用 CMake 呼び出しのみです。Linux CUDA の同じスクリプト内の vision reader configure には値を渡していません（`packaging/build_cuda_linux.sh:41-60`）。

## 実行時の詳細

各スクリプトが configure コマンドを組み立てる時点で環境から読み取ります。Linux のシェルスクリプトではそのコマンド行の展開時、Windows CUDA Python では `main()` 内の `os.environ.get()` 時点、Windows HIP ではバッチファイルの configure コマンド行展開時です。Strata 実行プロセス向けの static cache、リクエスト単位の再読込、起動後の環境変更の反映はありません。値は engine の CMake configure に渡されるだけです（`packaging/build_cuda_linux.sh:40-43`、`packaging/build_hip_linux.sh:62-66`、`packaging/build_sycl_linux.sh:48-51`、`spark/build_engine.sh:51-60`、`packaging/build_cuda_windows.py:150-176`、`tools/hip/build_windows.bat:73-85`）。

Linux HIP は engine configure の stdout / stderr を `$OUT/cfg.log` に保存し、失敗時は `build.status` に失敗記録を追記して非ゼロ終了します。CUDA Linux、SYCL Linux、Spark は configure を `set -e` の下で直接実行するため、失敗すればスクリプトが停止します。Windows CUDA Python は実行コマンドを表示し、非ゼロ終了時に `failed: <cmake> ...` の失敗を報告します。Windows HIP は configure が非ゼロなら `exit /b 1` します（`packaging/build_hip_linux.sh:63-68`、`packaging/build_cuda_linux.sh:16,41-46`、`packaging/build_sycl_linux.sh:18,49-51`、`spark/build_engine.sh:17,51-60`、`packaging/build_cuda_windows.py:144-147,173-176`、`tools/hip/build_windows.bat:73-80`）。

## 根拠

- Linux CUDA: `packaging/build_cuda_linux.sh:38-49`
- Linux HIP: `packaging/build_hip_linux.sh:59-69`
- Linux SYCL: `packaging/build_sycl_linux.sh:40-51`
- DGX Spark CUDA: `spark/build_engine.sh:46-60`
- Windows CUDA: `packaging/build_cuda_windows.py:66-77,150-176`
- Windows HIP: `tools/hip/build_windows.bat:70-85`
- `SHAPE` との相互作用: `packaging/shape_build.sh:12-29`
