# `BUILD_VISION`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

ビルド時に Strata の画像 reader `strata-vision` を構築するかどうかを選ぶ変数です。対象は CUDA engine の Linux x86_64 release build (`tools/packaging/build_cuda_linux.sh`)、DGX Spark 向け Linux arm64 build (`engine/spark/build_engine.sh`)、および CUDA source Docker build (`tools/docker/Dockerfile.src`) です。実行時の engine 設定ではなく、生成・梱包される reader の有無に作用します。reader のない CUDA package は `package_engine.py` が許容し、text-only として扱います (`tools/packaging/package_engine.py:98-102`)。

Linux x86_64 と Spark のシェルでは `${BUILD_VISION:-1}` を文字列 `1` と比較します。値が空でない `1` のときだけ reader を configure/build します (`tools/packaging/build_cuda_linux.sh:54-60`, `engine/spark/build_engine.sh:67-73`)。Docker では `ARG BUILD_VISION=1` を `RUN` 内で文字列 `1` と比較し、build-arg で同じ選択をします (`tools/docker/Dockerfile.src:39-40,60-64`)。

## 値と判定

| 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux x86_64 `build_cuda_linux.sh` | `${VAR:-1}` により `1` として有効 | 文字列全体が `1`（例: `1`） | 空文字は既定値 `1` になる。それ以外はすべて無効（例: `0`, `01`, `true`, `TRUE`, ` 1`, `1 `） |
| Spark `build_engine.sh` 直接実行 | `${VAR:-1}` により `1` として有効 | 文字列全体が `1` | 空文字は既定値 `1` になる。それ以外はすべて無効 |
| Spark package wrapper `build_cuda_linux_aarch64.sh` | wrapper が `${BUILD_VISION:-1}` を子の `build_engine.sh` に渡すため有効 | 文字列全体が `1` | 空文字は wrapper で `1` に置換され有効。それ以外は無効 (`tools/packaging/build_cuda_linux_aarch64.sh:34`) |
| Docker `Dockerfile.src` | Docker `ARG` の既定値 `1` で有効 | 文字列全体が `1` | 明示的な空文字を含め、`1` 以外は無効 |

数値変換や真偽値 parse はせず、空白除去・大文字小文字変換もありません。Linux シェルの `${VAR:-1}` は unset と空文字を同じく既定値にする一方、Docker の `ARG` は既定値指定であり、build-arg として空文字を渡せば比較に失敗します (`tools/packaging/build_cuda_linux.sh:55`, `engine/spark/build_engine.sh:67`, `tools/docker/Dockerfile.src:40,60`)。

## 有効になる条件

- 変数を評価するのは上記のビルド経路だけです。OS / backend / build macro / server mode / CLI / model state による実行時判定はありません。Linux x86_64 と Docker の処理は CUDA reader を構築し、Spark script は arm64 Linux / CUDA 13 toolkit 用です (`tools/packaging/build_cuda_linux.sh:8,55-59`, `engine/spark/build_engine.sh:2-4,29-45,67-73`, `tools/docker/Dockerfile.src:52-64`)。
- `BUILD_VISION=1` でも、reader の CMake configure/build が失敗すれば `set -e` または Docker `set -e` によりその build は失敗します (`tools/packaging/build_cuda_linux.sh:16,55-60`, `engine/spark/build_engine.sh:17,67-73`, `tools/docker/Dockerfile.src:46,60-64`)。
- `BUILD_VISION` が無効でも、Linux x86_64 script は build をスキップした後、`$vision_dir/bin/strata-vision` が既にあれば stage にコピーします。既定の `vision_dir` は `$repo/build-vision-$variant` で、`BUILD_VISION_DIR` で変更できます。そのため既存の reader がある作業ツリーでは、無効指定だけで text-only package になるとは限りません (`tools/packaging/build_cuda_linux.sh:54-59,67-72`)。梱包時に reader が含まれていて `BUILD.json` の `vision_archs` が package の CUDA arch を網羅しない場合、`package_engine.py` は `--allow-stale-vision` なしでは拒否します (`tools/packaging/package_engine.py:100-119,192-195`)。
- Spark の build script は、reader build と出力先へのコピーの両方を `BUILD_VISION=1` でガードします。無効なら `$out` に reader をコピーせず、`BUILD.json` に `vision_archs` を記録しません (`engine/spark/build_engine.sh:67-73,75-87`)。
- Docker の reader build は `BUILD_VISION=1` のときだけ実行しますが、stage 作成時の copy は無条件で既存の `build-vision/bin/strata-vision` を確認します。通常の source build で reader がなければコピーされず、`BUILD.json` にも `vision_archs` は付きません (`tools/docker/Dockerfile.src:60-74`)。
- Windows builder (`tools/packaging/build_cuda_windows.py`) はこの変数を参照せず、`BUILD_VISION_DIR` 等を使います。ほかの backend や macOS の reader build に、この名前を使う根拠はありません。

## 実行時の詳細

これはビルドスクリプトが実行される間に shell parameter expansion / Docker `ARG` として評価されます。常駐プロセスの cache やリクエストごとの読み直しはなく、プロセス起動後の環境変更を扱うコードもありません。Linux x86_64 script では build の可否と後段の artifact copy は別々の条件であり、後者は `BUILD_VISION` を見ずにファイルの有無を確認します (`tools/packaging/build_cuda_linux.sh:55-60,67-72`)。Spark では wrapper から `BUILD_VISION` の値を子 script へ環境変数として渡します (`tools/packaging/build_cuda_linux_aarch64.sh:34`)。

reader がない CUDA package について、梱包コードは note `no picture reader in this CUDA package: the engine answers text only (the app says pictures need the reader)` を返します。CLI 経由の梱包では `package_engine.py` が `note: ` を付けて出力します (`tools/packaging/package_engine.py:98-102,192-195`)。これは Strata の梱包処理の説明であり、外部 reader や GPU driver の挙動を含みません。

## ログと測定値

`BUILD_VISION` 自体を理由にした警告やログは、これらの分岐にはありません。reader の build コマンドが失敗した場合は、そのコマンドの失敗で script / Docker build が止まります (`tools/packaging/build_cuda_linux.sh:55-60`, `engine/spark/build_engine.sh:67-73`, `tools/docker/Dockerfile.src:60-64`)。既存 reader が梱包対象に残った場合の arch 不一致は、`package_engine.py` が `refusing to package ...` で始まる `SystemExit` を出します (`tools/packaging/package_engine.py:110-117`)。測定値は扱いません。

## 根拠

- `tools/packaging/build_cuda_linux.sh:52-80` — reader の既定値、build 条件、build directory、既存 artifact の stage へのコピー、package 呼び出し。
- `engine/spark/build_engine.sh:17-27,67-87` — Spark build 条件、reader の build と条件付き copy、`BUILD.json` 記録。
- `tools/packaging/build_cuda_linux_aarch64.sh:15-35` — wrapper の既定値と子 script への転送。
- `tools/docker/Dockerfile.src:39-40,46-80` — Docker build arg の既定値、build 条件、stage への copy。
- `tools/packaging/package_engine.py:78-120,147-163,189-209,367-371` — package 内の reader 検査、reader 不在の note、arch mismatch の拒否、梱包。
