# `METAL_CPP_DIR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`METAL_CPP_DIR` は、Metal エンジンのビルド時に metal-cpp ヘッダーのディレクトリを指定する値です。Strata の実行時に読む環境変数ではなく、確認できた環境値の読み取り箇所は macOS 用パッケージスクリプト `tools/packaging/mac/build_engine.sh` です。同スクリプトは値を CMake の `METAL_CPP_DIR` cache 変数に渡し、Metal プロジェクトは `Metal/Metal.hpp` の存在確認と include directory の登録に使います（`tools/packaging/mac/build_engine.sh:44,60-66`; `engine/metal/CMakeLists.txt:82-94`）。

## 値と判定

シェルの `${METAL_CPP_DIR:-$HOME/strata-mac/metal-cpp}` により、未設定または空文字なら `$HOME/strata-mac/metal-cpp` が使われます。空でない値は文字列としてそのまま `-DMETAL_CPP_DIR=...` に渡されます。数値や真偽値としての parse、大小比較、文字列の正規化はありません。パスに空白があっても代入と CMake 引数は引用されています（`tools/packaging/mac/build_engine.sh:44,64`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `tools/packaging/mac/build_engine.sh` の `engine` stage で CMake 構成 | `$HOME/strata-mac/metal-cpp` | 選択されたディレクトリ内に `Metal/Metal.hpp` が存在するパス | 空文字は unset と同じ既定値。`0`、`true`、存在しないパスなど、指定先に `Metal/Metal.hpp` がない値は無効 |
| `engine/metal/CMakeLists.txt` を直接構成し、同名の CMake cache 値を渡さない場合 | CMake の既定値は空文字 | CMake の `METAL_CPP_DIR` cache 値が指す先に `Metal/Metal.hpp` が存在 | 空値またはそのファイルがない値 |

後者は CMake の cache 変数の扱いであり、ソースに `$ENV{METAL_CPP_DIR}` による直接の環境参照はありません。シェル環境変数を同プロジェクトへ結び付けるコードは、パッケージスクリプトの明示的な `-D` 引数です（`engine/metal/CMakeLists.txt:83-86`）。

## 有効になる条件

- `tools/packaging/mac/build_engine.sh` の `engine` stage を実行すること。スクリプトは Metal パッケージ用で、Metal CMake プロジェクトは `APPLE` 以外の構成を fatal error で拒否します（`tools/packaging/mac/build_engine.sh:2,60-66`; `engine/metal/CMakeLists.txt:18-20`）。
- 指定先に `Metal/Metal.hpp` があること。なければ CMake は `strata metal: METAL_CPP_DIR is not set: the device runtime and the engine are not built` を status 出力して早期 return し、Metal runtime と engine の target を定義しません（`engine/metal/CMakeLists.txt:82-94,103-110`）。
- `STRATA_METAL_ENGINE` が `ON` であること。ヘッダーが見つかった後でも、この CMake option が `OFF` なら同じく早期 return します（`engine/metal/CMakeLists.txt:103-110`）。パッケージスクリプトはこの option を上書きしていません（`tools/packaging/mac/build_engine.sh:64`）。
- metal-cpp パスが有効な場合、そのディレクトリは `strata_gpu_metal` の system public include directory になります。runtime、host、kernel libraries を経て `strata` executable が構成されます（`engine/metal/CMakeLists.txt:89-99,154-177`）。

## 実行時の詳細

この値はプロセス起動後の Strata engine では読み直されません。パッケージスクリプト起動時にシェルが環境から値を展開し、`engine` stage の CMake 構成時に `-D` 引数として渡します。その後は CMake cache の configure-time 値です。`engine` stage では既存の `$WORK/metal-build` を削除してから configure するため、このスクリプト経由の実行では前回の cache 値を引き継ぎません（`tools/packaging/mac/build_engine.sh:44,60-66`）。

環境値の代入自体は stage 判定前に行われますが、CMake へ渡されるのは `engine` stage を選んだ場合だけです。他の stage のみを実行するとき、この値によるビルド処理はありません（`tools/packaging/mac/build_engine.sh:41,44,60-75`）。未設定・空文字ならシェル側既定値を渡します。非空の無効パスは既定値へ fallback せず CMake に渡され、CMake の早期 return 後にスクリプトは `ninja ... strata` を実行します。configure 時点で target が作られていないためこの build 段階は成功せず、スクリプトは `metal-build.log` の末尾を表示して終了コード 1 で終了します（`tools/packaging/mac/build_engine.sh:64-66`; `engine/metal/CMakeLists.txt:84-86,176-177`）。

`engine/metal/setup_mac.py` の setup 経路は、既存の `engine/third_party/metal-cpp/Metal/Metal.hpp` を調べ、なければ pinned zip を取得・展開して、そのパスを CMake に明示します。このコードに `METAL_CPP_DIR` 環境変数の読み取りはありません（`engine/metal/setup_mac.py:85-100,129-146`）。 GitHub Actions の `.github/workflows/metal-build.yml` と `.github/workflows/backends.yml` にも `-DMETAL_CPP_DIR=...` の指定がありますが、どちらも CMake cache 値を直接設定しており、この環境変数を読む箇所ではありません。`docs/history/` の参照は履歴資料です（`.github/workflows/metal-build.yml:43`; `.github/workflows/backends.yml:191`）。

## ログと測定値

パスの `Metal/Metal.hpp` が存在しないとき、CMake は上記の status 文言を出力します。通常の configure/build 成功を示す専用ログや runtime ログは、この変数に関しては確認できません。パッケージスクリプト経由では、その後の Ninja build が失敗すると `metal-build.log` の末尾 30 行を表示し、終了コード 1 になります（`engine/metal/CMakeLists.txt:84-86`; `tools/packaging/mac/build_engine.sh:64-66`）。性能・正確性などの測定値はこのビルドパス変数に該当しません。

## 根拠

- `tools/packaging/mac/build_engine.sh:44,60-66` — 環境値の unset/empty fallback、engine stage の CMake への転送、Ninja 失敗処理。
- `engine/metal/CMakeLists.txt:18-20,82-94` — Apple platform guard、CMake cache 既定値、ヘッダー存在判定、未成立時の status/return、include path。
- `engine/metal/CMakeLists.txt:103-110,154-177` — engine option、runtime から `strata` target までの構成。
- `engine/metal/setup_mac.py:85-100,129-146` — setup 経路での独立したヘッダー取得と CMake 引数設定。
