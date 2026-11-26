# `STRATA_Q6_PLANAR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL native Q6_K 出力 head を GGUF の 210-byte block 配列から、ql・qh・scale・d の16-byte load に適した plane 配置へ変換し、その配置を登録した重みを planar MMVQ kernel で読むかを制御する。格納する量子化要素自体は同じで、GGUF 配列の元 allocation は変換成功後に解放される。対象は `engine/sycl` の実装であり、CUDA/HIP/CPU 側にこの環境変数の読取り実装はない。`--native-head-gguf`（`--native` から補完される場合を含む）で Q6_K の native output head を読み込んだときに使われる。該当 head が無い、または型が Q6_K でない場合は作用しない（`engine/sycl/src/program/generate.cpp:1965-1966,2597,4578-4587`; `engine/sycl/src/core/native_head.cpp:87-96`）。

## 値と判定

`native_q6_k_planar_enabled()` が `std::getenv` の結果を調べ、値全体が1文字の `0` のときだけ無効にする。数値変換や trim、大文字小文字変換はない。空文字は設定済みだが無効条件に一致しないため有効。`00`、`0anything`、`false`、` 0`、`1` も有効である（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3099-3105`）。

| ビルド／経路 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL native Q6_K head | 有効 | 空文字を含む、`0` 以外のすべての文字列 | 完全一致の `0` |

この変数を直接切り替える CLI 引数はない。Q6_K output head については `STRATA_Q6_PACKED` が有効（`native_q6_k_packed_enabled()` が完全一致の `1` を読む）なら packed 変換が先に選ばれ、planar 化されない。MTP draft head でも packed が有効なら planar adopt は呼ばれない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097`; `engine/sycl/src/core/native_head.cpp:93-96`; `engine/sycl/src/core/mtp.cpp:865-872`）。

## 有効になる条件

- `engine/sycl` の SYCL 実装を使うこと。ソース中の読取りと plane kernel／registry は `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp` にある。
- native output head をロードする経路では、`output.weight` が Q6_K（型 ID 14）で、`--native-head-gguf` が指定されていること。通常経路は multi-GPU でない場合にロードし、layer split では最後の stage でロードする。`--native` は `--native-head-gguf` が空なら同じ preset を使う（`engine/sycl/src/program/generate.cpp:2597,4350-4357,4575-4587`; `engine/sycl/src/core/native_head.cpp:92-96`）。
- `STRATA_Q6_PACKED` が有効でないこと。有効条件は完全一致の `1`。packed と planar は同時に選ばれず、packed が先に優先される（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097,3935-3938`; `engine/sycl/src/core/native_head.cpp:93-96`）。
- 変換対象は `weights != nullptr`、`n_in > 0`、`n_in` が256の倍数、`n_out > 0` であること。外れる場合は元の重みポインタを返し、変換しない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3112-3114`）。
- MTP の draft vocabulary subset は、Q6_K head で `--mtp-q4` を使わず、subset を作る経路で planar gather／adopt の対象になり得る。既に planar な Q6_K head と `--mtp-q4` の組合せは `mtp.bind` が拒否し、`mtp.cpp:280` のエラーを返す（`engine/sycl/src/core/mtp.cpp:821-823,841-872,275-281`）。
- DFlash2 は vocab subset を作るとき、Q6_K head が planar 登録済みなら plane gather を使う。gather 用 allocation が確保できない場合は bind が失敗し、生成／serve の開始を拒否する。DFlash2 自体は一枚の GPU・一要求の経路に制限される（`engine/sycl/src/core/dflash2.cpp:263-281,316-330`; `engine/sycl/src/program/generate.cpp:4557-4567,7892-7903`）。

## 実行時の詳細

設定は `native_q6_k_planar_enabled()` 内の関数ローカル `static const bool` に保存され、最初に評価された値がプロセス内で再利用される。したがって、最初の評価後に環境を変更しても反映されない。native head のロード時、Q6_K かつ packed 無効の場合に判定し、条件を満たすと `native_q6_k_planar_adopt()` が planar allocation を作成する。変換成功時は queue を待ち、元 allocation を解放して新しい pointer を登録する。Q6_K MMVQ 呼び出しは registry に登録された pointer と shape が一致すれば planar kernel を起動し、登録がなければ通常経路へ続く（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3099-3107,3112-3147,3007-3035,3935-3938`）。

変換先 allocation の確保に失敗（確保時の例外も含む）した場合は元の GGUF 配置を保持する。SYCL 例外による変換失敗も元 pointer を返す。MTP の subset は、元 head が planar なら plane gather を試み、成功時は最初に用意した row-major subset allocation を解放して planar subset に置き換える。gather が `nullptr` を返した場合、MTP は row gather にフォールバックする（`engine/sycl/src/core/mtp.cpp:840-853`）。DFlash2 は同じ場合に `dflash2: no room for the draft head's planar copy (a Q6_K output head); STRATA_Q6_PLANAR=0 starts the engine with the GGUF layout` を返し、初期化を失敗させる（`engine/sycl/src/core/dflash2.cpp:263-272,323-330`）。

## ログと測定値

- planar 変換成功時: `strata: STRATA_Q6_PLANAR: the %s (%d x %d) is stored as 16-byte-aligned planes (same bytes)`（stderr）。
- planar 変換先の VRAM を確保できない場合: `strata: STRATA_Q6_PLANAR: no VRAM for the %s's planar copy (+%.1f MiB), keeping the GGUF layout`（stderr）。
- 変換中の SYCL 例外: `strata: STRATA_Q6_PLANAR conversion failed: %s`（stderr）。
- subset gather 成功時は `strata: STRATA_Q6_PLANAR: the %s (%lld x %d) is gathered from the planar head`、SYCL 例外時は `strata: STRATA_Q6_PLANAR gather failed: %s`（stderr）。確保失敗による gather の `nullptr` 返却自体は helper でログを出さない。
- `docs/INTEL.md:461` は Q6_K output/MTP head を plane 配置にする設定として記載しているが、条件付きの測定環境・回数は併記されていないため、性能値は記載しない。

## 根拠

- 読取り・文字列判定・cache: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3099-3105`
- 変換条件、確保 fallback、変換後の登録とログ: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3112-3151`
- planar registry を使う dispatch: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3007-3035,3935-3938`
- output head の適用条件と packed 優先: `engine/sycl/src/core/native_head.cpp:87-96`
- native head をロードする CLI 経路: `engine/sycl/src/program/generate.cpp:1965-1966,2597,4575-4587`
- MTP subset・`--mtp-q4` 拒否・gather fallback: `engine/sycl/src/core/mtp.cpp:271-281,821-872`
- DFlash2 planar gather と失敗経路: `engine/sycl/src/core/dflash2.cpp:263-281,316-330`
- Strata 資料との照合: `docs/INTEL.md:461`
