# `STRATA_GGML_COMMON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの開始時状態は `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Apple Silicon 向け Metal runtime が、実行時に Metal カーネルへ読み込む `ggml-common.h` のファイルパスを指定します。CUDA/HIP/SYCL の環境変数としては使われていません。Metal の `Context` を生成するときにパスを選び、その後 `compile()` が必要なカーネルソースの先頭にファイル内容を追加します。

## 値と判定

| 状態 | Strata の処理 |
|---|---|
| 未設定 | `<実行ファイルの場所>/metal/ggml-common.h` が存在すればそのパスを使う。なければ Metal build 時に埋め込んだ `third_party/ggml/ggml-common.h` のパスを使う。 |
| 設定あり（空文字を含む） | 環境変数の文字列をそのままパスとして採用する。空文字は未設定扱いにならず、空パスになる。 |
| 設定あり（非空） | 文字列全体をパスとして使う。数値・真偽値への変換、形式検査、範囲制限、CLI による上書きはない。 |

環境変数で指定したパスは、存在確認や package/default path への fallback をせず、`read_file()` に渡されます。読み取りに失敗すると stderr に `mtl: cannot read <path>` を出して `exit(2)` します。空文字の場合、共通ヘッダーの挿入条件が偽となるためファイルを開きません。代わりのパスも選びません。

## 有効になる条件

この読み取りは `metal/src/mtl_rt.mm` の `Context` に実装され、macOS 専用の `metal/` CMake build が対象です。CMake は `STRATA_GGML_COMMON_DEFAULT` に Strata checkout 内の `third_party/ggml/ggml-common.h` のパスを埋め込みます。runtime ライブラリ、Metal engine の kernel library、および `strata_ds4` 用の runtime object に同じ default 定義を渡しています。

パスが選ばれても、全てのカーネル compile で共通ヘッダーが使われるわけではありません。`compile()` はパスが空でなく、かつ prelude に `NO_GGML_COMMON` が含まれない場合だけヘッダーを追加します。たとえば `Window` の主な quant/MoE kernel library は既定 prelude で compile されるため挿入対象ですが、GDN、QSA、sampling、PLE など `NO_GGML_COMMON` を指定する library では対象外です。

## 実行時の詳細

`Context` の構築時に `resource("STRATA_GGML_COMMON", ...)` が `std::getenv()` を呼びます。ここで選んだ文字列は `ggml_common_path` に保持され、以後の compile はこの保存値を使います。したがって、Context 構築後にプロセス環境を変更しても、この Context のパス選択は再評価されません。Strata 側に CLI 引数、設定ファイル、他の環境変数との優先順位はありません。

実行ファイル横の package fallback の存在確認には `stat()` を使います。環境変数が設定済みなら、この package fallback の確認処理には進まず、環境値が優先されます。既定で選ばれた path または環境指定 path のファイルを読めないと `read_file()` が終了コード 2 でプロセスを終了します。ファイルを読めても Metal source compile が失敗した場合は `mtl: compile failed (<device>, macOS <version>; <kernel>):` と compiler の説明を stderr に出し、終了コード 3 で終了します。後者のログは Metal compile 一般の失敗経路です。

## 根拠

- `metal/src/resource_path.h:27-40,43-54` — 実行ファイル directory の解決、package resource の存在確認、環境変数→package→compiled-in path の選択順序。
- `metal/src/mtl_rt.mm:292-316` — Metal `Context` の初期化時に `STRATA_GGML_COMMON` を読み、パスを保存する箇所。
- `metal/CMakeLists.txt:16-18,29-39,121-127,155-159` — macOS 限定 build と、runtime/engine/DS4 runtime への compiled-in default path 定義。
- `metal/src/mtl_rt.mm:32-40,331-360` — ファイル読み込み失敗の stderr・終了コード、空でない path と `NO_GGML_COMMON` による挿入条件、Metal compile failure のログ・終了コード。
- `metal/src/engine/window.cpp:581-587,2497-2500` — `Window` の通常 library compile と `NO_GGML_COMMON` を指定する compile の例。
- `metal/src/mtl_rt.h:98-103,138-139` — compile API と Context 内の保持フィールド。
