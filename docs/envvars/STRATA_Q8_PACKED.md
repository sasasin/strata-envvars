# `STRATA_Q8_PACKED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Q8_0 重みをロード時に qs（量子化値）面と d（fp16 scale）面へコピーし、decode の native MMVQ がそのレイアウトを使うようにするスイッチ。CUDA/HIP 共通実装では eligible な Q8_0 行列について元の GGUF レイアウトを残した追加コピーを作り、SYCL 実装も同様にコピーを作る。元の行列は prompt 側の GEMM 用に残る。カーネルコメントでは量子化し直さず同じ int8 値と scale を配置し直す実装としている（`engine/src/kernels/cuda/native_mmvq.cu:2663-2671`、`engine/src/core/native_dense.cpp:498-516`、`engine/sycl/src/core/native_dense.cpp:353-390`）。

## 値と判定

CUDA/HIP と SYCL の `native_q8_0_packed_enabled()` は `std::getenv` の結果が存在し、かつ文字列全体がちょうど `1`（次の文字が NUL）である場合に有効とする。`atoi` や大文字小文字変換はしない。unset、空文字、`0`、`true`、`01`、`1anything`、先頭や末尾に空白がある文字列はすべてこの判定では無効。読み取り結果は関数内 `static` に保存される（`engine/src/kernels/cuda/native_mmvq.cu:2983-2989`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3054-3060`）。

| 実行経路 | unset | `1` | その他の値 |
| --- | --- | --- | --- |
| CUDA/HIP native カーネル | 無効。ただし CUDA ビルドで `STRATA_Q8_SM60=1` なら別ルートで packed 有効 | 有効 | 対象変数としては無効。別ルートの `STRATA_Q8_SM60=1` は独立して有効になり得る |
| SYCL native カーネル | 無効 | 有効 | 無効 |
| standalone `strata-q36` | 起動時に `1` を設定するため有効 | caller の値を維持し、その値が厳密に `1` の場合だけ有効 | caller の値を維持するため無効 |

CUDA/HIP 側の `STRATA_Q8_SM60` は同じ enabled 判定に OR される別スイッチで、HIP では常に無効、CUDA では厳密な `1` のとき有効。`STRATA_Q8_INPLACE=1` も CUDA 専用の独立経路で、追加コピーではなく eligible な行列を packed 形式で配置する（`engine/src/kernels/cuda/native_mmvq.cu:2625-2636`、`2638-2649`、`2983-2994`）。

## 有効になる条件

- native dense loader が対象行列をロードし、Q8_0（GGUF type 8）の 2 次元行列として扱うこと。`blk.1.ple_key.weight` は PLE 専用カーネルがあるため対象外（`engine/src/core/native_dense.cpp:459-471,498-503`、`engine/sycl/src/core/native_dense.cpp:353-359`）。
- CUDA/HIP の通常 packed kernel と SYCL では、形状が `n_in > 0`、32 の倍数、`n_in / 32 >= 2 * WARPS * WARP / 8`、`n_in <= 4096`、`n_out >= 2048` を満たすこと。現行カーネルの通常設定（`WARPS=4`, `WARP=32`）では入力幅 1024～4096、出力幅 2048 以上に相当する（`engine/src/kernels/cuda/native_mmvq.cu:2681-2683,2762-2765`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2526-2527,3062-3065`）。
- CUDA ビルドの `STRATA_Q8_SM60=1` 経路は形状条件が異なり、`n_in >= 128` かつ 32 の倍数、`n_out > 0` で eligible。HIP と SYCL はこの別経路を使わない（`engine/src/kernels/cuda/native_mmvq.cu:2625-2636,2991-2995`）。
- CUDA ビルドの `STRATA_Q8_INPLACE=1` とその形状・共有メモリ条件を満たす場合は、`STRATA_Q8_PACKED` が無効でも別途 in-place packed が使われる。HIP ではこの in-place 機能は無効（`engine/src/kernels/cuda/native_mmvq.cu:2991-3012`）。
- CUDA/HIP の Qwen3.6 専用 `strata-q36` は `STRATA_Q8_PACKED` が未設定なら、Linux では `setenv(..., "1", 0)`、Windows では未設定の場合に `_putenv_s(..., "1")` を行う。空文字を含め、設定済みの値は保持する（`engine/src/qwen35/q36_engine.cu:5424-5430`）。
- HIP の通常エンジンではアーキテクチャ既定値テーブルが環境変数を設定する。gfx1151 では `STRATA_GFX1151_DEFAULTS` が先頭文字 `0` でないとき、離散 RDNA3 gfx1100/1101/1102 では `STRATA_GFX11_DEFAULTS` が先頭文字 `0` でないとき `1` が候補になる。すでに `STRATA_Q8_PACKED` が設定済みなら、その値（空文字や `0` も含む）を上書きしない。gfx12 はこのスイッチをテーブルに含めない（`engine/src/core/arch_defaults.cpp:28-42,64-80,302-324`、`engine/include/strata/core/gfx11_extra.hpp:41-57`）。通常エンジンは HIP ビルドでデバイス情報取得後、カーネルが環境を初回参照する前に既定値を適用する（`engine/src/program/generate.cpp:4287-4320`）。
- Qwen3.6 以外に、この変数自体を設定する専用 CLI 引数は確認できない。対象値は環境から読み、Qwen3.6 の未設定補完または上記 HIP アーキテクチャ既定値が環境に値を設定する。通常の HIP `--serve` 経路にも同じエンジン起動時既定値が適用される。

