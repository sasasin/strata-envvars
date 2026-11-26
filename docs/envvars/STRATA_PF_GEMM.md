# `STRATA_PF_GEMM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP ビルドの prompt 中に行う FP16 入力・FP32 出力の GEMM で、Strata の WMMA GEMM を先に試すスイッチです。`Gemm::f16` では成功すれば通常の HIP GEMM に進まず、非対応 shape やデバイスで WMMA 関数が `false` を返すと既存経路へフォールバックします。`Gemm::native` では主に `STRATA_PF_PAD` と併用した padded stride の GEMM を選ぶ条件になります。CUDA-only ビルドではこの読み取り・分岐はコンパイルされません（`engine/src/prefill/gemm.cu:1303-1317,1489-1508`）。

明示設定が無い場合、HIP 起動時のアーキテクチャ既定値がこの変数を設定する機種があります。従って常に opt-in とは限りません。既定値も含めて、このスイッチが有効でも生成 token や GEMM の結果が通常経路と同一になる保証はコード上ありません。設計資料は丸め順序が異なり、回答の最下位 bit が変わる場合があると説明しています（`docs/STRIX_HALO.md:125-144`; 自動既定値の設定元は `engine/src/core/arch_defaults.cpp:183-189,193-200`）。

## 値と判定

GEMM の読み取り箇所では `getenv` の値の先頭 1 文字だけを `'1'` と比較します。文字列全体の parse、大文字小文字変換、空白除去、数値範囲検査はしません。`1`, `10`, `1anything` は真、未設定、空文字、`0`, `true`, ` 1` は偽です（`engine/src/prefill/gemm.cu:1310,1496`; SYCL 側の HIP 分岐 `engine/sycl/src/prefill/gemm.dp.cpp:952-957`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP の `Gemm::f16` / `Gemm::native` と、SYCL ソース内の `STRATA_USE_HIP` 分岐 | 明示値としては無効。後述の起動時既定値が適用される場合がある | 先頭文字が `1`（`1`, `10`, `1junk`） | 空文字、`0`, `true`, ` 1` |
| CUDA-only など `STRATA_USE_HIP` がないビルド | 当該ソースで読み取られない | 該当なし | 該当なし |

起動時に `apply_arch_defaults` は既存の環境値が**何であっても**上書きせず、未設定のときだけ `setenv(..., overwrite=0)`（Windows は `_putenv_s`）で既定値を書きます。したがって空文字や `0` も明示値として既定値より優先し、判定は偽になります。CLI 引数による上書き経路は確認できません（`engine/src/core/arch_defaults.cpp:218-224,302-310,334-343,407-410`）。

## 有効になる条件

- `Gemm::f16` のスイッチ読み取りと呼び出しは `STRATA_USE_HIP` のときだけです。`T <= 0` または `N <= 0` なら早期 return し、WMMA 呼び出しまで進みません（`engine/src/prefill/gemm.cu:1303-1317`）。SYCL 実装も同じ HIP compile guard 内です（`engine/sycl/src/prefill/gemm.dp.cpp:947-962`）。
- `STRATA_PF_SWITCH_MIN_T` も `atoll` で読み、未設定なら `0`、設定時は `T >= 値` が必要です。変換不能文字列は `atoll` の結果 `0`、負値も clamp されず、そのまま比較されます。これは `STRATA_PF_GEMM` 自体の値判定とは別です（`engine/src/prefill/gemm.cu:1310-1312,1495-1501`）。
- `Gemm::f16` は WMMA 関数が受理する shape・device・引数のときだけその GEMM を実行します。組み込み gfx11 WMMA は少なくとも `T >= 64`, `N >= 512`, `K` が 32 の倍数、`beta` が 0 または 1、各ポインターや stride が有効であることを要求します。gfx11 WMMA の device 判定に失敗した場合、HIP の対応ビルドでは Unsloth WMMA を試します。どちらも拒否・起動失敗なら後続の WMMA 設定または通常の HIP BLAS 経路へ進みます（`engine/src/prefill/wmma_gemm.cu:703-735`; `engine/src/kernels/hip/hip_unsloth_wmma.cu:317-345,751-755`; `engine/src/prefill/gemm.cu:1312-1327`）。
- `Gemm::native` の padded 経路は、さらに `STRATA_PF_PAD` の先頭文字も `1`、`T >= max(STRATA_PF_SWITCH_MIN_T, 64)`, `N >= 512`, `K % 32 == 0`, scratch 容量内であり、現在の device が padded WMMA product に対応することを要求します。満たさない場合は通常経路または既存の padded-X 処理へ進みます（`engine/src/prefill/gemm.cu:1492-1507`; `engine/src/prefill/prefill.cpp:1037-1049,5195-5210,5541-5544`; `engine/src/prefill/wmma_gemm.cu:62-68,758-764`）。
- 起動時既定値は HIP ビルドで `apply_arch_defaults` が呼ばれた場合に限ります。離散 gfx1100/1101/1102 では `gfx11_discrete_wmma_env` が既定で `1` を含みますが、`STRATA_GFX11_WMMA_DEFAULTS=0`、`STRATA_GFX11_DEFAULTS=0`、または `STRATA_DEFAULTS=026` でその組を止められます（`engine/include/strata/core/gfx11_extra.hpp:27-36,87-109`; 適用 `engine/src/core/arch_defaults.cpp:334-343`）。
- 統合 GPU では `igpu_default_env` による組の既定化があります。Linux の gfx1103 は既定で有効、Windows の gfx1151 も既定で有効です。gfx1150 と Linux gfx1150/gfx1151 は `STRATA_IGPU_PROMPT_SET=1` で有効化できます。`STRATA_IGPU_PROMPT_SET=0` または `STRATA_IGPU_DEFAULTS=0` は既定化を止めます。全ての可視 GPU が統合 GPU かつ同一 arch であることも `all_igpu` 判定の条件です（`engine/src/core/arch_defaults.cpp:119-138,172-200`; `engine/src/program/generate.cpp:4287-4320`）。
- `STRATA_PF_PAD` が有効でも padded product を使えない device では activation を pad しません。通常の `STRATA_PF_GEMM` 経路自体は padded product に限らず、非 padded GEMM にも適用されます（`engine/src/prefill/prefill.cpp:1037-1049`; `engine/src/prefill/gemm.cu:1303-1317`）。

