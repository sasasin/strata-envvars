# `STRATA_MMVQ_WAVE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

gfx906 向け HIP ビルドの一部の native MMVQ 呼び出しで、既定の wave64 用カーネルを使うか、従来の CUDA レイアウトのカーネルへ戻すかを切り替える。変数が正確に文字列 `0` のときだけ wave64 経路を無効にする。CUDA レイアウトへ戻すときは multi-column 呼び出しが `launch_multi` に進み、wave64 経路では 1〜8 列（ビルド設定により最大 16 列）を同一のカーネルで処理する（`engine/src/kernels/cuda/native_mmvq.cu:2499-2505,2540-2579,2581-2594,3311-3324,3775-3818`）。

適用されるのは `native_mmvq` の通常経路が `small_mmvq` または `STRATA_WAVE_MMVQ` を呼ぶ型（Q4_0、Q5_0、Q8_0、IQ4_NL、Q2_0、Q3_K、Q4_K、Q5_K、Q6_K、IQ4_XS）。型やモデルの選択自体を変える設定ではない（`engine/src/kernels/cuda/native_mmvq.cu:2581-2606,3311-3325,3420-3440,3478-3490,3520-3530,3559-3573,3600-3624,3642-3655,3699-3704,3775-3818`）。

## 値と判定

`STRATA_HIP_GFX906` が定義されたソースだけで、名前空間スコープの `g_wave_off` が初期化される。値の数値変換はせず、`std::getenv` が null でなく、かつ文字列全体が `"0"` と一致する場合に限り `true`（wave64 を止める）となる。空文字は設定済みでも `"0"` と一致しない。大文字小文字、空白、数値としての妥当性は判定しない（`engine/src/kernels/cuda/native_mmvq.cu:2499-2505`）。

| ビルド条件 | unset | wave64 経路を止める値 | wave64 経路を止めない値 |
|---|---|---|---|
| gfx906 HIP（`STRATA_HIP_GFX906` 定義） | wave64 を使う | `0` のみ | 空文字、`1`、`true`、`00`、`0anything`、` 0` など |
| 通常の CUDA、wave32 HIP など（同 macro なし） | 該当なし | 該当なし | macro が空定義になるため、この変数による分岐なし |

値が `0` 以外なら、wave64 を止める条件は満たされない。したがって `0anything` も「0」扱いにはならず、wave64 経路を選ぶ。gfx906 で wave64 がコンパイルされない場合、この変数による動作の変更はない（`engine/src/kernels/cuda/native_mmvq.cu:2575-2579`）。

## 有効になる条件

- ビルドが `STRATA_HIP_GFX906` を定義している必要がある。CMake はこの macro を gfx906 HIP toolchain で定義し、`STRATA_HIP_GFX906` ビルドでは CUDA ターゲットを HIP 互換層経由で有効にする（`engine/CMakeLists.txt:91-103,233-240`; `engine/cmake/backends/hip.cmake:6-26`）。通常 CUDA や wave32 HIP ビルドでは対象の `#if defined(STRATA_HIP_GFX906)` が成立しない（`engine/src/kernels/cuda/native_mmvq.cu:2499,2575-2579`）。
- `native_mmvq` がこのファイルの wave 切替箇所まで到達する必要がある。Q6_K の出力 head が `STRATA_Q6_PACKED` により packed 化され registry に登録されると、`q6_packed_mmvq` が先に処理を終えて wave switch を通らない（`engine/src/kernels/cuda/native_mmvq.cu:2944-2953,3145-3150,3600-3614`; `engine/src/core/native_head.cpp:262-263`）。
- Q4_K、Q5_K、IQ4_XS、Q6_K の前段には RDNA 用カーネルの試行があるが、gfx906 では `rdna_mmvq.cu` の gfx906 除外側が false を返すため、この経路は wave 切替を迂回しない（`engine/src/kernels/cuda/rdna_mmvq.cu:20-23,484-493`; 呼び出し位置は `engine/src/kernels/cuda/native_mmvq.cu:3319-3320,3526-3527,3567-3568,3609-3610`）。
- CLI 引数やサーバーモードによる優先順位はなく、該当経路で同名の環境値を直接読む。別設定のうち、Q6_K packed head が実際に使われる場合は上記の先行経路が優先する。CUDA Tensor Core MMVQ は HIP では対応 GPU と判定されず、この分岐より先に成功しない（`engine/src/kernels/cuda/dense_i8_tc.cu:1683-1703`; `engine/src/kernels/cuda/native_mmvq.cu:3775-3805`）。

## 実行時の詳細

