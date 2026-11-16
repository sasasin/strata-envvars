# `STRATA_VIT_FA`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP 版の own vision tower で、Q/K/V の fused attention カーネル `k_attn_fa_gfx11` を使うか選ぶ。適用されると、通常の attention の QK 積・softmax・PV 積を別々に行う経路に代えて、query のチャンクごとにそれらを一つの gfx11 WMMA カーネルで計算し、float32 の context を出力する。画像の vision encoder の attention を切り替える設定であり、言語モデル側の flash attention 設定ではない（`tools/vision/own/vit_gpu.cu:279-285, 1080-1117`）。

この変数を読むのは HIP 用 `VitGpu::load` だけ。CUDA・SYCL・Metal・CPU の own tower ではこの読み取りも fused attention 経路もない。実行には GPU reader (`strata-vision --gpu --tower own`、または `--tower auto` が own を選ぶ場合) が必要で、`--tower mtmd` は対象外。`--tower` の省略時は `STRATA_VISION_TOWER` が reader 選択に使われ、明示的な `--tower` が優先する（`tools/vision/own/CMakeLists.txt:118-163`; `tools/vision/strata_vision.cpp:94-112, 137-170`; `tools/vision/own/own_reader.cpp:114-125`）。

## 値と判定

HIP ビルドでは `std::getenv` で設定有無を見て、設定されていれば `std::atoi(e) != 0` の結果で gfx1151 の既定値を上書きする。`atoi` は先頭の空白の後の符号付き十進数の prefix を変換し、文字列全体の妥当性は検証しない（`tools/vision/own/vit_gpu.cu:902-903, 920-925, 945-953`）。

| ビルド・GPU | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP、gfx1151、wave size 32、`head_dim <= 96` かつ 8 の倍数 | 既定で要求する | `1`, `2`, `-1`, `1tail`（変換値が非ゼロ） | `0`, `-1tail`, `true`, 空文字（変換値が 0） |
| HIP、上記以外 | 既定で無効 | 非ゼロの `atoi` 結果なら利用を要求するが、GPU・形状条件を別途満たす必要がある | 変換値 0 なら無効 |
| 非 HIP | このコード経路では変数を読まない | なし | なし |

未設定は `getenv` が null となり、gfx1151 の条件を満たす場合だけ `fa_default` が既定値になる。それ以外は既定で無効。明示的な空文字は設定済みとして `atoi("") == 0` になり、gfx1151 の既定有効も無効に上書きする。`true` や `on` は整数 prefix がないため無効、先頭が `1` の `1tail` は有効、`0anything` は無効。大文字小文字を問う文字列比較はない。数値の境界検査や clamp はなく、0 以外の変換結果は有効要求として扱われる（`tools/vision/own/vit_gpu.cu:920-925, 945-947`）。

## 有効になる条件

- own vision reader を GPU で動かし、ビルドが HIP (`STRATA_VIT_HIP`) であること。CMake は HIP 構成で `vit_gpu.cu` を HIP 言語として追加し `STRATA_VIT_HIP` を定義する。CUDA 構成は同ファイルを使うが `STRATA_VIT_CUDA` を定義するだけで、対象変数の読み取り箇所は HIP の `#if` 内にない（`tools/vision/own/CMakeLists.txt:118-131`; `tools/vision/own/vit_gpu.cu:939-955`）。
- `STRATA_VIT_FA` が非ゼロ、または gfx1151 の既定条件を満たすこと。gfx1151 の既定判定は wave size 32、`head_dim <= 96`、`head_dim % 8 == 0`（`tools/vision/own/vit_gpu.cu:920-925, 945-947`）。
- fused attention の実行時には、デバイスが gfx11 系で wave size 32、head size が 96 以下かつ 8 の倍数であること。したがって他の gfx11 カードでも `STRATA_VIT_FA` の非ゼロ値で要求できるが、別世代、wave size 違い、または形状条件外では使われない（`tools/vision/own/vit_gpu.cu:947-953`）。
- reader のモデル・画像形状が own GPU reader の対応範囲に入ること。`--tower auto` は reader の対応判定で own を選び、`--tower mtmd` は own tower を起動しない。`--tower own` は own を直接選ぶが、encoder load が失敗すれば起動失敗になる（`tools/vision/strata_vision.cpp:137-173`; `tools/vision/own/own_reader.cpp:49-73, 114-125`）。

値が有効要求でも GPU/形状条件に合わなければ `m.fa` は false のままになり、fused attention ではなく通常経路を使う。別の CLI 引数による `STRATA_VIT_FA` の上書きはない。`STRATA_VIT_FA_UNITS` は有効時の query チャンク量を別途調整するが、FA の有効・無効は切り替えない（`tools/vision/own/vit_gpu.cu:945-954, 1080-1117`）。

## 実行時の詳細

値は HIP `VitGpu::load` 中に読み、`want_fa` と `m.fa` に保存される。環境を再確認するのは各 load 時で、encode ごとには読み直さない。従って同じロード済み reader の実行中に環境を変更しても、その instance の判定には反映されず、再 load で新しい値を読む（`tools/vision/own/vit_gpu.cu:895-903, 945-954`; `tools/vision/own/vit_gpu.cu:1011-1017`）。

`m.fa` が true なら Q/K/V 投影後、画像 patch 数 `N` と head 数 `H` に応じて query 範囲を分割し `k_attn_fa_gfx11` を起動する。未対応条件などで false の場合は通常の batched QK 積、softmax、PV 積へ進む。fused カーネル後の GPU エラーは `sync_err("the fused attention")` により encode 失敗として返る（`tools/vision/own/vit_gpu.cu:1066-1073, 1080-1117`; `tools/vision/own/vit_gpu.cu:1023-1026`）。

## ログと測定値

HIP GPU reader の load 時、`want_fa` が true の場合 stderr に次のどちらかを出す:

- 有効時: `vit-fa: fused attention on (gfx11 WMMA)`
- 要求したが条件外: `vit-fa: fused attention asked for but not available on this card (gfx11, wave32, head size <= 96 and a multiple of 8 only)`

未設定で既定無効のとき、または `atoi` 結果が 0 のときは、この `vit-fa` 行は出ない。`STRATA_VIT_PROF` が設定され、かつ fused attention が有効なら、encode ごとに stderr へ `vit-prof fa: longest fused-attention launch %.2f ms (STRATA_VIT_FA_UNITS %lld)` を出力する（`tools/vision/own/vit_gpu.cu:945-954, 1152-1159`）。

## 根拠

- `tools/vision/own/vit_gpu.cu:895-955` — GPU load、gfx1151 の既定値、環境変数の変換と利用条件。
- `tools/vision/own/vit_gpu.cu:1080-1117` — fused と通常 attention の実行分岐、GPU エラー経路。
- `tools/vision/own/vit_gpu.cu:1152-1159` — profile ログ。
- `tools/vision/own/CMakeLists.txt:118-163` — CUDA/HIP/SYCL/Metal の別ビルド条件。
- `tools/vision/strata_vision.cpp:94-112, 137-173`; `tools/vision/own/own_reader.cpp:114-125` — reader 選択と GPU tower の起動経路。
