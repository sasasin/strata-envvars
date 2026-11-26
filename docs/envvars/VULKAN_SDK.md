# `VULKAN_SDK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

これは Strata の通常の推論エンジン設定ではなく、セットアップ時に画像生成用 `sd-cli` を Vulkan backend でビルドする際の開発 SDK 検出・準備に使われる環境変数である。`terminal/setup.py` の `vulkan_sdk()` は値が指すパスがディレクトリかだけを調べる。ディレクトリなら Strata 独自の SDK 展開を省略し、Linux のシステム用開発ファイルも無ければ、固定バージョンの LunarG SDK を `third_party/vulkan-sdk` に展開して、現在の Python プロセスの環境変数と検索パスを更新する（`terminal/setup.py:5833-5865`）。

この処理へ進むのは `setup_images()` が画像生成を設定し、`build_image_engine()` の backend が `vulkan` の場合に限られる。画像生成を設定しない場合や別 backend では、この関数は呼ばれない（`terminal/setup.py:5982-6003`, `5900-5903`, `5940-5947`）。通常の backend 選択は GPU と OS によるが、`--image-backend` で選択を上書きできる（`terminal/tools/image/qimage.py:88-105`, `terminal/setup.py:5967-5975`, `11475-11476`）。

## 値と判定

`os.environ.get("VULKAN_SDK")` で文字列を読み、文字列の真偽値と `Path(have).is_dir()` のみ判定する。値の中身を数値・真偽値として parse したり、SDK 内のファイルを検証したりはしない（`terminal/setup.py:5837-5842`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 全 OS（Vulkan 画像エンジンのビルド経路） | SDK パスとしては採用しない。後続の OS 別判定へ進む | 空でない文字列で、その文字列が既存ディレクトリを指す場合（例: `/opt/vulkansdk`）は SDK が「ある」と判定 | 空文字列、存在しないパス、通常ファイルを指す値は「ある」と判定されない |

文字列の大文字小文字、空白、`0`/`1`/`true`/`false` 等には特別な意味がない。たとえば `VULKAN_SDK=0` は `0` という名前の既存ディレクトリがある場合にだけ「ある」と扱われる。空文字は未設定と同様に後続判定へ進む。パスがディレクトリであっても `include` や `bin/glslc` の存在・内容はこの判定では確認しない（`terminal/setup.py:5838-5842`）。

## 有効になる条件

- Strata セットアップで `--images qwen-image` を選び、確認を通過して画像エンジン構築へ進むこと。`--images no` または未指定なら画像構築を行わない（`terminal/setup.py:5982-6003`）。
- 選択 backend が `vulkan` であること。GPU/OS による自動選択のほか、`--image-backend vulkan` で指定できる（`terminal/setup.py:5967-5975`, `11475-11476`; `terminal/tools/image/qimage.py:88-105`）。
- `engine-image/sd-cli` と `BUILD.json` の backend・stamp が一致して既存ビルドが再利用される場合、`build_image_engine()` は早期 return し、`vulkan_sdk()` を呼ばない。したがって環境変数の判定や SDK 準備は再ビルド時だけ行われる（`terminal/setup.py:5905-5914`, `5940-5942`）。
- `VULKAN_SDK` が空でない既存ディレクトリを指す場合、関数は `None` を返して SDK 自動展開と OS 別 fallback を飛ばす。Strata はその値から CMake の `-D` パスを作らない。`cmake_build()` が通常の環境を継承して CMake を実行するため、環境変数自体は子プロセス環境に残る（`terminal/setup.py:5838-5840`, `5940-5947`, `6793-6817`）。ディレクトリ内の SDK が実際に使えるかはここでは検証しない。
- 値が unset・空・無効パスの場合、Linux/macOS 等では `glslc` が PATH から見つかり、かつ `/usr/include/vulkan/vulkan.h` が存在すればシステムファイルを使う扱いで `None` を返す（`terminal/setup.py:5841-5842`）。
- 上記いずれにも該当しない非 Windows 環境では固定 SDK を取得・展開し、Strata が `VULKAN_SDK` を設定する。Windows ではこの自動取得経路に入らず、SDK が認識できなければ setup を終了する（`terminal/setup.py:5843-5865`）。

## 実行時の詳細

`vulkan_sdk()` の呼び出し時に毎回環境を読み、関数内 cache はない。Python プロセス起動後に値を変えてから関数が呼ばれれば、その時点の値が判定される。関数が既存ディレクトリを認識すると元の値は変更しない。Linux 等の fallback で同梱 SDK を用意すると、Strata は `VULKAN_SDK` を `<repo>/third_party/vulkan-sdk/1.4.363.0/x86_64` に設定し、`PATH` の先頭に SDK の `bin`、`LD_LIBRARY_PATH` の先頭に `lib/VulkanLoader/lib` を追加する（`terminal/setup.py:5847-5864`）。

同梱 SDK を使うビルドでは、`build_image_engine()` は CMake に `Vulkan_LIBRARY`, `Vulkan_INCLUDE_DIR`, `Vulkan_GLSLC_EXECUTABLE` を `-D` 引数で明示する。システム SDK または既存の `VULKAN_SDK` ディレクトリを使う扱いでは、それらの引数を追加せず、Strata が `VULKAN_SDK` のパスから代替値を組み立てることもない（`terminal/setup.py:5940-5950`）。

同梱の gate ビルダー `terminal/tools/image/gate/build_sd.py` は入力の `VULKAN_SDK` を読み取らない。Vulkan build で `glslc` が PATH に見つからない場合に、作業 root 配下の SDK を準備し、子プロセス用 `env` 辞書の `VULKAN_SDK`, `PATH`, `LD_LIBRARY_PATH` と CMake 引数を設定する（`terminal/tools/image/gate/build_sd.py:72-73`, `91-115`, `120-124`）。

## ログと測定値

- 既存の `VULKAN_SDK` ディレクトリ、または Linux のシステム用 `glslc` とヘッダーが見つかった場合、この変数に関する成功ログは出ない（`terminal/setup.py:5838-5842`）。
- 同梱 SDK を設定した場合は `Vulkan SDK: {sdk}` を `[ok]` 付きで表示する（`terminal/setup.py:5860-5865`, `1039-1042`）。
- Windows で SDK を認識できない場合は `compiling the image generator for this GPU (Vulkan) needs the Vulkan SDK` とインストール案内を出し、setup は終了コード 1 で停止する（`terminal/setup.py:5843-5846`, `1049-1055`）。
- これはビルド準備用で、Strata の推論時に `VULKAN_SDK` を読む実装はこの checkout の全参照検索では確認できなかった。外部 CMake / Vulkan SDK 側の環境変数解釈はここでは記述しない。

## 根拠

- 環境変数判定、Linux/Windows の分岐、SDK 展開と環境設定: `terminal/setup.py:5833-5865`
- Vulkan backend のビルドと CMake 引数: `terminal/setup.py:5900-5964`
- 画像構築の呼び出し、CLI 選択肢: `terminal/setup.py:5982-6003`, `11471-11476`
- 自動 backend 選択と Vulkan 固定値: `terminal/tools/image/qimage.py:29-35`, `88-105`
- gate ビルダーの独立した環境設定: `terminal/tools/image/gate/build_sd.py:41-46`, `72-124`
