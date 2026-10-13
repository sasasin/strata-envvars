# `STRATA_BF16_TC`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

CUDA/SYCL の BF16 プリフィル GEMM で、compute capability 7.x の GPU に対し、BF16 入力を FP16 に変換して FP16 GEMM 経路を使うかを切り替える。CUDA では既定で sm_70〜sm_74 が変換経路、sm_75〜sm_79 は BF16 GEMM のまま。`STRATA_BF16_TC` を指定すると 7.x で上書きできる。値 `2` はテスト用に FP16 経路を他の capability にも強制する。

## 値と判定

値は `bf16_path()` の初回呼び出し時に読み、空でない文字列は `std::atoi` で整数化する。`atoi` のため文字列全体の厳密な数値検証はなく、先頭に整数として読める部分があればその値になり、整数として読めない文字列は `0` になる。空文字・未設定は `-1`（指定なし）として扱う。

| GPU compute capability | 未設定または空文字 | `0` | `1` やその他の正の整数（`2` を除く） | `2` | 負の整数 |
| --- | --- | --- | --- | --- | --- |
| 不明（問い合わせ失敗を含む） | BF16 GEMM | BF16 GEMM | BF16 GEMM | BF16 GEMM | BF16 GEMM |
| 6.x | Pascal 用 FP32 経路を選択 | 同左 | 同左 | FP16 経路 | 同左 |
| 7.0〜7.4 | FP16 経路 | BF16 GEMM | FP16 経路 | FP16 経路 | FP16 経路 |
| 7.5〜7.9 | BF16 GEMM | BF16 GEMM | FP16 経路 | FP16 経路 | BF16 GEMM |
| 8.0 以上 | BF16 GEMM | BF16 GEMM | BF16 GEMM | FP16 経路 | BF16 GEMM |

`2` のテストモードは capability が取得できた場合に先に判定される。6.x の通常判定は指定値より先に行われるため、`2` 以外なら Pascal 用 FP32 経路が優先される。負値は明示指定として記録されるものの、通常の「指定なし」と同じ既定判定に進む。非数値文字列は `atoi` により `0` となり、7.x では無効化指定と同じ結果になる。

## 有効になる条件

- この分岐は CUDA/SYCL の BF16 プリフィル GEMM にあり、HIP ビルドでは `#if !defined(__HIPCC__)` により使用されない。HIP の BF16 GEMM は別の hipBLASLt/WMMA 経路を通る。
- 7.x の通常の切り替えは各 GPU の compute capability に基づく。現在の device ID と capability は最大 64 枚分を atomic 配列にキャッシュする。取得失敗時は capability `0` として扱い、BF16 GEMM のままにする。
- FP16 変換経路を選んでも、通常の FP16 代替経路は `N > 1` かつ `beta == 0.0f` のときだけ実行する。単一出力行や加算 GEMM（`beta != 0`）では BF16 GEMM に戻る。バッファを確保できない場合も BF16 GEMM にフォールバックする。
- Pascal の FP32 変換経路は `STRATA_EXPERIMENTAL_SM60` ビルドでだけ実装される。CUDA では実験ビルドで必要な変換バッファを確保できないとエラーを stderr に出して終了する。SYCL では確保できなければ後続の BF16 GEMM に進む。実験ビルドでない場合、6.x 用経路は選択値上は 2 でもコンパイルされず、通常の BF16 GEMM に進む。
- `STRATA_BF16_TC=2` の FP16 経路は上記の `N > 1` / `beta == 0` 条件を満たす場合に限り実際の積で使われる。CUDA/SYCL のコード上に capability 8.x 以上でもこの経路を選べるのはテスト用途としての分岐である。

## 実行時の詳細

CUDA 実装は `Gemm::bf16()` から `bf16_path()` を呼ぶ。FP16 経路では BF16 の重みと活性を FP16 に変換し、重みと活性の作業領域が収まるよう行・トークン方向に分割して `Gemm::f16()` を呼び、FP32 出力を作る。変換時、FP16 の有限範囲を超える値は ±65504 に clamp される。通常の BF16 経路は `cublasGemmEx` に BF16 入力を渡す。Pascal 実験経路では BF16 値を FP32 に正確に拡張して `cublasSgemm` を使う。

SYCL 実装も同じ値判定と capability の優先順位を持つ。FP16 経路では同じく変換後に FP16 GEMM を実行し、通常経路では oneMKL の BF16 GEMM を使う。SYCL 側では変換領域の確保に失敗したとき、または FP16 経路の適用条件を満たさないときに通常 GEMM へ進む。

環境値自体は `bf16_path()` 内の関数ローカル `static const` に保存されるため、プロセス起動後に環境を変更しても、最初の `bf16_path()` 呼び出し後は反映されない。関数内に CLI 引数や設定ファイル値との優先順位処理はない。変換は BF16 プリフィル GEMM に対するもので、モデル内のすべての GEMM や CUDA/HIP ドライバーの挙動を切り替える設定ではない。

`docs/OLDER_GPUS.md` は sm_75 の既定が無効で `=1` が opt-in、sm_80 以上には適用されないことを説明している。また FP16 tensor-core 経路と BF16 GEMM は丸め順が異なり、出力が bitwise 一致しないと記している。文書掲載の性能・精度値はその資料に記載された個別測定の報告であり、この調査で再測定した値ではない。

## 根拠

- `src/prefill/gemm.cu:462-530`: CUDA の適用範囲、変換の説明、既定値、値の parse、GPU capability ごとの経路選択。
- `src/prefill/gemm.cu:571-673`: CUDA `Gemm::bf16()` の条件、変換 GEMM、Pascal の実験経路、BF16 GEMM へのフォールバック。
- `sycl/src/prefill/gemm.dp.cpp:530-634`: SYCL の同じ適用範囲、値の parse、capability ごとの経路選択。
- `sycl/src/prefill/gemm.dp.cpp:746-830`: SYCL `Gemm::bf16()` の条件、変換経路と BF16 GEMM へのフォールバック。
- `include/strata/prefill/gemm.hpp:28-32`: BF16 GEMM API と旧世代 GPU の説明。
- `docs/OLDER_GPUS.md:87-110`: 実験ビルド、sm_75 での opt-in、sm_80 以降には適用されないこと、丸め差に関する説明。
