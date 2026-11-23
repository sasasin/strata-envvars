# `STRATA_GR_RDNA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

ハイパーコネクション（GR）読みのマルチトークン実装 `fused_gr_read_multi` を、AMD RDNA3 / RDNA3.5 向けの Wave32 DPP カーネル（`engine/src/kernels/cuda/rdna_gr.cu`）へ差し替える opt-in スイッチ。既定の読み（`engine/src/kernels/cuda/fused_gr.cu` の plain / v3 read）の代わりに `rdna_gr_down` 系 + `rdna_gr_up` 系を起動する（`rdna_gr.cu:509-544`）。

変わるのは GR 読みの計算経路・起動カーネル・数値だけ。他の段（MoE ルーティング、サンプリング）は変わらない。GR 読みの出力が分割 K の和（int8 重みでは活性も int8 量子化）になるため、下流の値が既定と一致する保証はソースにない（既定のマルチトークン読みは `engine/include/strata/kernels/fused_gr.hpp:66-70` で bitwise を主張するが、RDNA 経路にはその記述がない）。適用先は `fused_gr_read_multi` を通る読みに限り、単一トークンの decode は `fused_gr_read` を呼ぶので対象外（`engine/src/core/layer.cpp:1565`、`:1588`）。

## 値と判定

読み取りは `rdna_gr_enabled()` の 1 箇所だけ（`engine/src/kernels/cuda/rdna_gr.cu:548-565`）。`std::getenv("STRATA_GR_RDNA")` が非 null なら**先頭 1 文字だけ**を見て `'1'` なら 1、それ以外は 0。文字列全体の比較も `atoi` もない。

- 有効: `1`、`10`、`1x`、`1 `（先頭が `'1'`）
- 無効: `0`、`00`、`true`、`on`、`yes`、空文字 `""`、` 1`（先頭が空白）
- 未設定: `STRATA_HIP_FAST_DEC` を同じ規則で判定し、`'1'` 始まりなら 2（GPU 世代チェック付き）、それ以外・未設定なら 0（無効）

先頭が `'1'` でなければ `STRATA_HIP_FAST_DEC` を見ない（`rdna_gr.cu:550-551`）。空文字や `0` の明示は、既定値を含む `STRATA_HIP_FAST_DEC=1` の RDNA 経路を打ち消す。

| 条件（build / 値の出所） | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| HIP AMD build、`STRATA_GR_RDNA` 設定 | — | `1`、`10`、`1x`（世代チェックなし） | `0`、空文字、`true`、` 1` |
| 同上、`STRATA_GR_RDNA` 未設定 | 無効 | `STRATA_HIP_FAST_DEC=1…` かつ gfx11 WMMA 対象 or gfx12 | `STRATA_HIP_FAST_DEC` が `0`・空文字など |
| CUDA（NVIDIA）build / `STRATA_HIP_GFX906` build | 常に無効 | なし（値は読まれない） | すべて |

第 2 行の世代チェックは `gfx_arch_is_gfx11_wmma`（gfx1100/1101/1102/1103/1150/1151）または `gfx_arch_is_gfx12`（gfx1200/1201）で、それ以外は false（`rdna_gr.cu:556-564`、`engine/include/strata/kernels/gfx_arch.hpp:29-32`、`:42`）。

## 有効になる条件