`g_wave_off` は関数内 `static` ではなく translation unit のグローバル変数で、初期化時に環境を読み取って以後の MMVQ 呼び出しで共有する。各呼び出しやリクエストでは再読込しないため、プロセス実行中に環境を変更しても反映されない。対象名を子プロセスへ渡す処理は確認できなかった（`engine/src/kernels/cuda/native_mmvq.cu:2505,2575-2579`）。

各カーネル関数は形状・ポインター・stream を検証したあと `STRATA_WAVE_MMVQ` を評価する。`g_wave_off` が false なら wave64 kernel を起動し、`launch_check()` の後に戻る。true ならこのマクロは何もしないため、同じ関数の既存 CUDA レイアウト処理へ続く。例えば Q4_0 など `small_mmvq` 経由の複数列は `launch_multi` へ進み、1 列は従来の単列 kernel を使う（`engine/src/kernels/cuda/native_mmvq.cu:2575-2606`）。Q2_0、Q3_K、Q4_K、Q5_K、Q6_K なども同じ切替 macro を各型の MMVQ 関数から呼ぶ（`engine/src/kernels/cuda/native_mmvq.cu:3311-3324,3420-3440,3478-3490,3559-3573,3600-3624`）。

通常の gfx906 ビルドでは `engine/src/kernels/cuda/native_mmvq.cu` が HIP 言語としてコンパイルされる（`engine/cmake/backends/hip.cmake:129-135`）。SYCL には同じ条件付きコードを含む移行済みコピー `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2337-2405` もあるが、通常の SYCL CMake 設定は `STRATA_HIP_GFX906` を定義しない（`engine/sycl/CMakeLists.txt:1-11,21-24`）。このコピーは移行生成コードとして独立した実装根拠にはせず、通常 SYCL ビルドでこの分岐が有効だとは扱わない。

完全一致検索で見つかる `engine/src/kernels/mmvq_multi_parity.cpp:245` と `engine/sycl/src/kernels/mmvq_multi_parity.cpp:296` の読み取りは parity test 専用で、アプリ本体の制御には含めない。CMake の `mmvq_multi_parity_cuda_layout` にある環境設定はそのテストを CUDA layout で起動するためのもの（`engine/cmake/strata_gpu_engine.cmake:801-810`）。`terminal/data/settings-register.json:25322`、コメント、および `docs/AMD_HIP.md:603` は名前の登録・説明であり、実行時の値読み取りではない。

## ログと測定値

この変数の値や切替について、実行時に専用ログを出すコードはない。wave64 起動後の CUDA/HIP ランタイムエラーは `launch_check()` が `native MMVQ launch: ` とランタイムのエラー文字列を付けた `std::runtime_error` にする。wave 切替関数の列数 switch に許容されない列数が渡る場合は `native MMVQ (wave) requires 1 <= ncols <= MAX_NCOLS` の `std::invalid_argument` になる（`engine/src/kernels/cuda/native_mmvq.cu:2491-2495,2548-2573,2575-2576`）。環境変数の無効値だけを理由にした警告・終了経路はない。

`docs/AMD_HIP.md:598-604` は gfx906 の MMVQ を wavefront 単位の実装として挙げ、`STRATA_MMVQ_WAVE=0` を CUDA layout へ戻すスイッチとして記載しており、コードの条件と一致する。同資料にこの変数の性能測定値はなく、`docs/DETAILS.md` にも対象変数の測定値は見つからなかった。

## 根拠

- 読み取り、コンパイル条件、値判定、切替 macro: `engine/src/kernels/cuda/native_mmvq.cu:2499-2505,2575-2579`
- 実際の型別 dispatch: `engine/src/kernels/cuda/native_mmvq.cu:2581-2606,3311-3324,3420-3440,3478-3490,3559-3573,3600-3624,3775-3818`
- gfx906 ビルド macro と HIP 言語化: `engine/CMakeLists.txt:91-103,233-240`; `engine/cmake/backends/hip.cmake:6-26,129-135`
- Q6_K packed の先行経路: `engine/src/kernels/cuda/native_mmvq.cu:2944-2953,3145-3150,3600-3614`; `engine/src/core/native_head.cpp:262-263`
- gfx906 における RDNA kernel の no-op: `engine/src/kernels/cuda/rdna_mmvq.cu:20-23,484-493`
- HIP で Tensor Core 経路を選ばない条件: `engine/src/kernels/cuda/dense_i8_tc.cu:1683-1703`
- SYCL 移行コードと通常ビルド設定: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2337-2405`; `engine/sycl/CMakeLists.txt:1-11,21-24`
- 設計資料との照合: `docs/AMD_HIP.md:598-604`; `docs/DETAILS.md`（対象変数への記載なし）
