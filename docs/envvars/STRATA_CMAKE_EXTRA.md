# `STRATA_CMAKE_EXTRA`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（2026-11-26 時点）。作業ツリーは `## main...origin/main`（未コミット変更なし）。

## 役割

engine の cmake configure 行に追加の `-D...` 引数を差し込むためのビルド時専用の置き場所。実行ファイルはこの名前を読まない（`rg STRATA_CMAKE_EXTRA` の全参照はビルド用スクリプト 7 本で、`engine/` の C++ / CMake 側に参照はない）。

読み取りは 6 本のビルドスクリプトだけ: `build_cuda_linux.sh:46`、`build_hip_linux.sh:66`、`build_sycl_linux.sh:51`、`engine/spark/build_engine.sh:55`（以上 `${STRATA_CMAKE_EXTRA:-}` の未クォート展開）、`build_cuda_windows.py:173,80`（`.split()`）、`terminal/tools/hip/build_windows.bat:84`（`%STRATA_CMAKE_EXTRA%`）、`tools/packaging/shape_build.sh:23`（後述の shape 判定）。`tools/packaging/make_model_release.py:149` は手順書の文字列として名前を出すだけで読まない。

Strata は値の意味を解釈しない。有効・無効を決めるのは受け取る cmake で、未知の `-D` は無視され、不正な引数なら configure が失敗する。指定できるのは cmake のキャッシュ変数一般で、例は `-DSTRATA_GEOMETRY_FILE=<abs path>` / `-DSTRATA_GEOMETRY=<name>`（`engine/cmake/strata_geometry.cmake:3-4,11-12`）や `-DSTRATA_WINDOW_MAX_T=8`（`terminal/tools/hip/build_windows.bat:25`）。ビルドされるカーネルや選択ヘッダは変わるが、実行時挙動は変わらない。

## 値と判定

Strata 側の parse は無く、判定は「引数へどう分割されるか」と後述の shape 判定 1 箇所だけ。

- POSIX sh の 4 本は未クォート展開。空白区切りで複数引数になり、未設定と空文字はどちらも 0 個の引数（`${VAR:-}`）。`# shellcheck disable=SC2086` は分割を意図した抑止（`tools/packaging/build_cuda_linux.sh:43` など）。
- 値の中の引用符は再解釈されない。`STRATA_CMAKE_EXTRA='-DSTRATA_GEOMETRY_FILE="/a b/g.hpp"'` は 2 引数に割れる。クォート無し展開なので `*` などはパス名展開の対象になる。
- Python は whitespace 区切りの `.split()` で、未設定と `""` は同じ `[]`。batch は `%STRATA_CMAKE_EXTRA%` の素の置換で、未定義なら空（`terminal/tools/hip/build_windows.bat:84`）。
- 大文字小文字・数値妥当性・先頭文字の検査はない。`1` / `true` / `0` / 空はいずれも「cmake への引数列」としてのみ意味を持つ。

| 条件 | unset | 有効な値の例 | 無効・効果なしの例 |
|---|---|---|---|
| sh 4 本 | 引数 0 個 | `-DSTRATA_GEOMETRY_FILE=/abs/geo.hpp`、`-DA=1 -DB=2` | 空文字（0 個）、`-D` の無い語、値中の空白（2 引数に割れる） |
| Python | `[]` | 同上 | 同上（`""` は `[]`） |
| batch | 空 | 同上 | 同上。既存ビルドディレクトリでは読まれない |

Strata が値の中身を見る唯一の箇所は shape 判定 `case " ${STRATA_CMAKE_EXTRA:-} " in *-DSTRATA_GEOMETRY*)`（`tools/packaging/shape_build.sh:23-28`）。空白で挟んだ文字列への部分一致で大文字小文字を区別する。`-DSTRATA_GEOMETRY_FILE=...`、`-DSTRATA_GEOMETRY=...`、`-DSTRATA_GEOMETRY_XYZ=1` は当たり、`-dstrata_geometry=...` は当たらない。

## 有効になる条件

