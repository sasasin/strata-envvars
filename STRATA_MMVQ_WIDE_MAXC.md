# `STRATA_MMVQ_WIDE_MAXC`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL版の native Q6_K MMVQ が wide カーネルを使う際に許可する、入力列数 `ncols` の上限を指定します。これは処理全体の列数制限ではなく、wide Q6_K カーネルを選ぶ条件の一つです。条件から外れた呼び出しは、その後の rowwarp カーネルまたは通常の MMVQ カーネルへ進みます。

## 値と判定

値は `std::atoi` で `int` に変換され、環境変数文字列全体の検証や範囲 clamp はありません。先頭の空白と符号は `atoi` の規則で扱われ、数値の後ろにある文字列は変換結果に影響しません。数値として始まらない文字列と空文字は 0 になります。

| 設定 | `wide_maxc` |
|---|---:|
| 未設定、`STRATA_MMVQ_A2` が有効（未設定または `atoi` の結果が非0） | 8 |
| 未設定、`STRATA_MMVQ_A2=0`（または `atoi` の結果が0） | 4 |
| 設定済み | `atoi` の変換結果 |

たとえば `3tail` は 3、`abc`、空文字、`0` は 0 です。上限が 0 以下なら、`ncols >= 1` との条件を満たせず wide カーネルは選ばれません。1〜7ならその数までが候補、8以上なら通常の有効範囲（1〜8）が候補です。上限値を8に clamp するコードはありません。

## 有効になる条件

この変数を読むのは `sycl/src/kernels/cuda/native_mmvq.dp.cpp` の SYCL 移植版です。SYCL ビルドの CMake は CUDA `.cu` に対応する `.dp.cpp` があればその移植コピーを選ぶため、この実装は SYCL engine の native MMVQ 経路に組み込まれます。CUDA 側の `src/kernels/cuda/native_mmvq.cu` には、この名前の参照はありません。

設定値が wide カーネル上限に反映されるのは、Q6_K (`ggml_type == 14`) の MMVQ 呼び出しが packed Q6_K 経路で処理されず、次の条件を満たす場合です。

- `STRATA_MMVQ_WIDE` によって wide カーネルが有効である（未設定なら有効、設定時は `atoi` の結果が非0）。
- `1 <= ncols <= STRATA_MMVQ_WIDE_MAXC`。
- `n_in` が256の倍数である。
- `n_out >= wide_min`。`STRATA_MMVQ_WIDE_MIN` が設定されていればその `atoi` 値、未設定なら `STRATA_MMVQ_A2` が有効なとき0、無効なとき4096です。

通常の native MMVQ の入力契約では `1 <= ncols <= 8` です。ただし Q6_K 関数は wide 判定を `validate_shape()` より先に行います。そのため、契約外の `ncols > 8` が渡され、かつ `STRATA_MMVQ_WIDE_MAXC` がその数以上で他の wide 条件も成立すると、switch の `default` 分岐が `launch_q6k_wide<8>` を起動してしまいます。上限を8より大きくしても有効な列数が増えるわけではなく、契約外入力が wide 分岐に入る可能性を広げます。wide 条件を満たさない場合でも、`ncols` が1〜4、`STRATA_MMVQ_RPW` の値が正、`n_in` が256の倍数なら後続の rowwarp 経路が選ばれることがあります。それ以外は通常の Q6_K MMVQ 経路に進み、そこで `validate_shape()` が入力を検証します。

## 実行時の詳細

`native_q6_k_mmvq()` は最初に packed Q6_K 経路を試します。その経路が処理を引き受けると wide 判定には到達せず、この変数も初期化されません。packed 経路が処理しない最初の呼び出しで、`wide_maxc` は関数内の `static const int` として一度だけ評価されます。そのため、読み取り後にプロセス環境を変更しても上限は再評価されません。未設定時の既定値で参照する `q6k_a2()` も、同じく static 値として初回評価後に保持されます。

wide カーネルが選択されると `ncols` 1〜7は列数ごとのテンプレート版を起動し、8は `launch_q6k_wide<8>` を起動します。変数による選択や fallback 専用のログ出力はありません。呼び出し元は native Q6_K の検証処理、layer 計算、native output head などにあります。

## 文書との照合

`docs/INTEL.md` は、SYCL版Q6_K wideカーネルの整列ロード対応と、その測定時の性能・出力一致を記録しています。また `STRATA_MMVQ_A2=0` で旧経路へ戻す説明がありますが、`STRATA_MMVQ_WIDE_MAXC` の値や個別効果は説明していません。したがって、本書では性能差をこの上限の効果として主張しません。

## 根拠

- `sycl/CMakeLists.txt:87-107,205-216` — SYCL ビルドのソース解決と `native_mmvq` の kernel target。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1534-1537` — `STRATA_MMVQ_A2` の判定。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1989-1990` — wide カーネルの既定有効状態。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2120-2125` — 通常経路で行う `ncols` を含む形状検証。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2699-2723,3426-3459` — packed 経路、wide 上限判定と起動、rowwarp/通常経路への継続。
- `sycl/src/core/native_head.cpp:112-120`, `sycl/src/core/verify.cpp:1025-1027` — native MMVQ の engine 呼び出し例。
- `docs/INTEL.md:448-455` — Q6_K wide カーネルの背景と資料中の測定記録。
