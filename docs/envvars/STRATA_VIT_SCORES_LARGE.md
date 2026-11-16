# `STRATA_VIT_SCORES_LARGE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 同梱の own vision tower が GPU attention の score buffer に使う「大きな画像向け」要素数 budget を、Mi 要素単位で上書きする診断用設定です。CUDA/HIP・Metal・SYCL の GPU 実装にあり、CPU tower や mtmd reader の score buffer を制御するものではありません。設定値は画像の特徴や attention 計算を直接変える値ではなく、attention の query chunk に確保する score/probability buffer の budget に反映されます。`tools/vision/own/vit_gpu.cu:459-464, 793-802, 1004-1008`、`tools/vision/own/vit_metal.mm:112-121, 251-262, 468-473`、`tools/vision/own/vit_sycl.cpp:287-298, 384-386, 478-479`。

`docs/DETAILS.md:984-1016` は画像 reader の選択と利用者向け画像設定を説明していますが、この診断用変数や score chunk budget は記載していません。以下は現行コードで確認できる処理だけを記します。

## 値と判定

3 backend とも GPU tower の `load()` 中に `std::getenv` で設定有無を調べ、設定されていれば `std::atol` で数値接頭辞を `long` に変換します。変換結果が 1 以上なら `kScoreElemsLarge = (size_t)v << 20` とし、単位は Mi 要素です。全体文字列の妥当性検査や上限 clamp はありません。したがって空文字・非数値・`0`・負数は既定値のまま、`1` は 1 Mi 要素、`1junk` は数値接頭辞の 1 として採用されます。`2.5` は `atol` が読む整数接頭辞の 2 として扱われます。前後の空白や符号も `atol` の変換規則に従います。`STRATA_VIT_SCORES_LARGE` の読み取り箇所: `tools/vision/own/vit_gpu.cu:1005`、`tools/vision/own/vit_metal.mm:469`、`tools/vision/own/vit_sycl.cpp:478`。

| backend / build | unset または変換値 < 1 | 正の値の既定値・変換後 | 無効例 |
|---|---|---|---|
| CUDA / HIP（`vit_gpu.cu`） | 512 Mi 要素 | 設定値 Mi 要素 | 空文字、`0`、`-1`、`true`、`0anything` |
| Metal（macOS、`vit_metal.mm`） | 256 Mi 要素 | 設定値 Mi 要素 | 空文字、`0`、`-1`、`true`、`0anything` |
| SYCL（`vit_sycl.cpp`） | 256 Mi 要素 | 設定値 Mi 要素 | 空文字、`0`、`-1`、`true`、`0anything` |

既定値は各実装のメンバー初期化で定まり、CUDA/HIP は `tools/vision/own/vit_gpu.cu:461-464`、Metal は `tools/vision/own/vit_metal.mm:114-118`、SYCL は `tools/vision/own/vit_sycl.cpp:292-298` にあります。

## 有効になる条件

- own vision tower の GPU backend がビルドされ、実行時に GPU tower が選択されること。CUDA/HIP は `vit_gpu.cu`、Metal は `vit_metal.mm`、SYCL は `vit_sycl.cpp` がそれぞれ build 条件に応じて組み込まれます（`tools/vision/own/CMakeLists.txt:13-18, 24-44, 46-54, 56-70, 120-163`）。CPU 経路にはこの読み取り処理がありません。
- 画像の patch 数 `N` が 16,384 を超えること。`N <= 16,384` では `kScoreElemsLarge` を選ばず、通常の `kScoreElems` が使われます（CUDA/HIP: `tools/vision/own/vit_gpu.cu:797-802`、Metal: `tools/vision/own/vit_metal.mm:259-262`、SYCL: `tools/vision/own/vit_sycl.cpp:384-386`）。
- `STRATA_VIT_SCORES` が有効な正数として読まれていないこと。この変数を `atoi` で読み、1 以上なら `scores_env=true` として全画像で通常の `kScoreElems` を選ばせるため、その場合 `STRATA_VIT_SCORES_LARGE` は読み取られていても chunk budget の選択に使われません（CUDA/HIP: `tools/vision/own/vit_gpu.cu:1003-1005, 801`、Metal: `tools/vision/own/vit_metal.mm:468-469, 260`、SYCL: `tools/vision/own/vit_sycl.cpp:477-478, 385`）。
- 対象 buffer の確保が成功すること。大きな budget で score buffer を確保できない場合、各 backend は通常の `kScoreElems` に戻して再確保します。fallback 先も確保できない場合はロードまたは encode が失敗します（CUDA/HIP: `tools/vision/own/vit_gpu.cu:815-827`、Metal: `tools/vision/own/vit_metal.mm:272-280`、SYCL: `tools/vision/own/vit_sycl.cpp:392-404`）。
- `strata-vision` では `--tower mtmd` が選択されている場合、この own tower 経路自体を通りません。`--tower own` は明示的に own を選び、`--tower auto` は対応する mmproj / GPU 条件に応じて own または mtmd を選びます（`tools/vision/strata_vision.cpp:94-113, 137-144, 161-170`）。

