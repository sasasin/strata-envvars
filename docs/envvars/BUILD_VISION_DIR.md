# `BUILD_VISION_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象は Strata 所有ソース内の参照。実行時エンジンによる読み取りは見つからず、Linux CUDA 用のビルドスクリプト 2 件が読む。

## 役割

CUDA リリース用の画像 reader `strata-vision` をビルドする CMake binary directory を指定します。`packaging/build_cuda_linux.sh` は既定で `$repo/build-vision-$variant`、DGX Spark 用 `spark/build_engine.sh` は `$repo/build-vision-spark` を使います。どちらも `-S tools/vision -B "$vision_dir"` で CMake に渡し、成果物をそのディレクトリの `bin/strata-vision` から探します。

これはエンジンの実行時設定ではありません。実行時に `BUILD_VISION_DIR` を読み取る参照はなく、この変数自体が reader を有効化するわけでもありません。

## 値と判定

両スクリプトとも POSIX shell の `${BUILD_VISION_DIR:-既定値}` を使います。

| 環境値 | 選択されるディレクトリ |
|---|---|
| 未設定、または空文字 | スクリプトごとの既定値（上記） |
| 空でない値 | その文字列をそのまま使用。文字列の形式・ディレクトリの事前検証や正規化はしない |

数値変換や真偽値の解釈はありません。相対パスは、両スクリプトがリポジトリへ `cd` した後に CMake と成果物検査へ渡されるため、リポジトリ直下を基準に解決されます。空白を含む値は引用符付きで渡されます。

## 有効になる条件

- `packaging/build_cuda_linux.sh` は Linux x86_64 の CUDA 12/13 パッケージ作成経路で使用します。CUDA variant ごとに既定ディレクトリが変わります（`cuda12` / `cuda13`）。`BUILD_VISION` が未設定または空なら `1` とみなされ、値が厳密に `1` の場合だけ reader を configure/build します。
- `spark/build_engine.sh` は Linux ARM64 / CUDA 13 の DGX Spark ビルド経路です。こちらも `BUILD_VISION` が未設定または空なら `1`、厳密に `1` の場合だけ reader を configure/build し、成果物を出力フォルダーへコピーします。`packaging/build_cuda_linux_aarch64.sh` 経由の場合も環境から継承した `BUILD_VISION_DIR` がそのまま Spark スクリプトへ届きます。
- したがって `BUILD_VISION_DIR` を指定しても、別変数 `BUILD_VISION` が `1` 以外なら reader のビルドは行われません。x86_64 スクリプトでは、その場合も指定ディレクトリに以前の `bin/strata-vision` があれば後段でパッケージへコピーされ得ます。Spark スクリプトはコピーも `BUILD_VISION=1` の条件内です。
- いずれもスクリプト内で値を設定時に一度展開します。プロセス実行中に環境が変わっても再読込しません。子プロセスへの転送・上書きはなく、選択したパスを CMake の `-B` と成果物参照に使います。

## 実行時の詳細

x86_64 スクリプトは `BUILD_VISION=1` のとき `tools/vision` を CUDA・portable 設定で configure し、同じ GPU architectures を指定して `strata-vision` target を build します。後段は `"$vision_dir/bin/strata-vision"` がファイルとして存在すれば staging 領域にコピーし、`BUILD.json` に `vision_archs` を記録します。`BUILD_VISION` が `1` 以外でもこの存在確認は行います。

Spark スクリプトも ARM portable 設定で同じ target を build し、`BUILD_VISION=1` かつ成果物ファイルが存在するときだけ出力フォルダーへコピーして `BUILD.json` に `vision_archs` を記録します。`tools/vision/CMakeLists.txt` は target の runtime 出力先を `${CMAKE_BINARY_DIR}/bin` としています。

両ビルドスクリプトは `set -eu` を指定しています。reader の configure/build が失敗するとそこでスクリプトも失敗終了します。reader をビルドしない場合に成果物が見つからなくても専用エラーは出さず、コピーと `vision_archs` の記録を省略します。変数の読み取り自体はログ出力しません。指定パスが不正な場合の診断文言は CMake 等が出すもので、Strata 独自の検証・警告はありません。

## 根拠

- `packaging/build_cuda_linux.sh:14-23,33-46,53-58`: shell の既定値展開、repo への移動、`BUILD_VISION` 条件、CMake binary directory、成果物検査と packaging staging へのコピー。
- `spark/build_engine.sh:16-25,58-75,84-88`: Spark 側の既定値展開、repo への移動、reader build 条件と出力へのコピー。
- `packaging/build_cuda_linux_aarch64.sh:25-32`: `spark/build_engine.sh` の起動。`BUILD_VISION_DIR` を上書きせず、呼び出し元の環境が継承される。
- `tools/vision/CMakeLists.txt:96-102`: `strata-vision` target と `${CMAKE_BINARY_DIR}/bin` への出力設定。
- `packaging/ENGINE-COMPONENT.md:108-110`: x86_64 と Spark 向けの配布構成・ビルド経路の説明。`BUILD_VISION_DIR` 固有の説明はない。