- 効くのはビルド時の configure だけで、出荷済み `strata` の起動・推論には影響しない。
- shape 判定は `SHAPE` が設定されているときだけ走る（`tools/packaging/shape_build.sh:15`）。`SHAPE` 未設定なら、extra が geometry を名指していても `shape_check` も `--shape` パッケージ化も行われない（同 `:29,33`）。
- `SHAPE` あり かつ extra に `-DSTRATA_GEOMETRY` を含む → スクリプトは `-DSTRATA_GEOMETRY=$SHAPE` を足さない（同 `:23-27`）。ヘッダ存在チェックは省略され、代わりにビルド後の `strata --geometry` が `SHAPE` と一致するかの検査だけが残る（同 `:32-36`）。
- `SHAPE` あり かつ extra に geometry 指定なし → `engine/include/strata/core/geometries/$SHAPE.hpp` が無ければ `exit 2`（同 `:25-26`）。
- `terminal/tools/hip/build_windows.bat` は `%BUILD_DIR%\build.ninja` が無いときだけ configure する（同 `:76`）。configure 済みなら extra を変えても再 configure されない。
- `tools/packaging/build_hip_linux.sh` は `VISION_ONLY` が空のときだけ engine を configure する（同 `:61`）。
- ピクチャリーダ (`strata-vision`) の configure には渡らない（`tools/packaging/build_cuda_linux.sh:58-59`、`tools/packaging/build_vision_windows.bat:54` は `STRATA_SYM_CMAKE` だけを読む）。

## 実行時の詳細

- 読み取り時期: スクリプト実行中に configure 行を組み立てる 1 回。sh 4 本は `shape_build.sh` を source した時点でもう一度参照する（`tools/packaging/build_cuda_linux.sh:39`、`engine/spark/build_engine.sh:46` など）。`static` のようなキャッシュは無く、実行中に値を変えても走っている configure には影響しない。
- 配置: arch・バックエンド・`-DSTRATA_BUILD_TESTS` などスクリプト固有の `-D` より後ろ。ただし sh 4 本では `$shape_cmake` と `$sym_cmake` がさらに後ろに来る（`tools/packaging/build_cuda_linux.sh:46`、`tools/packaging/build_hip_linux.sh:66`、`tools/packaging/build_sycl_linux.sh:51`、`engine/spark/build_engine.sh:55`）。同じ変数を重ねると後ろの値が使われるため、extra で `-DSTRATA_KEEP_SYMBOLS` は打ち消せず（`tools/packaging/symbols_build.sh:12-13`）、`-DSTRATA_GEOMETRY` は shape 判定側が自己抑制する。Python と batch では extra が最後（`build_cuda_windows.py:80`、`build_windows.bat:84`）。
- 子プロセス: sh 各本は extra をコマンド引数として cmake に渡すだけで、環境変数としての転送は制御しない。Python は configure 用 `env` を vision ビルドにも複製して渡すが（`tools/packaging/build_cuda_windows.py:201`）、vision 側の configure 行にこの名前は現れない。
- `BUILD.json`（`tools/packaging/build_cuda_linux.sh:73`）と `package_engine.py` の `--arch` / `--variant` はスクリプト変数から作られる（同 `:35-36,78-82`）。extra で `-DCMAKE_CUDA_ARCHITECTURES` を上書きすると、実際のマシンコードとパッケージ記載の arch が食い違い得る。

## ログと測定値

専用のログ・警告は無い。値は configure の出力に現れるだけ。

- `tools/packaging/build_cuda_windows.py:153` が configure 行全体を `+ ` 付きで stdout に出す。
- `tools/packaging/build_hip_linux.sh` は configure 出力を `$OUT/cfg.log` に落とし、失敗時は `build.status` に `ABORT engine configured failed (rc=..)` を残して `exit 1`（同 `:45-47,66-67`）。他の sh は `set -eu`（`tools/packaging/build_cuda_linux.sh:16` など）、batch は `|| exit /b 1` で打ち切る。
- 測定値は該当なし。

## 根拠

- `tools/packaging/build_cuda_linux.sh:41-46`（説明コメント、configure 行と extra の位置）
- `tools/packaging/build_hip_linux.sh:59-67` / `tools/packaging/build_sycl_linux.sh:41-51`（source 時期と configure 行）
- `engine/spark/build_engine.sh:46-55`（arm64 CUDA 版）
- `tools/packaging/build_cuda_windows.py:68-80,168-181,201-204`（`.split()`、末尾連結、vision への env 複製）
- `terminal/tools/hip/build_windows.bat:25,76-84`（設定一覧、`build.ninja` ガード、展開位置）
- `tools/packaging/shape_build.sh:12-30,32-37`（部分一致での自己抑制と `--geometry` 検査）
- `tools/packaging/symbols_build.sh:12-13`（後置される `-DSTRATA_KEEP_SYMBOLS=ON`）
