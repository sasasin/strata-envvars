# `STRATA_PF_GEMM`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

主な役割は AMD HIP のプリフィルで、FP16 入力・FP32 出力の dense projection GEMM を Strata 独自の gfx11 WMMA カーネルに切り替える opt-in 変数です。量子化重みを FP16 に dequantize した後の projection と、もともと FP16 の重みを使う projection の両方に関係します。専用カーネルを呼ぶ分岐は HIP 条件下だけですが、`STRATA_PF_PAD` と組み合わせた padding 判定は共通のプリフィルコードでもこの変数を読みます。

## 値と判定

各読み取り箇所は値を数値として parse せず、先頭文字が `'1'` かどうかだけを判定します。したがって未設定・空文字・`0`・`true`・`2` は無効、`1`・`10`・`1anything` は有効です。大文字小文字や後続文字は検査しません。

判定は呼び出し元関数内の `static const bool` に保存されます。`Gemm::f16` と `Gemm::native` は別々に値をキャッシュし、プリフィルの activation padding 判定 `pf_pad()` も独立にキャッシュします。各判定後にプロセス環境を変更しても、その判定には反映されません。

## 有効になる条件

- 専用 WMMA GEMM の読み取り・切り替えは HIP ビルド（`STRATA_USE_HIP`）に限られます。共通の `pf_pad()` は CUDA ビルドでも `STRATA_PF_GEMM` と `STRATA_PF_PAD` を読みますが、専用 GEMM への切り替えはしません。CUDA で両方を有効にすると padded activation stride が渡され、HIP 専用処理のない `Gemm::native` は対応できない stride として stderr に出して終了する経路があります。
- 呼び出し先の実カーネルがビルドに含まれ、現在の GPU が gfx1100、gfx1101、gfx1102、gfx1150、gfx1151 のいずれかであること。その他の GPU ではカーネル関数が `false` を返し、通常の GEMM 経路へ進みます。
- `strata_pf_gemm_f16[_ld]` の形状条件を満たすこと。最低 `T >= 64`, `N >= 512`, `K >= 32` かつ `K` が32の倍数、`beta` が0または1、leading dimension と各次元が許容範囲内である必要があります。
- `STRATA_PF_SWITCH_MIN_T` が設定されている場合、`T >=` その値であること。これは `std::atoll` で読み、未設定なら0です。値の全体検証や clamp はありません。たとえば非数値文字列は通常0、数字で始まる文字列は数値部分までが使われ、負数もそのまま比較に使われます。

## 実行時の詳細

`Gemm::f16` では、閾値を満たすと専用 WMMA GEMM を先に試し、成功すればその結果を使います。失敗した場合は、HIP WMMA の別経路（`STRATA_WMMA_GEMM` が有効な場合）、FP16 出力経路、hipBLASLt、hipBLAS の順で利用可能な既存経路に進みます。つまり `STRATA_PF_GEMM=1` は対象形状の実行を保証せず、対象 GPU・形状・beta 等の条件を満たす必要があります。

量子化重み側の `Gemm::native` は、さらに `STRATA_PF_PAD=1`、`T >= 64`、`N >= 512`、`K % 32 == 0`、パディングした重みが scratch に収まる条件を満たすと、重みを行 stride `K+64` で FP16 dequantize して専用 GEMM を試します。この padded 経路を使わない場合、`ldx == K` なら通常の dequantize + GEMM に進みます。padded activation stride (`ldx != K`) が渡されている場合は別途、非 padded 重みを使った strided 専用経路を試します。それが失敗すると stderr に `prefill gemm: a padded X ... needs STRATA_PF_PAD's path` を出して終了します。

`STRATA_PF_PAD` は gfx1151 のアーキテクチャ既定値として Strata が設定することがありますが、`STRATA_PF_GEMM` 自体はその既定値一覧に含まれず、引き続きユーザー opt-in です。既定値適用時に環境変数が既に存在すれば値を問わずユーザー設定を保持します。`STRATA_PF_PAD` と `STRATA_PF_GEMM` の両方が先頭 `1` の場合、プリフィル側は padded activation を準備します。

## ログと数値差

専用 GEMM が有効になったことを `STRATA_PF_GEMM` 固有のログで知らせる実装は確認できません。`STRATA_PF_GEMM=1` だけでは `STRATA_PF_SWITCH_MIN_T=4096` にはなりません。資料は長い prompt 向け構成例として両方を設定しています。

`docs/STRIX_HALO.md` はこの経路を gfx1151 の FP16 projection 用 128×256 WMMA GEMM と説明し、hipBLASLt とは加算順序が異なり丸め結果が変わるため opt-in としています。`docs/AMD_HIP.md` には RX 7900 XTX の報告者測定として複数の opt-in をまとめた速度値がありますが、これはこの変数単独の効果を示す測定ではありません。

## 根拠

- `src/prefill/gemm.cu:675-689`: HIP 条件下の値判定、閾値、専用 GEMM と後続経路。
- `src/prefill/gemm.cu:819-870`: 量子化重みの padded dequantize 経路、条件不成立時の通常経路、padded activation の失敗時ログ。
- `src/prefill/wmma_gemm.cu:37-56,681-708`, `include/strata/kernels/gfx_arch.hpp:22-26`: ビルド条件、GPU 対象、形状検査と WMMA kernel dispatch。
- `src/prefill/prefill.cpp:318-321,350-359,2648-2653,2880-2883`: 閾値の既定値、`STRATA_PF_PAD` との組み合わせ、および GDN/QSA の padded activation 使用箇所。
- `src/core/arch_defaults.cpp:32-45,61-79`: gfx1151 での `STRATA_PF_PAD` 既定設定とユーザー値の保持。
- `docs/STRIX_HALO.md:100-116`, `docs/AMD_HIP.md:227-242`: 推奨 opt-in 構成と報告測定。測定値は上記のとおり複数設定を含む。
