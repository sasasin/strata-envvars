# `STRATA_PF_P1A_FL3`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP ビルドの P1A MoE prefill カーネルで、gate/up と down の起動構成を FL=3（interleaved dual-tile accumulators と XOR-swizzled double-buffered LDS）にするか選ぶ。無効時は各カーネルの既定テンプレート構成を起動する。変数は処理の種類・量子化形式・出力先を選ばず、同じ P1A 演算のカーネル構成だけを切り替える（`engine/src/prefill/moe_p1a.cu:514-557`）。

この環境変数を読むコードは `engine/src/prefill/moe_p1a.cu` に一箇所だけある。通常の CUDA ビルドではこのファイルは `strata_pf_own` に含まれず、HIP 用のソースとして追加される（`engine/cmake/backends/hip.cmake:30-47`、`engine/cmake/backends/cuda.cmake:135-150`）。候補一覧と設定レジストリの記載に対し、実装は NVIDIA/CUDA 経路ではなく HIP 経路に限られる。

## 値と判定

`p1a_fast_flags()` の初回呼び出し時に `STRATA_PF_P1A_PLAIN`、続いてこの変数を `std::getenv` で読み、値が空かどうかと先頭 1 文字だけを調べる。文字列全体の parse、数値検査、大文字小文字変換、空白除去はしない（`engine/src/prefill/moe_p1a.cu:514-520`）。

| ビルド / 条件 | unset または空文字 | 設定時に FL=3 となる値 | 設定時に FL=3 にならない値 |
|---|---|---|---|
| HIP、`STRATA_PF_P1A_PLAIN` が未設定・空・先頭が `1` 以外 | 現在の HIP device が非統合型 gfx1100 / gfx1101 / gfx1102 の場合だけ FL=3。それ以外は既定構成 | 空でない値の先頭文字が `1`。例: `1`, `10`, `1anything` | 空でない値の先頭文字が `1` 以外。例: `0`, `true`, ` 1`, `anything` |
| HIP、`STRATA_PF_P1A_PLAIN` の先頭文字が `1` | この変数の値にかかわらず既定構成 | 該当なし | `STRATA_PF_P1A_FL3=1` を含め、常に既定構成 |
| 通常の CUDA ビルド | この変数を読む P1A 実装を含まない | 該当なし | 該当なし |

空文字は設定値として扱われず、アーキテクチャ既定値へ進む。無効な非空文字列はエラーにならず FL=3 を無効にする。`STRATA_PF_P1A_PLAIN` は先に調べられ、空でなく先頭が `1` なら、FL3 の値や自動判定にかかわらず既定構成を選ぶ。たとえば `STRATA_PF_P1A_PLAIN=10` もこの優先条件に一致する（`engine/src/prefill/moe_p1a.cu:515-531`）。

自動判定は選択中 device の取得に失敗した場合、device index が 0–63 の範囲外の場合、device properties を取得できない場合も FL=3 にならない。device properties では `integrated == false` かつ `gfx_arch_is_discrete_rdna3` が真であることを条件とし、この helper は gfx1100 / gfx1101 / gfx1102 を認識する（`engine/src/prefill/moe_p1a.cu:523-531`、`engine/include/strata/kernels/gfx_arch.hpp:22-26`）。

## 有効になる条件

- HIP 用 Strata prompt-kernel ビルドであること。通常の CUDA ビルドには `moe_p1a.cu` が含まれず、この変数の読み取りもない（`engine/cmake/backends/hip.cmake:30-47`、`engine/cmake/backends/cuda.cmake:135-150`）。
- P1A 経路に FP16 input が渡されること。`STRATA_PF_P1A=1` が有効なら渡される。加えて `STRATA_PF_F16=2` が有効な場合も `p1a_input` が input を保持するため、`experts_native()` の型・容量条件が一致すれば P1A カーネルが選ばれ得る。`STRATA_PF_P1A` は文字列全体がちょうど `1` で、`dev_info().g11_wmma` も必要。Windows gfx1151 または discrete RDNA3 gfx1100/1101/1102 では起動時のアーキテクチャ既定値が `STRATA_PF_P1A` を設定する場合があるが、ユーザーが既に設定した値は保持される。discrete RDNA3 の既定値は `STRATA_GFX11_DEFAULTS=0`、`STRATA_GFX11_WMMA_DEFAULTS=0`、または `STRATA_DEFAULTS=026` によって省かれ得る（`engine/src/prefill/moe_fused_iq.cu:3612-3621, 3631-3637, 3656-3662`、`engine/src/core/arch_defaults.cpp:302-323`、`engine/include/strata/core/gfx11_extra.hpp:27-36, 87-109`、`engine/src/core/arch_defaults.cpp:190-214`）。
- P1A 対象の native expert 形式であること。基本対応は Q4_K gate/up と Q5_1 down。`STRATA_PF_P1A_L2` が有効なら Q4_K / Q5_K gate/up と Q5_1 / Q8_0 down の組み合わせまで広がる（`engine/src/prefill/moe_p1a.cu:509-512`、`engine/src/prefill/moe_fused_iq.cu:3623-3629, 3664-3668`）。
- 呼び出しごとに FP16 input が渡され、FP16 down output が要求され、down rotation がなく、gfx11 WMMA 対応であり、タイル数が 65,535 以下、かつ `n * kMoeFF * 2` bytes の FP16 H が確保済みであること。条件を満たさない呼び出しは P1A カーネル自体を使わず、後続の既存経路へ進むため、この変数も作用しない（`engine/src/prefill/moe_fused_iq.cu:3703-3715`）。
- P1A input は `STRATA_PF_P1A` または `STRATA_PF_F16=2` のいずれかが有効なときにだけ保持される。down FP16 の要求は `STRATA_PF_DM16` に加えて CPU 行がなく、peer 経路でなく、関連バッファが 16-byte 整列という条件を満たす必要がある（`engine/src/prefill/moe_fused_iq.cu:3612-3637, 3656-3662`、`engine/src/prefill/prefill.cpp:980-984, 5830-5845`）。
- アーキテクチャ既定の P1A 有効化は FL3 の自動選択とは別。Windows gfx1151 では P1A が既定で有効でも自動 FL3 は false になり、discrete RDNA3 では WMMA 既定値が有効なら P1A と FL3 自動判定の両方が有効になり得る。FL3 を明示すれば自動判定の device 条件は置き換わるが、P1A 呼び出し条件は引き続き必要（`engine/src/core/arch_defaults.cpp:190-214`、`engine/src/prefill/moe_p1a.cu:514-531`）。

