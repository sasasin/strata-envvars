# `STRATA_GDN_CONVL2`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

プロンプト処理の GDN（gated delta net）畳み込みと、畳み込み出力の Q/K ヘッド L2 正規化を一つのタイル化カーネルにまとめるスイッチ。対象は GDN のプロンプト前処理 `gdn_conv` で、通常のトークン単位の decode 経路を切り替えるものではない。

## 値と判定

CUDA/HIP と SYCL の `gdn_conv` は、最初に条件を通過した時点で値を `static const bool` に保存し、`std::atoi(value) != 0` で判定する。未設定、空文字、整数に変換できない文字列、先頭の整数部分が `0` の文字列は無効。`1` や `-1` など、`atoi` の結果が 0 以外なら有効であり、文字列全体の一致や範囲検査はない。たとえば `2x` は有効、`x2` は無効になる。

| 状態 | 判定・動作 |
|---|---|
| 未設定 | 通常のタイル化畳み込みと、別カーネルによる L2 正規化 |
| `atoi` が 0 | 通常経路 |
| `atoi` が 0 以外 | 条件を満たす場合に畳み込みと Q/K L2 正規化を融合 |
| 値を実行中に変更 | `static` に保存された判定には反映されない |

## 有効になる条件

- プロンプト経路が `gdn_conv` を呼び、かつ `T > 64` であること。`CONV_TILE` は CUDA/HIP と SYCL の両実装で 64。
- `STRATA_GDN_CONV_SERIAL` が**未設定**であること。この変数は値の内容ではなく設定有無で直列経路を選ぶ。設定されているか `T <= 64` の場合は `STRATA_GDN_CONVL2` を評価せず、融合を使わない。
- CUDA/HIP の実装と SYCL 実装に融合カーネルがある。ただしアーキテクチャ既定値の自動設定は `STRATA_USE_HIP` のビルドに限られる。コード上、`gfx1151` と `gfx12`（RDNA4）で既定値表に含まれ、ユーザーがこの変数を何らかの値（空文字を含む）で設定済みならその値が優先される。`STRATA_GFX1151_DEFAULTS=0` または `STRATA_GFX12_DEFAULTS=0` は該当表全体の適用を止める。CUDA/SYCL ビルドではこの既定値設定処理は呼ばれないため、融合を選ぶには変数を明示する。

## 実行時の詳細

通常経路では、畳み込みをタイルごとに計算し、履歴更新カーネルを実行した後、各トークンの Q/K ヘッドに別の L2 正規化カーネルを実行する。有効時は融合カーネルがタイル内で畳み込み出力を作り、Q/K チャネルについて同じタイル内で L2 正規化する。その後、独立した履歴更新カーネルを実行して `gdn_conv` から戻る。V チャネルはこの L2 正規化の対象ではない。CUDA/HIP 版は fused 分岐内で戻るため、後段の独立 L2 カーネルを起動しない。SYCL 版も fused 分岐から戻る。

HIP 起動時にアーキテクチャ既定値が設定されると、`stderr` に `strata: gfx12 (RDNA4): ...` または `strata: gfx1151 (Strix Halo): ...` というスイッチ一覧の行が出る。既定値表を適用しない場合、この行はその処理からは出ない。ソースのコメントは CUDA 13.3 / sm_120 では bitwise でないと記している。`docs/STRIX_HALO.md` は gfx1151 での出力一致を一台の保守者環境での確認として説明しており、あらゆる GPU・ツールチェーンでの一致を保証する根拠ではない。

## 根拠

- `src/prefill/kernels.cu:311-368,1907-1925` — CUDA/HIP のタイル幅、融合カーネル、`atoi` による初回判定、直列・短チャンク条件、履歴更新と通常経路の L2 起動。
- `sycl/src/prefill/kernels.dp.cpp:471-555,2500-2601` — SYCL の同等カーネルと分岐。`STRATA_GDN_CONV_SERIAL` 設定有無、`T <= CONV_TILE`、融合時に独立 L2 処理を省く流れ。
- `src/prefill/prefill.cpp:2618-2624`、`sycl/src/prefill/prefill.cpp:2901-2907` — GDN プロンプト処理から `gdn_conv` を呼ぶ箇所。
- `src/program/generate.cpp:2152-2158`、`sycl/src/program/generate.cpp:1970-1976` — アーキテクチャ既定値の適用呼び出しが HIP ビルド条件下にあること。
- `src/core/arch_defaults.cpp:10-42,61-77` — gfx12 / gfx1151 の既定値表、`STRATA_GFX12_DEFAULTS` と `STRATA_GFX1151_DEFAULTS` による停止、ユーザー設定の優先、`stderr` の起動ログ。
- `docs/STRIX_HALO.md:3-6,83-92` — gfx1151 の測定環境、既定スイッチ一覧、および保守者環境での出力一致という文書上の範囲。
