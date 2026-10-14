# `STRATA_QI_OLD_QKV`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象は Strata 所有ソース。外部 stable-diffusion.cpp / ggml の内部動作は対象外。

## 役割

Strata 同梱の Qwen-Image-2.1 native runner が使う Q/K/V 後処理 CUDA/HIP カーネルの選択を切り替えます。環境変数が未設定で、関数の形状条件も満たす場合は、8 head を1 block 内で処理する `k_qkv_post_w` を選びます。変数が設定されていると、その経路を抑止して従来の `k_qkv_post` に戻します。

これは Strata の通常のテキスト生成エンジンの設定ではありません。画像生成用 `sd-cli` に組み込まれた native Qwen-Image-2.1 runner のみが読む開発・調整用フックです。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 形状条件を満たせば warp-per-head カーネルを選択 |
| 空文字を含む、何らかの文字列を設定 | 設定有りとして warp-per-head カーネルを抑止 |

値の内容、数値、先頭文字、大文字小文字は調べません。`getenv("STRATA_QI_OLD_QKV") != nullptr` の有無だけを分岐に使うため、`0`、`false`、空文字でも設定すると抑止されます。無効値という概念や値の parse、fallback はありません。fallback 先は同じ関数内の `k_qkv_post` です。

## 有効になる条件

- `tools/image/sdcpp_native` のネイティブ runner が stable-diffusion.cpp に適用され、CUDA または HIP ビルドで組み込まれている必要があります。Strata の画像セットアップコードはこの native runner を CUDA/HIP 用として扱います。
- stable-diffusion.cpp の Qwen-Image-2.1 native runner が選択され、モデル計算で `qi21_qkv_post()` が呼ばれる必要があります。Strata サーバー経由では画像設定の `native` が有効な場合に限って `qwen_image_2_1_native=1` をモデル引数へ追加する経路です。
- 未設定時に高速側を選ぶには、さらに `qlo == nullptr`、`H % 8 == 0`、`ld % 4 == 0` が必要です。どれかを満たさなければ変数の設定状態にかかわらず従来カーネルです。
- native runner は現在 `H=32`、`D=128`、`C=4096` を使い、後処理呼び出しには投影元 stride `ldq` を渡します。結合 QKV 投影時は `ldq=3*C`、個別投影時は `ldq=C` です。いずれも `ld % 4 == 0` を満たします。
- WMMA attention 用の q-split 残差 `qlo` を渡す場合は、変数が未設定でも warp-per-head 経路を使いません。このときは従来カーネルが q の高位半分に加えて低位半分も格納します。

## 実行時の詳細

native runner は各 transformer layer の後処理で `qi21_qkv_post()` を呼びます。関数内では呼び出しごとに `getenv()` を行い、static cache はしません。したがって、通常の1回の画像計算中は同じ環境を見ますが、プロセス実行中に環境を書き換えれば後続の呼び出しでは再評価されます（コード上の読み取り動作）。

warp-per-head 側は1 block 256 thread で8 headを処理し、Q/K の RMSNorm、RoPE、Q/K/V の出力格納を行います。従来側は grid `(T,H)`、1 head あたり1 block で同種の後処理を行います。いずれも関数に渡された同じテンソルとパラメータを使います。変数設定時に出力数値が一致することや性能差があることは、このコードだけからは断定できません。

カーネル起動後、関数は `cudaGetLastError()` が成功なら `0`、それ以外なら `2` を返します。`blocks_pass()` は失敗時に `Qwen Image 2.1 native: a kernel failed (%d)` を警告出力して失敗を返し、呼び出し元は `the image pass failed` として native runner を無効化して stock runner に切り替えます。この環境変数自体によるログ出力はありません。

## 根拠

- `tools/image/sdcpp_native/qi21-native.cu:598-624` — 環境変数の有無、3つの高速側条件、両カーネルの起動、戻り値。
- `tools/image/sdcpp_native/qi21-native.cu:113-144` — 従来カーネルの処理と qlo 格納。
- `tools/image/sdcpp_native/qi21-native.cu:146-189` — warp-per-head カーネルのブロック構成と後処理。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:49-60, 332-367, 441-442, 571-574` — native runner のモデル寸法、prefix 判定、qlo 条件、各 layer からの呼び出し。
- `tools/image/sdcpp_native/apply.py:1-10, 27-45, 49-51, 63-70` — pinned stable-diffusion.cpp への組み込みと CUDA/HIP build 条件。
- `tools/image/qimage.py:169-199`、`serve/images.py` — native runner の対象 backend とサーバー設定の扱い。
- `docs/IMAGES.md:3-7, 22-24, 32-38` — 画像機能と CUDA/HIP backend の概要。`STRATA_QI_OLD_QKV` の値や挙動は記載されていません。
