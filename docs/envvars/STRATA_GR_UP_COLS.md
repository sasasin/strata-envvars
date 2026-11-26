# `STRATA_GR_UP_COLS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版 fused GR read の up カーネルで、1 work-group が扱う列数を選ぶ。既定の 16 列から 4、8、32、64 列へ切り替えられる。列数に応じて `N / C` 個の work-group を起動するため、コンパイル済み形状の `N=2560` ではそれぞれ 640、320、80、40 個となる。列数別のテンプレート実体は同じ `gr_up_multi_kernel<C>` である。ソースコメントは 4 / 8 列について「同じ bits」と記しているが、32 / 64 列を含む全設定についての出力一致を確認した記述ではない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:34-38,853-856,1200-1205,1212-1237`）。

読み取り箇所はこの SYCL ソースの `gr_up_cols()` 1 箇所。通常の CUDA 実装 `engine/src/kernels/cuda/fused_gr.cu` にはこの名前の読み取りがなく、SYCL ビルドで該当 up 経路が選ばれた場合の設定である（SYCL プロジェクトのビルド定義: `engine/sycl/CMakeLists.txt:1-10,21-25`）。

## 値と判定

`std::getenv` の結果を `std::atoi` に渡し、変換結果が `4`, `8`, `32`, `64` のいずれかの場合だけ採用する。それ以外は `UPM_COLS`（16）へ戻る。文字列全体の妥当性検証や範囲 clamp はない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:853-856,1203-1206`）。

| 条件 | unset | 有効になる値（例） | 無効値・既定値へ戻る例 |
|---|---:|---|---|
| SYCL の `gr_up_cols()` 経由 | 16 | `4`, `8`, `32`, `64` | 空文字、`0`, `1`, `16`, `-4`, `true`, `false`, `xyz` は 16 |

`atoi` は数値の先頭部分を読むので、たとえば `8junk` や先頭に空白を含む ` 8` は変換結果が 8 となり採用される。`4.0` は整数部の 4 が採用される。大文字小文字の比較はない。空文字や数値で始まらない文字列は 0 となり、許可値ではないため 16 になる。数値として変換された後の値に clamp はなく、許可リストとの完全一致だけで判定する（同上）。

## 有効になる条件

- SYCL エンジンの `fused_gr.dp.cpp` を使うビルドであること。CUDA エンジンの同名 fused GR 実装ではこの環境変数を読まない。
- `fused_gr_read_multi()` が最終的に `launch_gr_up_multi()` に到達すること。`STRATA_GR_V3` が対応デバイスで実行可能と判定されると同関数は先に return し、対象変数の up 列数選択を通らない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202,3289-3297`）。
- multi-read の up 側で B60 private Q8、GF の up/combo、cached norm、`lo_once`、`gr_more_groups()` の各分岐が選ばれた場合も `launch_gr_up_multi()` を通らず、この値はその up 起動に適用されない。通常分岐では `launch_gr_up_multi()` が呼ばれる（同 `:3465-3493`）。
- 単一トークンの `fused_gr_read()` は、`kDownXnTooBig`、`gr_down_sliced()`、`gr_norm_split()`、`gr_down_direct()` のいずれかが真なら multi-read に委譲し、上記 multi-read の条件に従う。それらがすべて偽なら専用 `gr_up_kernel` を起動するため、この環境変数はその経路に効かない（同 `:3522-3559`）。
- CLI 引数や別の環境変数が値を直接上書きする処理はない。ほかの経路切替変数は、上記のとおり対象の up 起動自体を迂回させることがある。

## 実行時の詳細

`gr_up_cols()` 内の関数ローカル `static const int` 初期化で初回評価時に読み、結果を以後の呼び出しでキャッシュする。したがって初回評価後にプロセス環境を変えても再読込されない。選択された列数は `launch_gr_up_multi()` の switch に渡り、対応するテンプレート実体を起動する。各 work-group 数は `N / C`、work-group のサイズは `THREADS`（256）である（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:39-40,1203-1206,1212-1245`）。

既定の 16 は `UPM_COLS` として定義されている。multi-read の通常 up 分岐でだけ環境値を使い、`gr_large_grf()` が真の場合は同じ列数のカーネルに large-GRF properties を付ける。`STRATA_GR_UP_ILP` は別の分岐で ILP 版を選ぶが、列数の判定自体は共通である（同 `:853-856,1208-1237,3485-3493`）。

## ログと測定値

この変数の読み取り・fallback・採用を知らせるログはない。値が許可リスト外でも警告せず 16 を使う。カーネル起動時の SYCL エラー処理はキュー/ランタイム側に依存し、この環境変数専用のエラー経路は実装されていない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1203-1206,1239-1245,3492-3500`）。

ソースコメントには Xe2 / B70 の latency-bound の観察と、列数 8 / 4 で 320 / 640 work-group になる旨が記されているが、測定条件一式や再現手順は同箇所に示されていないため、性能値としては記載しない（同 `:1200-1205`）。

## 根拠

- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:853-856,1200-1206` — 既定列数、変換、許可値、fallback。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1212-1245` — 列数別のカーネル起動。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202,3289-3297,3465-3500` — multi-read の early return と up 側の分岐。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3522-3559` — 単一 read から multi-read への委譲条件と専用経路。
- `engine/sycl/CMakeLists.txt:1-10,21-25` — SYCL エンジンが独立したビルドであること。
