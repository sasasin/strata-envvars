# `HY4_VIT_PRELUDE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4_VIT_PRELUDE` は、Metal 版 Hy4-Flash の画像 ViT カーネルを実行時コンパイルするとき、Metal ソースの前に追加する文字列を指定する。Strata は値を真偽値や数値として解釈せず、`#define NO_GGML_COMMON 1` の直後に連結して `hy4_mpp.metal` と `hy4_vision.metal` のコンパイルへ渡す（`engine/src/hy4flash/metal/hy4_metal_vision.h:91-103`、`engine/metal/src/mtl_rt.mm:182-193`）。したがって、変数自体が画像経路を有効化するわけではなく、画像カーネルのコンパイル対象テキストを変える。

この読み取りは Metal 実装にある。オフラインの Metal runner は画像入力がある場合、serve は画像付き要求が来た場合に `VitMetal::load` を呼ぶ。Metal の画像テストプログラムも同じ関数を使う（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782`、`engine/src/hy4flash/metal/hy4_metal_serve.h:365-373`、`engine/src/hy4flash/metal/hy4_vision_test_metal.cpp:30-36`）。

## 値と判定

`getenv` で設定有無を調べ、設定されていればその値を文字列として前置文字列に連結する。値の内容・数値形式・大文字小文字・空白に対する検証や変換は Strata 側にない。空文字は `getenv` が非 null でも連結される文字数が 0 のため、未設定と同じコンパイル前置内容になる。空文字以外の任意の文字列がコンパイラへ渡されるが、妥当性や意味は Strata では判定しない（`engine/src/hy4flash/metal/hy4_metal_vision.h:100`）。

| 条件 | unset | 設定時に前置される内容 | Strata の値判定 |
|---|---|---|---|
| Metal の `VitMetal::load` | `#define NO_GGML_COMMON 1\n` のみ | 同じ define の後に環境変数の文字列をそのまま追加 | 変換・形式検査なし。空文字は unset と同じ内容。`0`、`1`、`true`、`false`、`0anything` もそれぞれ文字列として渡す |

## 有効になる条件

- Metal の `VitMetal::load` が呼ばれること。通常のオフライン実行では画像レコードがある場合に呼ばれ、serve では画像付き要求で初めて呼ばれる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1778`、`engine/src/hy4flash/metal/hy4_metal_serve.h:365-369`）。
- Metal 画像 ViT のビルド・実行経路であること。この値を読む箇所は `engine/src/hy4flash/metal/hy4_metal_vision.h` のみで、HIP と SYCL の同名画像コードにはこの変数の参照がない。
- 前置文字列を含む MSL がコンパイルできること。失敗時には `VitMetal::load` が失敗を返す（`engine/src/hy4flash/metal/hy4_metal_vision.h:99-103`、`engine/metal/src/mtl_rt.mm:219-226`）。
- CLI 引数や別環境変数による `HY4_VIT_PRELUDE` の優先順位・上書きはない。`HY4_VIT_GELU` は別の設定値として同じ `load` 内で読み取られ、Prelude 文字列を変更しない（`engine/src/hy4flash/metal/hy4_metal_vision.h:97-100`）。

## 実行時の詳細

`VitMetal::load` は既に `loaded` なら直ちに成功を返すため、各 `VitMetal` インスタンスの最初のロード時だけコンパイルと環境変数読み取りに進む（`engine/src/hy4flash/metal/hy4_metal_vision.h:92-100`、`123-126`）。環境変数は関数内に cache されないが、`load` の成功後に同じインスタンスで環境を変更しても再読込・再コンパイルはされない。serve の `venc` はインスタンスを保持し、画像付き要求の処理でロードするため、その後の要求は同じコンパイル済みライブラリを使う（`engine/src/hy4flash/metal/hy4_metal_serve.h:292-296`、`365-373`）。

`compile_try` は受け取った前置文字列に改行と Metal 標準ヘッダーを続け、指定されたソースファイルを連結してコンパイルする。コンパイル失敗時は `-1` とコンパイラの説明を返し、画像側は `err` に `vision kernels: ` と最大 400 文字の説明を設定する（`engine/metal/src/mtl_rt.mm:182-193`、`219-226`、`engine/src/hy4flash/metal/hy4_metal_vision.h:99-103`）。

## ログと測定値

成功時は stderr に `[vision] shard %.2f GB mapped, kernels compiled, %.2f s` が出る（`engine/src/hy4flash/metal/hy4_metal_vision.h:123-126`）。このログは Prelude が未設定かどうかを表示しない。

前置文字列を含むカーネルのコンパイルに失敗した場合、オフライン runner は stderr に `images: vision kernels: ` とエラー説明を出して終了コード 1 を返す。`hy4-vision-test-metal` は stderr に `load: vision kernels: ` を出して終了コード 1 を返す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1776-1780`、`engine/src/hy4flash/metal/hy4_vision_test_metal.cpp:32-36`）。serve では stdout のプロトコル応答として `ERR image: vision kernels: ...` を返し、その要求の処理を続ける（`engine/src/hy4flash/metal/hy4_metal_serve.h:365-370`）。コンパイル成功後は同じライブラリが使われ、Prelude による生成結果等の差を測定した記載は `docs/DETAILS.md` を含む確認した Strata 資料には見つからなかったため、性能・出力への影響はここでは断定しない。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_vision.h:91-103` — 読み取り、前置文字列の生成、コンパイル失敗の伝播。
- `engine/src/hy4flash/metal/hy4_metal_vision.h:123-126` — 成功後のロード状態とログ。
- `engine/metal/src/mtl_rt.mm:182-193`、`219-226` — 前置文字列とソースの連結、コンパイル失敗の返却。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782`、`engine/src/hy4flash/metal/hy4_metal_serve.h:292-304`、`365-373` — オフライン画像経路と serve の遅延ロード・失敗応答。
- `engine/src/hy4flash/metal/hy4_vision_test_metal.cpp:30-36` — 同じロード関数を使う Metal 画像テストプログラム。