## 実行時の詳細

CUDA/HIP の native dense loader は Q8_0 行列を読み込んだ後、対象変数が有効で形状が eligible なら、ホストで packed 配置を作り、デバイスに同じサイズの別領域としてアップロードする。packed 側の登録は元の重みポインタをキーに行われる。後続の `native_q8_0_mmvq()` は登録済み重みなら packed カーネルを試し、使えない形状・列数などでは `small_mmvq` の通常レイアウトへ戻る（`engine/src/core/native_dense.cpp:498-516,630-649`、`engine/src/kernels/cuda/native_mmvq.cu:2767-2805,3699-3704`）。SYCL 側も dense load 時に同サイズの packed 領域を作って登録し、MMVQ で packed 経路を試した後、条件に合わなければ通常 kernel を使う（`engine/sycl/src/core/native_dense.cpp:353-390,456-473`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3054-3089,4138-4151`）。

変数の値そのものは `native_q8_0_packed_enabled()` の初回呼び出し時に一度だけ読み取られる。通常の HIP エンジンでは先にアーキテクチャ既定値の適用を試みる。Qwen3.6 専用エンジンでは CLI の処理後、重みのロードより前に未設定値を補う。初回判定後に環境を変更してもキャッシュ済み判定は変わらない。`STRATA_Q8_PACKED=1` の通常追加コピーは元の各 eligible 行列と同サイズのデバイス領域を追加で使う。CUDA/HIP と SYCL の双方でロードまたはコピーに失敗すると `native dense upload ...` / `native dense packed upload ...` のエラー文字列を設定してロードを失敗させる（`engine/src/core/native_dense.cpp:485-486,508-515`、`engine/sycl/src/core/native_dense.cpp:347-349,375-388`）。

Qwen3.6 エンジンではロード時に Q8_0 行列を eligible 判定し、対象なら packed copy を作って登録する。専用経路の一部は packed eligibility と enabled 判定を見て独自 Q8 kernel の採否も切り替える（`engine/src/qwen35/q36_engine.cu:1439-1450,2426-2432,2528-2535`）。

## ログと測定値

追加コピーを作った CUDA/HIP または SYCL native dense loader は stderr に `native dense: STRATA_Q8_PACKED=1 packed %zu Q8_0 matrices for decode (+%.1f MiB)` を出す。対象形状の行列が無い、変数が無効、または loader を通らない場合、このログは出ない（`engine/src/core/native_dense.cpp:651-653`、`engine/sycl/src/core/native_dense.cpp:475-477`）。Qwen3.6 のロードはこの native dense ログ経路ではなく、ここに示したログ文言の出力は確認できない。

ソースコメントには gfx1151 での形状別測定値が記録されているが、この文書では別環境へ一般化できる測定値として扱わない。コメント記載条件は S26、UD-IQ4_XS の 8 実層、形状ごとの paired 測定、1～5 列で、`n_in=2560` から `6144/10240/12288` への変更が呼び出し当たり +10～12%（engine trace では該当呼び出し -10.7%）、`n_in=6144` から 2560 は単体 +2～4% だが engine では -3%、`n_out<2048` は不利とされ、現行の形状 gate に反映されている（`engine/src/kernels/cuda/native_mmvq.cu:2672-2675`）。

## 根拠

- 値の読み取り・キャッシュ・CUDA 専用の別経路: `engine/src/kernels/cuda/native_mmvq.cu:2625-2649,2983-2995`
- SYCL の値判定と形状条件: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3054-3065`
- 通常形状条件と packed MMVQ の分岐: `engine/src/kernels/cuda/native_mmvq.cu:2762-2805,3699-3704`
- CUDA/HIP と SYCL のロード時コピー、登録、ログ、失敗: `engine/src/core/native_dense.cpp:498-516,630-653`、`engine/sycl/src/core/native_dense.cpp:353-390,456-477`
- HIP アーキテクチャ既定値と適用タイミング: `engine/src/core/arch_defaults.cpp:28-42,64-80,302-324`、`engine/include/strata/core/gfx11_extra.hpp:41-57`、`engine/src/program/generate.cpp:4287-4320`
- Qwen3.6 の未設定時既定値とロード時適用: `engine/src/qwen35/q36_engine.cu:1439-1450,5424-5430`