## 実行時の詳細

設定は `VitGpu::load()` が重みを読み込んだ後、work buffer の `size_buffers()` を最初に呼ぶ前に一度だけ読み、tower インスタンスの `kScoreElemsLarge` に保存します（CUDA/HIP: `tools/vision/own/vit_gpu.cu:895-896, 1001-1008`、Metal: `tools/vision/own/vit_metal.mm:368-373, 466-473`、SYCL: `tools/vision/own/vit_sycl.cpp:424-431, 474-479`）。プロセス実行中に環境変数を変更しても、そのインスタンスには反映されません。`size_buffers()` は `N > 16,384` かつ `scores_env` が false のとき large budget と通常 budget の大きい方を候補にし、必要な総 score 数で上限を切ります。また各 query chunk が最低 64 query 分になる条件も適用されるため、環境変数の値がそのまま確保要素数になるとは限りません（CUDA/HIP: `tools/vision/own/vit_gpu.cu:793-803`、Metal: `tools/vision/own/vit_metal.mm:259-262`、SYCL: `tools/vision/own/vit_sycl.cpp:384-387`）。

初回 buffer は reader の起動時に warm-up 用画像で確保され、さらに大きな画像を encode するときは `size_buffers(N)` が必要に応じて再確保します。いずれも load 時に保存した値を使います（`tools/vision/own/own_reader.cpp:121-124, 150-165`、CUDA/HIP: `tools/vision/own/vit_gpu.cu:1011-1022`、Metal: `tools/vision/own/vit_metal.mm:482-493`、SYCL: `tools/vision/own/vit_sycl.cpp:486-499`）。この変数を子プロセスへ転送する処理は見つかりません。`strata-vision` 自身がそのプロセス内で GPU tower を初期化します。

CUDA/HIP の `kScoreElemsLarge` は 512 Mi 要素（F16 buffer なら 1 GiB 相当）、Metal/SYCL は 256 Mi 要素（F16 buffer なら 512 MiB 相当）です。実際の buffer は score と確率を同じ F16 領域で扱いますが、確保量は画像サイズや query chunk の下限でも制約されます（`tools/vision/own/vit_gpu.cu:459-464, 793-803`、`tools/vision/own/vit_metal.mm:112-121, 259-262`、`tools/vision/own/vit_sycl.cpp:287-298, 384-387`）。

## ログと測定値

この変数自体の値、採用・拒否、または large-to-default fallback を通知する専用ログはありません。buffer 確保エラーは backend の一般的な GPU memory エラーになります。CUDA/HIP は `GPU memory: <CUDA/HIP error>`（`tools/vision/own/vit_gpu.cu:676-684`）、Metal は `GPU memory: no buffer of <bytes> bytes`（`tools/vision/own/vit_metal.mm:126-131`）、SYCL は `GPU memory: <exception>` または `GPU memory: out of device memory`（`tools/vision/own/vit_sycl.cpp:307-320`）を設定します。fallback の再確保にも失敗すると reader の起動エラーに包まれ、`--tower own` では stdout に `ERR cannot load the vision encoder ...` が出ます。`auto` で own reader を起動した場合、READY 前の失敗は stderr の `strata-vision: Strata's picture reader did not start (...); reading pictures with llama.cpp's reader` と mtmd reader への切替になります（`tools/vision/own/own_reader.cpp:92-100, 121-125`、`tools/vision/strata_vision.cpp:168-175`）。

## 根拠

- 全 backend の直接読み取りと `atol` 変換: `tools/vision/own/vit_gpu.cu:1004-1005`、`tools/vision/own/vit_metal.mm:469`、`tools/vision/own/vit_sycl.cpp:478`。
- 既定値、large budget の選択条件・計算: `tools/vision/own/vit_gpu.cu:461-464, 797-803`、`tools/vision/own/vit_metal.mm:114-118, 259-262`、`tools/vision/own/vit_sycl.cpp:292-298, 384-387`。
- `STRATA_VIT_SCORES` の優先: `tools/vision/own/vit_gpu.cu:1003-1005`、`tools/vision/own/vit_metal.mm:468-469`、`tools/vision/own/vit_sycl.cpp:477-478`。
- 大きな buffer の失敗時 fallback: `tools/vision/own/vit_gpu.cu:815-827`、`tools/vision/own/vit_metal.mm:272-280`、`tools/vision/own/vit_sycl.cpp:392-404`。
- tower / build 経路と起動時エラーの扱い: `tools/vision/own/CMakeLists.txt:13-70, 120-163`、`tools/vision/strata_vision.cpp:94-113, 137-175`、`tools/vision/own/own_reader.cpp:92-125, 150-168`。
