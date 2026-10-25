# `STRATA_QI_GFX12_ATTN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

HIP backend で RDNA4（gfx12）の Qwen Image 2.1 native runner が使う image-token attention kernel を選びます。未設定なら gfx12 では WMMA kernel を選ばず、runner 内で ggml の flash attention に進みます。gfx11（RDNA3）はこの変数に関係なく WMMA kernel の対象です。

この環境変数は Strata 同梱の `tools/image/sdcpp_native` 実装だけで読み取られます。native runner 自体も `qwen_image_2_1_native=1` を指定した経路で選択されます。

## 値と判定

| 状態 | gfx12 / HIP での判定 |
|---|---|
| 未設定 | WMMA attention を選ばない |
| 設定値の先頭文字が `1` | WMMA attention の対象にする |
| 空文字、先頭文字が `1` 以外 | WMMA attention を選ばない |

値全体の parse はせず、`getenv()` の結果が非 null であり、先頭文字が文字 `1` かだけを検査します。したがって `1`, `10`, `1anything` は有効、`true`, `0`, 空文字は無効です。大文字小文字や後続文字は判定されません。

## 有効になる条件

- HIP backend であること。CUDA backend ではこの変数を読み取らず、NVIDIA の Ampere 以降なら `qi21_has_wmma_attn()` が WMMA attention を利用可能と判定します。
- 対象 GPU が RDNA4 / gfx12 であること。この場合は変数が設定され、先頭文字が `1` のときだけ利用可能と判定します。RDNA3 / gfx11 は環境変数なしで利用可能と判定します。
- native runner の attention 経路が使われること。runner は Qwen Image 2.1 native の選択条件に加え、入力形状、reference image の有無、fused MLP、CUDA/HIP backend などを確認し、条件に合わない場合は stock runner に戻ります。
- `STRATA_QI_GGML_ATTN` が未設定であること。これが設定されていると、WMMA kernel の対象 GPU でも runner は ggml attention を選びます。

## 実行時の詳細

`QwenImage21NativeRunner::compute()` の最初の weight load 時に `qi21_has_wmma_attn()` を呼び、その結果を `wmma_attn` に保存します。gfx12 ではこの関数が `STRATA_QI_GFX12_ATTN` を読み、GPU 世代と値を判定します。以後の計算では保存済みの選択を使います。

image-token attention では、`STRATA_QI_EXACT_ATTN` が設定されていれば先に fp32 causal attention 経路を選びます。それ以外で `wmma_attn` が真なら `qi21_attn_wmma()` を呼び、偽なら ggml graph の `ggml_flash_attn_ext()` を実行します。したがって `STRATA_QI_GFX12_ATTN=1` は gfx12 で WMMA 経路を許可しますが、`STRATA_QI_GGML_ATTN` または exact attention の選択を上書きしません。

環境変数の変更は native runner の初回 weight load 後には再評価されません。Strata ソースではこの変数に対応する専用ログや警告は確認できませんでした。

## 根拠

- `tools/image/sdcpp_native/qi21-native.cu:551-565`: HIP の RDNA3 判定、RDNA4 の環境変数読み取り、CUDA 側の別判定。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:445-475`: native runner の入力・backend 条件、初回ロード時の `wmma_attn` 決定。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:391-415`: exact attention、WMMA、ggml flash attention の選択。
- `tools/image/sdcpp_native/apply.py:29-33`: `qwen_image_2_1_native=1` を含む場合に native runner を登録する条件。
- `docs/DETAILS.md` には、この環境変数または Qwen Image 2.1 native attention の挙動説明・測定値は見当たりませんでした。
