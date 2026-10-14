# `STRATA_QI_QSPLIT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリ自体の環境変数動作は対象外。

## 役割

Strata 同梱の Qwen Image 2.1 ネイティブ DiT runner が WMMA attention を使うとき、fp16 に丸めた query の高位値だけでなく、丸め誤差の残差も attention score の計算に加えます。通常の Strata テキスト生成エンジン全体に適用される設定ではありません。

この runner は stable-diffusion.cpp へ Strata の `tools/image/sdcpp_native` を適用して作られ、CUDA/HIP ビルドに含まれます。さらに `--model-args qwen_image_2_1_native=1`（Strata の画像サーバーでは config の `native: true`）で選択した場合だけ使われます。したがって、変数を設定しても stock runner を使う構成には影響しません（`tools/image/sdcpp_native/apply.py:1-10,27-45,49-51`; `tools/image/qimage.py:170,190-198`; `serve/images.py:125-128`）。

## 値と判定

runner のコンストラクターで `getenv("STRATA_QI_QSPLIT") != nullptr` を一度評価します。未設定なら無効、設定されていれば値の中身によらず有効です。空文字、`0`、`false` も有効で、数値変換や文字列比較はありません。この結果は runner の `qsplit` メンバーに保持され、同じ runner の処理中に環境を書き換えても再評価されません（`tools/image/sdcpp_native/qwen_image_2_1_native.hpp:49-60,80-90`）。

## 有効になる条件

有効な設定が実際の query 残差経路に渡るには、ネイティブ runner が選択され、画像トークン処理で `use_wmma` が真である必要があります。`use_wmma` は画像 pass で、対応 GPU 上の WMMA attention が利用可能かつ `STRATA_QI_EXACT_ATTN` が未設定のとき真です（`qwen_image_2_1_native.hpp:332-338,391-400`）。

- HIP の RDNA3 では WMMA attention が利用可能です。RDNA4 は `STRATA_QI_GFX12_ATTN` の先頭文字が `1` の場合に限り利用可能になります（`qi21-native.cu:551-560`）。この経路では Q split が残差計算に使われます。
- NVIDIA CUDA では Ampere 以降が WMMA attention 対応として選ばれます（`qi21-native.cu:561-565`）。ただし後述のとおり、この attention カーネルは query 残差入力に対応していません。
- WMMA attention が選ばれない場合や `STRATA_QI_EXACT_ATTN` が設定されている場合、画像 attention は別経路を使い、この変数による残差計算は行いません（`qwen_image_2_1_native.hpp:332-338,391-407`）。

ネイティブ runner 自体も、参照画像、非 fused MLP、非 CUDA/HIP backend、想定外の入力形状などでは stock runner にフォールバックします（`qwen_image_2_1_native.hpp:446-466`）。

## 実行時の詳細

WMMA attention を使う画像 pass では、QKV 後処理カーネルが RoPE 適用後の query `r` を fp16 に丸めて高位値を保存します。`STRATA_QI_QSPLIT` が設定されている場合は、同じ query の「元の float 値から fp16 高位値を戻した値を引いた残差」を fp16 にして、高位値バッファの後ろへ格納します。attention カーネルは各 key tile に対し、高位 query と残差 query の両方から WMMA 積を加算します（`qi21-native.cu:113-143,271-328`）。

HIP の WMMA 実装はこの高位・残差の両入力を受け付けます（`qi21-native.cu:643-659`）。一方 CUDA 実装は残差 pointer が非 null ならコード `1` を返し、attention を実行しません（`qi21-native.cu:660-672`）。そのエラーは image pass の失敗として扱われ、runner は `Qwen Image 2.1 native: the image pass failed; using the stock runner` の警告を出し、ネイティブ runner を無効化してその step を stock runner に委ねます。以降の呼び出しも stock runner を使います（`qwen_image_2_1_native.hpp:108-112,571-574`）。このため NVIDIA Ampere 以降で WMMA attention が選ばれる構成では、この環境変数の設定によりネイティブ経路からフォールバックする可能性があります。

コードコメントは「accuracy gain なし、step time +7%」と測定結果を記していますが、同じ箇所に GPU、モデル、設定、測定方法の条件はありません。その数値はこのソースコメントに書かれた値としてのみ確認でき、一般的な性能特性とは判断できません（`qwen_image_2_1_native.hpp:84-88`）。

## 根拠

- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:80-90` — 環境変数の読み取りと runner 単位の保持。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:332-338,363-367,391-400` — 適用条件、残差バッファの受け渡し、attention 経路の選択。
- `tools/image/sdcpp_native/qi21-native.cu:113-143,271-328` — fp16 高位 query と残差 query の生成、および HIP WMMA での加算。
- `tools/image/sdcpp_native/qi21-native.cu:551-565,643-672` — backend / GPU 条件と CUDA・HIP カーネルの対応差。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:108-112,446-466,571-574` — native runner の無効化、stock runner へのフォールバック。
- `tools/image/sdcpp_native/apply.py:1-10,27-51`; `tools/image/qimage.py:170,190-198`; `serve/images.py:125-128` — 同梱ツール、build 条件、runner 選択。
