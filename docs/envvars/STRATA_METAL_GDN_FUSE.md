# `STRATA_METAL_GDN_FUSE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal の prompt chain における GDN 入力投影 4 本（qkv、z、alpha、beta）を、別々の GEMM 4 回ではなく、連結した重みと出力を使う GEMM 1 回にまとめるかを制御する。オフにすると個別の GEMM と通常の `gdn_pre` / `gdn_post` dispatch を使う。GDN scan と出力投影はどちらの分岐にも残る（`engine/metal/src/engine/window.cpp:100-105`; `engine/metal/src/engine/prompt_chain.inc:327-370`）。

この変数の実読み取りは `gdn_fused_inputs()` の `std::getenv` 1 箇所で、同関数は Metal prompt chain の setup から呼ばれる。候補一覧には名前があるが、候補名だけではなくこの読み取りを根拠に環境変数として扱う（`engine/metal/src/engine/window.cpp:103-105`; `engine/metal/src/engine/prompt_chain.inc:113`）。

## 値と判定

`std::getenv` の戻り値が null かどうかを見た後、設定値全体を `std::string` と `"0"` で完全一致比較する。数値 parse、空白除去、大小文字変換はしない。したがって空文字や `"false"` は「無効値」ではなく、オフ指定に一致しない値として扱われる（`engine/metal/src/engine/window.cpp:103-105`）。

| 条件 | unset | 融合をオフにする値 | オフ指定に一致しない値 |
|---|---|---|---|
| Metal prompt chain の setup | `off == false`。Apple M5 系では融合を選ぶ | 完全一致する `"0"` | 空文字、`"1"`、`"00"`、`"0anything"`、`"false"`、`" 0"`、`"0 "`、`"TRUE"` など。値の全体が `"0"` でない限り `off == false` |

表の右欄でも、実際に融合するのは device 名が `"Apple M5"` で始まる場合だけ。それ以外は `gdn_fused_inputs()` が false を返す（`engine/metal/src/engine/window.cpp:104-105`）。

## 有効になる条件

- Metal エンジンがビルドされていること。Metal runtime の構成があり、`STRATA_METAL_ENGINE` が有効である必要がある。CMake は Metal framework をリンクし、`STRATA_GPU_METAL=1` を定義する（`engine/metal/CMakeLists.txt:82-93,103-110`）。
- 実行 device 名が `"Apple M5"` で始まること。M4 やそれ以外の名前では、変数が未設定または `"0"` 以外でも融合しない（`engine/metal/src/engine/window.cpp:103-105`）。
- prompt が Metal の大きな prompt chain に進むこと。`STRATA_METAL_PROMPT=window` なら通常の window path に留まり、streaming 中もこの `Window::prompt` 経路には入らない。通常の非 streaming prompt では `n >= STRATA_METAL_PROMPT_MIN` が条件で、後者の既定値は 32 行（`engine/metal/src/engine/window.cpp:3743-3749`）。
- prompt chain 内の GDN layer（`l % G_QI != G_QI - 1`）で融合分岐が使われる。環境変数は fused GEMM を選ぶだけで、prompt chain 自体や Metal backend を有効化しない（`engine/metal/src/engine/prompt_chain.inc:322-328`）。

この環境変数に対する CLI 引数の上書き分岐は確認できない。`STRATA_METAL_PROMPT` と `STRATA_METAL_PROMPT_MIN` は GDN 融合の値を上書きするのではなく、prompt chain に到達するかを左右する（`engine/metal/src/engine/window.cpp:3746-3749`）。

## 実行時の詳細

`prompt_run_rows()` が非 streaming・window fallback ではない prompt を `Window::prompt()` に渡し、`Window::prompt()` が `pc_setup()` を呼ぶ。初回 setup では prompt buffer `b.fused` に `gdn_fused_inputs(cx_->device_name())` の結果を保存する。環境値 `off` は関数内 `static const bool` の初回評価時に一度だけ読み込まれ、以後の環境変更は反映されない。device 名による M5 判定は setup 呼び出しごとに評価される（`engine/metal/src/engine/window.cpp:103-105,3743-3749`; `engine/metal/src/engine/prompt_chain.inc:49-65,113`）。

融合時は GDN の 4 重みを `Wcat` の連続領域へ dequantize し、`gemm(..., G_GDNF, N)` を 1 回 dispatch する。連結出力 `yf` を fused `gdn_pre_f` と `gdn_post_f` に渡し、間の scan は同じ `gdn_scan_name()` 選択の dispatch を使う。非融合時は各重みを別 buffer に dequantize し、qkv / z / alpha / beta の GEMM を 4 回行って通常の `gdn_pre` / `gdn_post` を呼ぶ。分岐後は両方とも同じ `gdn` scan と `ssm_out` 投影へ進む（`engine/metal/src/engine/prompt_chain.inc:113-139,327-370`）。

## ログと測定値

この変数の値や fused / non-fused の選択を直接表示するログ、専用の警告・終了経路は確認できない。prompt setup は stderr に `strata metal: prompt kernels (mac-kern's prompt chain) for chunks of %d rows, %s, ready in %.0f ms` を出すが、メッセージは融合選択を示さない。`STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` が設定されると prompt の時間と token/s を stderr に表示するが、これも GDN の fused 状態を報告しない（`engine/metal/src/engine/prompt_chain.inc:151-153`; `engine/metal/src/engine/prompt_chain.inc:608-611`）。

ソースコメントには M5 family、T=2048 の GDN 入力投影について `3.09 -> 2.87 ms a layer` とあるが、モデル・具体的な機種・測定条件が揃っていないため、測定値として一般化して記載しない（`engine/metal/src/engine/window.cpp:100-102`）。

## 根拠

- `engine/metal/src/engine/window.cpp:100-105` — 対象関数、完全一致 `"0"` 判定、Apple M5 名の prefix 条件。
- `engine/metal/src/engine/prompt_chain.inc:49-65,113-139` — setup 時の呼び出し、fused / separate buffer 構成。
- `engine/metal/src/engine/prompt_chain.inc:322-370` — GDN layer の判定と fused / separate GEMM・kernel dispatch。
- `engine/metal/src/engine/window.cpp:3735-3749` — prompt chain の呼び出しと streaming / window / 最小行数条件。
- `engine/metal/src/engine/prompt_chain.inc:151-153,608-611` — stderr の prompt setup / trace ログ。
- `engine/metal/CMakeLists.txt:82-110,150-168` — Metal runtime、compile definition、Metal engine の build 条件。