## 実行時の詳細

`experts_native()` が上記の P1A 条件を満たすと、`p1a::gate_up()` と `p1a::down()` の両方を呼ぶ。両関数は `p1a_fast_flags()` の結果で FL=3 テンプレートか既定テンプレートを選び、同じ H / down 出力バッファへ起動する。P1A が実行されると FP16 down rows を使ったことと P1A 使用済みを記録し、カーネル起動エラーを確認してから戻る（`engine/src/prefill/moe_p1a.cu:534-557`、`engine/src/prefill/moe_fused_iq.cu:3703-3715`）。

FL3 と `STRATA_PF_P1A_PLAIN` の値は `p1a_fast_flags()` 内の関数ローカル `static const` に初回評価時に保存されるため、その後プロセス内で環境を変更しても再評価されない。自動判定時の device architecture 判定は device index ごとの `static` 配列に保存される。device 取得・properties 取得失敗はログを出さず既定構成へ進む（`engine/src/prefill/moe_p1a.cu:514-531`）。この環境変数を設定する Strata の CLI 引数は確認できなかった。`--gpu` は HIP の可視 device を起動前に選ぶため、自動判定に使われる現在の device に間接的に関係する（`engine/src/program/generate.cpp:3776-3797`）。

## ログと測定値

FL3 の値や選択した FL 構成を直接表示するログはない。`STRATA_PF_P1A` が有効で、最初の fused prompt chunk で P1A が一層以上実行された場合は、その chunk の最終層で stderr に `strata: prompt experts P1A (STRATA_PF_P1A=1): ...` の集計を一度だけ出す。この集計は P1A を使った型ペアと層数を報告するが、FL3 の有効・無効は区別しない。P1A 層がなければ行を出さない。`STRATA_PF_F16=2` 経由で P1A カーネルが実行されても `STRATA_PF_P1A` が有効でなければ、この集計関数は呼ばれない（`engine/src/prefill/prefill.cpp:2273-2308, 5858-5861`）。

P1A カーネルの起動エラーは stderr に `prefill fused experts (native): experts_native (P1A): <GPU runtime error>` を出して終了コード 1 で終了する（`engine/src/prefill/moe_fused_iq.cu:68-72, 3711-3714`）。FL3 の選択自体に伴う警告・エラーはない。ソースコメントには FL=0 が 40-CU gfx1151 で約 2.5% 速かったという記述があるが、モデル・OS・計測条件などが揃っていないため、測定結果としては扱わない（`engine/src/prefill/moe_p1a.cu:521-522`）。

## 根拠

- 候補名の直接参照は `engine/src/prefill/moe_p1a.cu:517` の `std::getenv`。同じ関数で `STRATA_PF_P1A_PLAIN` を先に判定する（`engine/src/prefill/moe_p1a.cu:514-520`）。
- FL3 と fallback のカーネル選択: `engine/src/prefill/moe_p1a.cu:521-557`。
- HIP ビルドへの組み込みと CUDA 側の除外: `engine/cmake/backends/hip.cmake:30-47`、`engine/cmake/backends/cuda.cmake:135-150`。
- P1A 自体の有効条件、対象形式、呼び出し境界: `engine/src/prefill/moe_fused_iq.cu:3612-3629, 3656-3668, 3703-3715`。
- アーキテクチャ既定値: `engine/src/core/arch_defaults.cpp:190-214, 302-323`、`engine/include/strata/core/gfx11_extra.hpp:27-36, 87-109`。
