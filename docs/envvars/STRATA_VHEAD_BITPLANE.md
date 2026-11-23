# `STRATA_VHEAD_BITPLANE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

ネイティブ出力 head の重みを追加の bit-plane 表現に展開し、対応 GPU と条件を満たす場合に verify window の greedy argmax を bit-plane カーネルで計算するかを制御する。対象は `output.weight` が Q8_0 または Q6_K のネイティブ head。環境変数を有効にしても、この追加表現を作成できない場合は既存の native MMVQ 経路が使われる。読み取りは CUDA カーネル実装の `vhead_bitplane_enabled()` にある（`engine/src/kernels/cuda/vhead_bitplane.cu:670-678`）。

## 値と判定

`std::getenv` の結果を関数内 `static const bool` に一度だけ保存し、未設定でなく、かつ `std::atoi(value) != 0` の場合に値を有効とする。整数全体の厳密な検証やエラー報告はしない。`atoi` の変換結果で判定するため、空文字・`0`・`0abc`・`true` は無効、`1`・`-1`・`1tail` は有効（符号と先頭の十進数字列を変換）となる。空白だけの値や数字で始まらない文字列は 0 になる。変数を読み取った後の値変更は、このプロセスの判定に反映されない。ヘッダーの宣言コメントには「default ON」とあるが、実装は未設定を `false` にするため、実際の既定は OFF（無効）である（`engine/include/strata/kernels/vhead_bitplane.hpp:28-29`, `engine/src/kernels/cuda/vhead_bitplane.cu:673-677`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA の bit-plane 実装 | 無効 | `atoi` の結果が非 0（例: `1`, `-1`, `1tail`） | `atoi` の結果が 0（例: 空文字, `0`, `0abc`, `true`） |
| HIP コンパイル | 無効 | 有効にならない | すべて。HIP では device capability を 0 として返す |
| Metal stub | 無効 | 有効にならない | すべて。stub は `false` を返し、この変数を読み取らない |

## 有効になる条件

値が有効でも、以下のすべてを満たさなければ bit-plane head は作成・使用されない。

- `--native-head-gguf` が選ばれたネイティブ出力 head の経路であること。この引数は `--stream-token` を必要とし、native preset を使う場合は preset が native head の入力にもなる（`engine/src/program/generate.cpp:1260`, `5137`, `5350-5353`, `8320-8325`）。multi-GPU の場合、この箇所では `NativeHead::load` 自体を呼ばない（同 `generate.cpp:8320-8325`）。
- CUDA デバイスの compute capability が 8.0 以上であること。能力値の取得に失敗した場合は 0 として扱われる。HIP は常に 0 を返すため対象外（`engine/src/kernels/cuda/vhead_bitplane.cu:648-668`）。
- head がホスト pinned memory ではなく VRAM 上にあり、型が Q8_0 (`type == 8`) または Q6_K (`type == 14`) であること（`engine/src/core/native_head.cpp:266-267`）。
- Q6_K の場合、`STRATA_Q6_PACKED` による packed head が選ばれていないこと（同 `native_head.cpp:262-267`）。
- 作成開始時の空き VRAM が `1536 MiB` より大きいこと（同 `native_head.cpp:268-271`）。等しい場合は作成しない。追加バッファの確保または変換カーネルの同期に失敗した場合も作成関数は `nullptr` を返す（`engine/src/kernels/cuda/vhead_bitplane.cu:680-737`）。
- verify 内で `T <= 16`、かつ `STRATA_LOGITS_DUMP` が未設定であること（空文字を含め、設定されていれば bit-plane を使わない）。さらに Q6_K head では `T >= 4` が必要（`engine/src/core/verify.cpp:3020-3027`）。

## 実行時の詳細

`NativeHead::load` が head のアップロードと型別 pack を終えた後に環境変数を評価し、条件を満たせば `vhead_bitplane_create()` が追加のデバイスバッファを確保して重みを変換する。この処理は head のロード時に行われる。値の真偽は `vhead_bitplane_enabled()` の初回呼び出しで static cache される一方、compute capability 判定は呼び出しごとに行われる（`engine/src/core/native_head.cpp:262-271`, `engine/src/kernels/cuda/vhead_bitplane.cu:666-678`）。

verify は適用条件を満たすと、量子化済み activation と bit-plane handle を `vhead_bitplane_argmax()` に渡し、出力 token ID を直接 `m_out_` に書く。成功時はその window の通常の logits argmax を省略する。分割 head の経路が優先され、bit-plane 関数が使えない場合は通常の native MMVQ に戻り、得られた logits から token を選ぶ（`engine/src/core/verify.cpp:3101-3124`, `3130-3138`）。bit-plane を使った後に window の logits が必要になった場合は `ensure_head_logits()` が通常の native MMVQ で logits を改めて計算する（同 `verify.cpp:4421-4432`, `4452-4460`）。

## ログと測定値

bit-plane handle の作成に成功した場合、stderr に `strata: exact bit-plane LM head enabled (%s, +%.1f MiB VRAM; STRATA_VHEAD_BITPLANE=0 disables)` を出す（`engine/src/core/native_head.cpp:271-275`）。空き VRAM 不足や作成失敗時にこの機能専用の理由ログはなく、通常の head 計算経路に進む（同 `native_head.cpp:268-279`, `engine/src/kernels/cuda/vhead_bitplane.cu:713-737`）。ここでは性能測定値を記載できる資料を確認していない。

## 根拠

- 読み取り・値判定・GPU 対応判定: `engine/src/kernels/cuda/vhead_bitplane.cu:648-678`
- head 作成条件・空き VRAM・有効ログ: `engine/src/core/native_head.cpp:262-279`
- 重み形式・寸法条件、確保失敗時の `nullptr`: `engine/src/kernels/cuda/vhead_bitplane.cu:680-737`
- CLI 条件と head のロード箇所: `engine/src/program/generate.cpp:1260`, `5137`, `5350-5353`, `8320-8329`
- verify 適用条件、計算経路、logits fallback: `engine/src/core/verify.cpp:3020-3027`, `3101-3138`, `4421-4460`
