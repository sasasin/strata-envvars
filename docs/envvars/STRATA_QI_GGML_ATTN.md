# `STRATA_QI_GGML_ATTN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（`2026-10-14` 時点）。

## 役割

Strata 同梱の Qwen Image 2.1 ネイティブ DiT ランナーで、画像トークンの attention に使う Strata 独自 WMMA カーネルを無効にし、ggml の flash attention を選ばせる。通常の Strata エンジンや stable-diffusion.cpp の通常ランナーを切り替える設定ではない。

## 値と判定

| 状態 | 判定と結果 |
|---|---|
| 未設定 | 対応 GPU なら `wmma_attn` が有効になり得る。 |
| 設定あり | `getenv(...) == nullptr` が偽になるため `wmma_attn` は無効。空文字、`0`、`1`、その他の文字列で違いはない。 |

値の数値変換や文字列比較は行わず、環境変数の存在だけを見る。コマンドライン引数や設定ファイルによるこの判定の上書きはない。

## 有効になる条件

- ネイティブランナー自体は、CUDA または HIP 対応でビルドされた同梱 `sd-cli` に `qwen_image_2_1_native=1` の model arg が渡され、拡散モデルのパスも存在するときに選択される。通常の設定では `tools/image/qimage.py` が CUDA/HIP をネイティブ対象 backend として扱う。
- 計算時には入力形状が想定どおりで、参照画像がなく、fused MLP が有効で、runtime backend が CUDA/HIP である必要がある。条件を満たさない入力では stock runner に処理が渡り、この環境変数は読まれない。
- 環境変数が未設定でも、CUDA ビルドでは NVIDIA Ampere 以降でなければ Strata WMMA attention は選ばれない。HIP ビルドでは RDNA3 が対象。RDNA4 は別の `STRATA_QI_GFX12_ATTN` が設定され、その先頭文字が `'1'` の場合に対象となる。
- `exact_attn` が有効なときは fp32 の参照 attention 経路が優先されるため、この変数による WMMA の切替は実質的に影響しない。

## 実行時の詳細

対象のネイティブ runner は `compute()` の適格性チェックを通った後、重みがまだロードされていない最初の呼び出しで、GPU 対応判定と環境変数の有無から `wmma_attn` を設定する。重みロード後は `loaded` が立ち、この設定を再評価しない。従ってプロセス起動後に環境変数を変更しても、既にロード済みの runner には反映されない。

テキスト prefix の attention は常に `qi21_attn_causal` を使う。画像 token の attention では、`STRATA_QI_GGML_ATTN` が設定されていると `use_wmma` が偽になり、ggml の `ggml_flash_attn_ext` を使うグラフが構築される。出力精度は `GGML_PREC_F32` に設定し、runtime backend がこの演算をサポートしない場合はエラーコード `3` でその pass を失敗させる。その場合 `blocks_pass()` の失敗が `fail("the image pass failed")` につながり、警告 `Qwen Image 2.1 native: the image pass failed; using the stock runner` を出して runner を無効化し、stock runner に処理を戻す。

設定値を表示する専用ログはない。ネイティブ runner の重みロード成功ログには `wmma_attn` が真のとき ` (Strata attention)` が付く。ただし、このログは GPU と環境変数によるフラグを示し、`exact_attn` が真なら画像 attention 自体は fp32 経路を選ぶ。ggml attention に切り替えたこと自体を示すログは確認できない。

## 根拠

- `tools/image/sdcpp_native/apply.py:27-45,48-51` — `qwen_image_2_1_native=1` と拡散モデルパスがある場合にネイティブ runner を選択し、CUDA/HIP ビルドで機能を組み込む。
- `tools/image/qimage.py:169-170,197-198` — ネイティブ runner の backend 範囲と設定項目。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:445-475` — 適格性チェック、初回ロード時の環境変数読み取り、`loaded` の更新。
- `tools/image/sdcpp_native/qi21-native.cu:551-565` — CUDA/HIP の GPU 世代条件と `STRATA_QI_GFX12_ATTN` の判定。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:321-338,381-415` — prefix/image の区別、WMMA・厳密 attention・ggml flash attention の分岐と ggml backend 対応確認。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:233-236,553-555,571-574` — WMMA 使用時のログ、attention pass の失敗処理、stock runner への fallback。
- `docs/DETAILS.md` — この環境変数や Qwen Image 2.1 ネイティブ runner の切替を説明する記述は見つからなかった。上記の挙動はソースコードを根拠とする。