- **build**: 読み取りは `#if defined(__HIP_PLATFORM_AMD__) && !defined(STRATA_HIP_GFX906)` の中だけ。他は false を返すスタブ（`rdna_gr.cu:25`、`:593-596`）。NVIDIA 用の CUDA build では無視される。
- **呼び出し経路**: `fused_gr_read_multi`（1〜8 トークン、または 8 トークン単位のスライス）のみ（`fused_gr.cu:4468-4484`）。
- **Q8 重みがあると無効**: `a[0].q8_down` と `q8_up` が非 null なら `launch_q8` で return し、`rdna_gr_enabled()` に到達しない（`fused_gr.cu:4284-4292`）。`STRATA_HC_Q8` で作られる Q8_0 コピーがこれに当たる（`verify.cpp:1805-1807`）。`STRATA_HC_Q8` は未設定でも gfx1100/1101/1102、gfx12、gfx1151 では既定で有効（`engine/src/core/native_dense.cpp:48-100`）なので、これらのカードでは `STRATA_HC_Q8=0`（または `STRATA_GFX11_DEFAULTS=0` / `STRATA_GFX12_DEFAULTS=0`）にしないと RDNA カーネルに到達しない。
- **persistent read が先に走ると無効**: `STRATA_HC_PERSIST=1` で `fused_gr_read_persist` が成功すると `fused_gr_read_multi` 自体が呼ばれない（`verify.cpp:1816`）。
- **モデル形状**: RDNA カーネルは `N=2560, HC=4, LR=320` の定数を持つ（`rdna_gr.cu:28`）。融合読みはこの形状でのみ有効（`fused_gr.cu:4522-4524`、`layer.cpp:1501`）。
- **重み形式**: `s_down` / `s_up` が非 null なら int8 + per-32 scale 版、null なら bf16 版を起動する（`rdna_gr.cu:512-543`）。
- **`STRATA_GR_RDNA=1` は GPU 世代を検査しない**。gfx11/gfx12 以外の AMD カードでも起動要求が通る（`rdna_gr.cu:554-555`）。世代チェックは `STRATA_HIP_FAST_DEC` 経由のときだけ。
- **既定値の相互作用**: Strata は `STRATA_GR_RDNA` を設定しないが、`STRATA_HIP_FAST_DEC=1` を gfx1100/1101/1102（`engine/include/strata/core/gfx11_extra.hpp:107`）と gfx1151 Windows（`engine/src/core/arch_defaults.cpp:212`）の既定として注入する（ユーザー設定は上書きしない、`arch_defaults.cpp:336`）。`STRATA_GFX11_WMMA_DEFAULTS=0` / `STRATA_GFX11_DEFAULTS=0` / `STRATA_DEFAULTS=026` で止まる（`gfx11_extra.hpp:27-37`）。ただし同じカードでは `STRATA_HC_Q8` も既定で有効なため、そのままでは Q8 読みが優先され RDNA カーネルは動かない（`STRATA_HC_Q8=0` が別途必要）。

## 実行時の詳細

- **評価時期**: `rdna_gr_enabled()` 内の `static const int env` を初回呼び出し時に 1 回だけ評価し、以後キャッシュする（`rdna_gr.cu:549-553`）。起動後の環境変更は反映されない。Q8 経路では呼ばないため評価がそこで遅延する。環境が 2（`STRATA_HIP_FAST_DEC` 経由）のときだけ `arch_ok[64]` にデバイス別の世代判定もキャッシュする（`rdna_gr.cu:556-564`）。
- **起動内容**: `launch_gr<T>` が bf16 版または int8 版の down/up を起動し、トークン数 1〜7 は専用インスタンス、それ以外は 8（`rdna_gr.cu:581-589`）。`STRATA_GR_FUSED=1` かつ barrier 確保時は persistent 版 `rdna_gr_fused` にする（`rdna_gr.cu:512-535`）。barrier の確保は `STRATA_GR_FUSED` が設定されていれば値によらず試みる（`rdna_gr.cu:575-577`）。
- **作業領域**: 呼び出し元の `xn_scratch` を分割して使い、追加のデバイス確保はしない（`rdna_gr.cu:569-572`）。
- **適用範囲**: verify ウィンドウ / MTP のマルチトークン GR 読み（`verify.cpp:1817`、`engine/src/core/mtp.cpp:1243` など）とベンチ・検査ツール（`engine/src/kernels/fused_gr_bench.cpp:124` など）。子プロセスへの転送や CLI による上書きはない（`terminal/data/settings-register.json:12885-12913` の `launch_files` / `engine_sets` も空）。

## ログと測定値

有効化を告げるログはない（既定でも有効でも何も出ない）。観測できるのは失敗経路だけ:

- 起動後エラー: `fused_gr_read_multi rdna: <cudaGetErrorString>` を stderr に出して `std::exit(1)`（`fused_gr.cu:4295-4299`）。
- 引数不整合: `fused_gr_read_multi: invalid arguments` / `... for token %d` で終了（`fused_gr.cu:4254-4257`、`:4266-4268`）。RDNA 経路に限らない。

`docs/SETTINGS.md:95` は本変数を「NVIDIA and AMD」とするが、NVIDIA の CUDA build では読み取りがスタブになる（`rdna_gr.cu:593-596`）ため一致しない。`docs/` に RDNA GR 経路の測定値（機種・モデル・量子化・回数付き）は見当たらないため、数値は引用しない。

## 根拠

- `engine/src/kernels/cuda/rdna_gr.cu:25`、`:28`、`:509-544`、`:548-565`、`:575-577`、`:593-596`
- `engine/src/kernels/cuda/fused_gr.cu:4284-4301`、`:4468-4484`、`:4522-4524`
- `engine/src/core/layer.cpp:1501`、`:1565`、`:1588`、`engine/src/core/verify.cpp:1816-1818`
- `engine/src/core/arch_defaults.cpp:212`、`:336`、`engine/include/strata/core/gfx11_extra.hpp:27-37`、`:107`
- `engine/include/strata/kernels/fused_gr.hpp:66-70`、`docs/SETTINGS.md:95`
