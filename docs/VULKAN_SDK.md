# `VULKAN_SDK`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリや Vulkan driver 自身が環境変数を使う動作は対象外。

## 役割

Strata のセットアップが、画像生成用 `sd-cli` を Vulkan backend で新規コンパイルするときに Vulkan SDK の場所を確認します。環境変数が有効なディレクトリを指す場合は「システム側の SDK を使う」と判断し、Strata 自身は SDK パスやビルド定義を追加しません。環境変数が使えず Linux の開発ファイルも見つからない場合、Strata は固定版 LunarG SDK をリポジトリ内に展開し、ビルド子プロセス用の環境変数を設定します。

## 値と判定

| `VULKAN_SDK` の状態 | Strata の判定 |
|---|---|
| 未設定または空文字 | SDK ディレクトリとして使わず、次に OS の開発ファイルを確認する |
| 非空で、その値をパスとした場所がディレクトリ | SDK があると扱い、`vulkan_sdk()` は `None` を返す |
| 非空だが、その場所がディレクトリでない | SDK がないものとして次の確認へ進む |

値の文字列比較、数値変換、大小文字変換はありません。非空ディレクトリの内部に `include` や `bin/glslc` があるかも、この環境変数の判定時には確認しません。値の前後の空白も除去しません。

根拠: `setup.py:3082-3091`。

## 有効になる条件

- `setup_images()` が `--images qwen-image` を処理し、利用者がモデルのダウンロードと画像生成設定を承諾した場合に画像エンジンのビルドへ進みます。`--images` が未指定または `no` の場合、この変数は読み取られません（`setup.py:3203-3218`）。
- 選択 backend が `vulkan` の場合に限り、`build_image_engine()` は `vulkan_sdk()` を呼びます（`setup.py:3161-3168`）。他 backend ではこの変数を読みません。
- 既存の `engine-image/sd-cli` と `BUILD.json` が現在の backend/pin に一致する場合、ビルド処理は早期 return します。この場合も `vulkan_sdk()` を呼ばず、環境変数の値は評価されません（`setup.py:3131-3139`）。
- Windows では、環境変数が既存ディレクトリを指さない場合、Strata は `third_party` の展開先を探さず、LunarG SDK のインストールを案内して失敗します。Linux でのみ同梱 SDK の自動取得・展開へ進みます（`setup.py:3092-3108`）。

## 実行時の詳細

新規 Vulkan ビルドでは、まず `VULKAN_SDK` が非空でディレクトリかを見ます。該当すれば `None` を返すため、Strata は `Vulkan_LIBRARY`、`Vulkan_INCLUDE_DIR`、`Vulkan_GLSLC_EXECUTABLE` の CMake 引数を追加しません。ここで Strata が実行するのはパスの有無の判定までです（`setup.py:3087-3089,3161-3168`）。

環境変数を使えない Linux では、`glslc` が PATH 上にあり、かつ `/usr/include/vulkan/vulkan.h` が存在すれば、システムの開発ファイルを使う経路として `None` を返します（`setup.py:3090-3091`）。どちらかが欠けると、固定版 `1.4.363.0` の SDK アーカイブを取得し、定義済みのサイズと SHA-256 を検証して `third_party/vulkan-sdk/1.4.363.0/x86_64` に展開します。展開先に `bin/glslc` が既にあれば再取得を省略します（`setup.py:3096-3108`, `tools/image/qimage.py:29-35`）。

自動展開した場合、Strata は現在のセットアッププロセス内で `VULKAN_SDK` をその SDK ディレクトリに設定し、SDK の `bin` を `PATH` の先頭に、SDK の Vulkan loader ディレクトリを `LD_LIBRARY_PATH` の先頭に追加します。その後 CMake に SDK の loader、headers、`glslc` の場所を渡します。`vulkan_sdk()` は `sdk` を返します（`setup.py:3109-3114,3161-3172`）。これらはセットアップが起動するビルドに向けた設定であり、Strata サーバーの起動時に `VULKAN_SDK` を読む実装は見つかりませんでした。

## 観測できる結果

自動展開経路では `Vulkan SDK: <path>` を表示します（`setup.py:3113`）。Windows で SDK が見つからない場合は、SDK のインストールと setup の再実行、または `--image-backend cpu` を案内して失敗します（`setup.py:3092-3095`）。Linux の SDK ダウンロードは `tools/image/qimage.py` に記録された URL、サイズ、SHA-256 を使います。ドキュメントも、Linux では開発ファイルがない場合に SDK を `third_party/` へ展開し、Windows では SDK を先にインストールする手順を説明しています（`docs/IMAGES.md:36-39`）。

## 根拠

- 読み取り・fallback: `setup.py:3082-3114`
- Vulkan backend のビルド適用: `setup.py:3127-3185`
- 画像セットアップからの呼び出し: `setup.py:3203-3227`
- SDK の固定版・アーカイブ情報: `tools/image/qimage.py:29-35`
- 利用者向け画像生成説明: `docs/IMAGES.md:22-39`
