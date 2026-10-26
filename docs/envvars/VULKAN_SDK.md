# `VULKAN_SDK`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象は Strata 所有のセットアップコード。外部ツールがこの変数をどう解釈するかは対象外。

## 役割

`setup.py` が Vulkan backend の画像生成器 `sd-cli` をビルドするとき、既にある Vulkan SDK の場所を判定するために読みます。有効なディレクトリが指定されていれば、Strata は SDK をダウンロード・展開せず、`None` を返して既存の環境設定を使います。これは通常の Strata 推論エンジンの backend 選択ではなく、画像生成器のセットアップ経路に限られます。

## 値と判定

| 状態 | `vulkan_sdk()` の処理 |
|---|---|
| 未設定、空文字、または値が指すパスがディレクトリでない | SDK が使えるかを OS ごとの次の判定に進む。 |
| 値が指すパスがディレクトリ | `None` を返す。Strata はその値を検証して `VULKAN_SDK` を設定し直すことはしない。 |

値は `Path(have).is_dir()` で判定され、文字列の trim、展開、正規化はコード上で行いません。相対パスは呼び出し時の作業ディレクトリに対する `Path` として判定されます。

## 有効になる条件

この読み取りに到達するのは `build_image_engine("vulkan", ...)` が実際にビルドへ進み、`vulkan_sdk()` を呼ぶ場合です。画像生成器の実行ファイルと build stamp が一致して再利用される場合、`build_image_engine()` は先に return するため、この変数は読み直されません。Vulkan backend の選択自体は `--image-backend vulkan` などのセットアップ経路で行われます。

`VULKAN_SDK` が有効なディレクトリでも、その SDK のヘッダーや `glslc` の存在を Strata がここで検査するわけではありません。

- Linux では、環境変数の値が有効なディレクトリなら直ちに `None` を返します。そうでない場合でも、`glslc` が PATH 上にあり、`/usr/include/vulkan/vulkan.h` が存在すればシステムの開発ファイルを使います。
- Windows では、環境変数の値が有効なディレクトリでないと SDK の案内を表示して `fail()` します。
- Linux で上記いずれも使えない場合は、Strata が pin した LunarG SDK `1.4.363.0` を `third_party/vulkan-sdk/1.4.363.0/x86_64` に取得・展開します。この経路では指定値が無効でもエラーにはせず、自動取得へ進みます。

## 実行時の詳細

Vulkan 画像生成器のビルド時、既存の `VULKAN_SDK` ディレクトリを採用した場合は環境変数を変更せず、`cmake_build()` を呼びます。Linux の OS パッケージを採用する場合も同様です。

Strata が SDK を自動展開した場合は、プロセス内の `VULKAN_SDK` を展開先に設定し、SDK の `bin` を `PATH` の先頭に、`lib/VulkanLoader/lib` を `LD_LIBRARY_PATH` の先頭に追加します。CMake には SDK の `libvulkan.so`、include、`glslc` のパスを明示します。システムの Vulkan loader が見つからない場合、SDK loader のディレクトリを画像生成器の `lib_dirs` に保存し、後の起動設定へ渡します。

## 根拠

- `setup.py:4814-4826` — 画像生成器のビルド成果物を再利用する早期 return。
- `setup.py:4848-4858` — Vulkan backend から SDK 解決を呼び、SDK の CMake 設定と必要時の loader ディレクトリを作る。
- `setup.py:4769-4801` — `VULKAN_SDK` の読み取り、Linux/Windows の分岐、自動 SDK 展開と環境設定。
- `tools/image/qimage.py:31-35` — 自動取得経路が使う SDK version、URL、サイズ、SHA-256。
- `setup.py:8571` および `setup.py:4905-4912` — 画像 backend オプションと画像生成器を構成する呼び出し。
- `docs/IMAGES.md:53-67` — 画像 backend と、Linux で開発ファイルがない場合の SDK 自動取得に関する記述。
