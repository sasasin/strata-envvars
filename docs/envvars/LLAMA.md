# `LLAMA`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`LLAMA` は Linux AMD/HIP のパッケージ用ビルドスクリプト `packaging/build_hip_linux.sh` が読む、llama.cpp checkout のパス指定です。空でなければ、エンジン用 ggml の選択値 `STRATA_GGML_DIR` と、画像 reader 用 CMake の `LLAMA_DIR` に変換して渡します。空または未設定なら、初回構成時は Strata に同梱されたソースを使います。これは Strata 実行ファイルが読む環境変数ではなく、このスクリプトを実行するときのビルド設定です（`packaging/build_hip_linux.sh:21-25,60-80`）。

## 値と判定

スクリプトは Bash の `${LLAMA:-}` で値を取り込み、その後 `[ -z "$LLAMA" ]` で空かどうかだけを判定します。`:-` により未設定と空文字はどちらも空になります。空でなければ値をパス文字列としてそのまま CMake に渡し、`LLAMA` 自体について数値・真偽値・存在確認・空白除去・パス正規化はしません（`packaging/build_hip_linux.sh:21-25,71-80`）。

| 条件 | 未設定 | 非空で有効になる値 | 空またはこのスクリプトで別扱いにならない値 |
|---|---|---|---|
| `packaging/build_hip_linux.sh` を Bash で実行 | 空と同じ。初回 CMake 構成では同梱ツリーを使う | `../llama.cpp` のような checkout パス。`0` や空白だけの値も非空なので override として転送される | `LLAMA=''` は未設定と同様。`true` / `false` も真偽値として解釈されず、それぞれ文字列のパスとして転送される |

`LLAMA` が非空でも、値が有効な checkout を指すかはこのシェルスクリプトでは検証しません。CMake の構成・ビルドがそのパスを扱い、失敗時は通常のビルド失敗経路に入ります（`packaging/build_hip_linux.sh:63-85`; `cmake/strata_ggml.cmake:8-13`; `tools/vision/CMakeLists.txt:18,122`）。

## 有効になる条件

- この環境変数を読むのは `packaging/build_hip_linux.sh` です。他の実行経路がこの名前の環境値を参照する箇所はありません。`LLAMA` という名前の他の参照は、Windows スクリプト内で `STRATA_GGML_DIR` から作るローカル変数か、CMake 関数引数です（例: `tools/hip/build_windows.bat:94-99`, `cmake/strata_ggml_tq_overlay.cmake:20-23`）。
- エンジン構成は `VISION_ONLY` が空のときだけ行われます。このとき非空の `LLAMA` は `-DSTRATA_GGML_DIR=...` として `cmake -S .` に渡されます。`STRATA_CMAKE_EXTRA` はその引数より後ろに追加されるため、同じ変数を含む CMake 引数を指定すればエンジン側の指定を後から変えられます（`packaging/build_hip_linux.sh:60-68`）。CMake は非空の `STRATA_GGML_DIR` を ggml の root とし、空なら `third_party/strata-ggml` を選びます（`cmake/strata_ggml.cmake:6-13`）。
- `VISION_ONLY` の有無にかかわらず、このスクリプトは CPU reader と HIP reader の構成・ビルドへ進みます。非空の `LLAMA` は両方へ `-DLLAMA_DIR=...` として渡され、空なら `tools/vision/CMakeLists.txt` の同梱 `third_party/strata-llama` の既定値が使われます（`packaging/build_hip_linux.sh:60-85`; `tools/vision/CMakeLists.txt:18-20,122`）。
- `OUT` の下に既存の CMake build directory/cache がある場合、スクリプトが空値のときに `-DSTRATA_GGML_DIR` / `-DLLAMA_DIR` を渡さないため、以前の構成で保存された値が残り得ます。したがって空または未設定でも、再利用 build directory では同梱ツリーが選ばれるとは限りません。明示的な非空値はそれぞれの `-D` として構成コマンドに渡されます（`packaging/build_hip_linux.sh:24-25,63-65,71-81`; `cmake/strata_ggml.cmake:8-13`; `tools/vision/CMakeLists.txt:18`）。
- この設定は Linux HIP パッケージビルド経路に限られます。モデル状態、生成時 CLI、サーバーモード、GPU の実行時選択を `LLAMA` が変える読み取り箇所はありません。

## 実行時の詳細

環境変数の読み取りはスクリプト起動時、`set -u` の直後のシェル展開で一度行われ、以後はシェル変数 `LLAMA` が使われます。起動後の環境変更を再読込する処理はありません。プロセス起動後の Strata 実行ファイルへの引き継ぎもなく、値は CMake configure のコマンドライン引数に変換されます（`packaging/build_hip_linux.sh:21-25,63-80`）。

エンジン用 CMake 構成は `OUT/b`、画像 reader は `OUT/bv` と `OUT/bh` に構成されます。`VISION_ONLY` が非空の場合はエンジン構成・ビルドを飛ばしますが reader の構成には `LLAMA` が使われます（`packaging/build_hip_linux.sh:29,60-85`）。

## ログと測定値

`LLAMA` 専用のログや値の警告はありません。構成ログは `$OUT/cfg.log`、`$OUT/cfg-vision.log`、`$OUT/cfg-vision-hip.log` にリダイレクトされます。各 configure/build の終了コードが非ゼロなら `chk` が `$OUT/build.status` に `ABORT ... failed (rc=...)` を記録してスクリプトを終了します。HIP reader が生成されなかった場合は `ABORT no strata-vision-hip` を記録し、HIP reader の build log の末尾も status に追記します（`packaging/build_hip_linux.sh:44-47,63-85`）。

## 根拠

- `packaging/build_hip_linux.sh:21-25` — シェルでの取り込み、未設定・空文字の扱い、エンジン用 `STRATA_GGML_DIR` 引数。
- `packaging/build_hip_linux.sh:60-85` — `VISION_ONLY` 分岐、CMake 引数の組み立て、engine / CPU reader / HIP reader の構成と失敗処理。
- `cmake/strata_ggml.cmake:6-13` — `STRATA_GGML_DIR` の cache 変数と同梱 ggml への fallback。
- `tools/vision/CMakeLists.txt:18-20,122` — `LLAMA_DIR` の同梱既定値と llama.cpp tree の追加。
