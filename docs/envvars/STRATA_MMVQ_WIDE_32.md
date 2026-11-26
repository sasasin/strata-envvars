# `STRATA_MMVQ_WIDE_32`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Intel Arc 向け SYCL エンジンの native MMVQ において、Q8_0 と IQ4_NL の量子化行列積に使う wide-32 kernel を選ぶ。既定では有効で、無効にすると対象の行列積は既存の small/multi kernel に進む。対象関数は `native_q8_0_mmvq` と `native_iq4_nl_mmvq` で、CUDA/HIP 等の別実装にはこの名前の読み取り箇所はない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2155-2161, 4139-4161`）。

## 値と判定

`wide_32()` は `std::getenv` で設定有無を調べ、設定されていれば `std::atoi(...) != 0` を使う。文字列全体の妥当性検査や clamp はない。`atoi` が先頭の整数部分を変換するため、数字の後ろに続く文字は判定に影響しない。数値に変換できない文字列や空文字は 0 として扱われる（同 `:2155-2157`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| SYCL の対象経路 | 有効（`getenv` が null） | `1`、`-1`、`1suffix`、` 1tail`（`atoi` が非ゼロ） | 空文字、`0`、`0anything`、`true`、空白だけ（`atoi` が 0） |

判定は真偽文字列や先頭文字ではなく整数変換後の非ゼロ判定なので、`true` は有効値にならず、大文字小文字の区別も判定要素ではない。数値部分の前の空白は `atoi` が読み飛ばし、数値部分の後ろは無視する。範囲検査は実装されていない（同 `:2155-2157`）。

## 有効になる条件

- 読み取りは `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあり、SYCL エンジンに組み込まれた経路でのみ作用する。Strata の設定資料も Intel Arc の環境変数として掲載している（`engine/sycl/CMakeLists.txt:273-282` が native_mmvq の SYCL kernel source を追加し、`docs/INTEL.md:437-460` が Intel Arc 向け設定として掲載）。
- 対象は GGML type 8 の Q8_0 と type 20 の IQ4_NL。各型の native MMVQ 呼び出しから `try_wide32` に到達する必要がある（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4213, 4139-4161`）。
- wide kernel を選ぶには `ncols` が 1〜8 で、`n_in` が 32 の倍数であることが必要。条件を満たさなければ `try_wide32` は false を返し、small/multi kernel に進む（同 `:2160-2172, 4148-4161`）。
- Q8_0 では、登録済みの適合 packed weight が見つかると `q8_packed_mmvq` が wide-32 判定より先に処理を終える。packed 登録は `STRATA_Q8_PACKED` が文字列 `1` と完全一致し、行列形状が適格な場合に行われる（同 `:4148-4150, 3054-3065, 2673-2695`）。
- Q8_0 ではさらに、B60 MTP cache が要求され、packed weight または single-actor 条件が成立し、列数が 1/4/8 で、該当 weight の cache hit がある場合は別の probe 経路が先に return する（同 `:4141-4146`）。その分岐の要求条件は `STRATA_PRIVATE_B60_NEXT_POOL` と `STRATA_PRIVATE_MTP_Q8_SOA` の両方が設定され先頭文字が `1`、かつ weight が packed 状態か、`STRATA_PRIVATE_BMG_SINGLE_ACTOR` が設定され先頭文字 `1` であること。さらに現在 device と行列・列数に一致する cache hit が必要（`engine/sycl/include/b60_mtp_q8_cache.hpp:5-9`, `engine/sycl/include/b60_layout_state.hpp:7-10`, `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4141-4146`）。
- ソースに、この変数の値による CLI 引数との優先順位、サーバーモードやモデル状態による上書きはない。上記の型・形状・先行経路によって wide-32 を通らない場合は、この変数が有効でも当該呼び出しでは使われない。

## 実行時の詳細

`wide_32()` 内の関数ローカル `static const bool` が初回評価時に値を保存する。評価は Q8_0 の先行 cache/packed 経路を通らず `try_wide32` に来たとき、または IQ4_NL が同関数を呼んだときに発生する。その後にプロセス環境を変更しても、このプロセス内の判定には反映されない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2155-2161, 4141-4161`）。

有効かつ形状条件を満たす場合、列数に合わせた 1〜8 列の `native_mmvq_wide32_kernel` を SYCL queue に投入し、結果を `y` に書く。Q8_0 と IQ4_NL はそれぞれ専用 traits で重みを読み、Q8_1 活性値との積を行う。無効または形状条件外なら、Q8_0 は `small_mmvq<Q80Block, 8>`、IQ4_NL は `small_mmvq<IQ4NLBlock, 4>` にフォールバックする（同 `:2090-2118, 2120-2144, 2146-2172, 4148-4161`）。

## ログと測定値

この切り替え専用の有効・無効ログや警告は、読み取り・分岐箇所にはない。wide kernel を選ぶ経路は投入後に `launch_check()` を呼ぶが、同関数の実装に由来する診断内容はこの変数の値を説明するログではない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4148-4161`）。本書では Strata の現行設定資料に対象スイッチの比較可能な測定条件・測定値を確認できなかったため、性能値は記載しない。

## 根拠

- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2155-2172` — 値の取得・static cache・整数判定・wide kernel の列数と入力幅条件。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2090-2153` — Q8_0 / IQ4_NL traits、wide kernel の計算・出力。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4139-4161, 4204-4213` — Q8_0 / IQ4_NL の dispatch と先行・fallback 経路。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2673-2695, 3054-3065` — Q8_0 packed 経路の優先とその有効条件。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4141-4146`, `engine/sycl/include/b60_mtp_q8_cache.hpp:5-9`, `engine/sycl/include/b60_layout_state.hpp:7-10` — Q8_0 の B60 MTP cache hit 時の先行経路と要求条件。
- `engine/sycl/CMakeLists.txt:273-282`, `docs/INTEL.md:437-460` — SYCL kernel source の追加と設定資料上の Intel Arc 向けの位置づけ。