## 実行時の詳細

HIP の `Gemm::f16` と `Gemm::native` は、それぞれ関数内 `static const` lambda で値を初回評価し、プロセス内に cache します。SYCL 側の HIP 分岐も同様です。アーキテクチャ既定値は `generate.cpp` の起動処理で、engine のスイッチ初回読み取りより前に設定されます。従って実行中に環境変数を変えても、既に評価した読み取り箇所には反映されません（`engine/src/prefill/gemm.cu:1310,1496`; `engine/sycl/src/prefill/gemm.dp.cpp:955`; `engine/src/program/generate.cpp:4287-4320`）。

`Gemm::f16` でスイッチが真かつ token 数しきい値を満たすと `strata_pf_gemm_f16` を呼びます。実装は gfx11 WMMA の場合に受理可能な形状からカーネルを選び、HIP ビルドの対応外アーキテクチャでは Unsloth の Wave32 WMMA を試します。`false` を返した場合、`Gemm::f16` は `STRATA_WMMA_GEMM` の別経路、HIP の `f16_io_` 経路、hipBLASLt などへ順に進みます（`engine/src/prefill/gemm.cu:1307-1327`; `engine/src/prefill/wmma_gemm.cu:703-735,740-765`; `engine/src/kernels/hip/hip_unsloth_wmma.cu:317-345`）。

このスイッチは prompt の各 FP16 GEMM 呼び出しで分岐に使われ、CLI の専用引数やリクエスト単位の値はありません。`STRATA_PF_PAD` を有効にした場合、prefill の GDN/QSA activation buffer の行 stride と確保量が変わります。`Gemm::native` はその stride の X と必要なとき padded weight を WMMA に渡し、padded 経路が使えない場合には通常 stride での処理を試します（`engine/src/prefill/prefill.cpp:1895-1908,5195-5210,5541-5544`; `engine/src/prefill/gemm.cu:1492-1534`）。

## ログと測定値

自動既定値が新しい値を設定したとき、gfx11 離散 GPU は `strata: gfx11 (RDNA3): %zu matrix-core prompt & MoE switches on by default (STRATA_GFX11_WMMA_DEFAULTS=0 or STRATA_GFX11_DEFAULTS=0 turns them off; NAME=0 turns one off): ` に続けて switch 名を出力します。統合 GPU は `strata: integrated GPU (%s): the matrix-core prompt set is on (1.6x to 2x faster prompts on a Radeon 780M, the answers differ in the last bits): ` を出力してから設定名を列挙し、`.  Turn one off with NAME=0 (for example STRATA_HC_UPMIX=0), all of them with STRATA_IGPU_PROMPT_SET=0` を続けます（Windows ではさらに `.  Not yet tested on Windows`）。ユーザーが変数をあらかじめ設定していた場合、その変数は自動設定ログの一覧に出ません（`engine/src/core/arch_defaults.cpp:334-343,406-421`）。

この変数が通常の GEMM 経路を選んだことを示す専用ログはありません。`STRATA_PF_PAD=1` も有効で、device に padded product がない場合は `prefill gemm: STRATA_PF_PAD needs the padded gfx11 product, which this card does not run; not padding` と stderr に出します（`engine/src/prefill/prefill.cpp:1041-1047`）。padded X に対応する経路もなく unpadded copy 用 device memory を確保できない場合、`Gemm::native` はエラー文を stderr に出して `exit(1)` します（`engine/src/prefill/gemm.cu:1523-1534`）。これは `STRATA_PF_GEMM` 単独の失敗通知ではありません。

`docs/AMD_HIP.md:309` はこのスイッチを gfx11 のみと記していますが、調査対象 commit の WMMA 実装は非 gfx11 compilation fallback から Unsloth WMMA を呼び、同梱 API は gfx11 と gfx12 を対応範囲として記載しています（`engine/src/prefill/wmma_gemm.cu:738-765`; `engine/include/strata/kernels/hip_unsloth_wmma.hpp:252-264`）。従って当該表の backend 範囲は現行コードと一致しません。資料中の測定値は現行 commit で再測定していません。

## 根拠

- `engine/src/prefill/gemm.cu:1303-1327,1489-1534`
- `engine/src/prefill/prefill.cpp:1034-1052,1895-1908,5195-5210,5541-5544`
- `engine/src/prefill/wmma_gemm.cu:44-69,698-765`
- `engine/src/kernels/hip/hip_unsloth_wmma.cu:317-345,710-755`
- `engine/src/core/arch_defaults.cpp:119-138,172-224,302-343,406-421`
- `engine/include/strata/core/gfx11_extra.hpp:27-36,87-109`
- `engine/src/program/generate.cpp:4287-4320`
- `engine/sycl/src/prefill/gemm.dp.cpp:947-975`
- `engine/include/strata/kernels/hip_unsloth_wmma.hpp:252-264`
- `docs/STRIX_HALO.md:125-150`; `docs/AMD_HIP.md:300-310,445-463`
