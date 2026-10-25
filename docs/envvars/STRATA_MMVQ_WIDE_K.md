# `STRATA_MMVQ_WIDE_K`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

SYCL の native MMVQ で、`Q4_K`、`Q5_K`、`IQ4_XS` の積和計算に wide カーネルを使うかを切り替えます。既定では wide カーネルを試し、設定値が整数として 0 に変換される場合は従来の multi / small カーネルへ進みます。CUDA ネイティブ実装など、この変数を読まない経路には作用しません。

## 値と判定

値は `std::atoi()` で変換し、変換結果が 0 でない場合に有効です。文字列全体の妥当性検査やエラー通知はありません。

| 環境変数の状態・値 | wide カーネルの判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 無効（`atoi("")` は 0） |
| `1`、`2`、`-1` | 有効（変換結果が非 0） |
| `0`、`0suffix`、`nonnumeric` | 無効（変換結果が 0） |
| `1suffix` | 有効（`atoi` が先頭の整数部分を変換） |

`atoi` のため、先頭の空白や符号も整数変換の規則に従います。整数範囲外の入力に対する特別な処理、clamp、fallback は実装していません。根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1870-1873`。

## 有効になる条件

変数が有効でも、wide 経路を試すのは次の条件を満たす呼び出しだけです。

- 対象形式が `Q4_K`、`Q5_K`、`IQ4_XS` のいずれか。
- `ncols` が 1〜8。
- `n_in` が量子化ブロック幅 `QK` の倍数（これらの形式では形状検証も 256 要素単位）。

条件外の場合、または変数が無効の場合、呼び出し元は通常の `STRATA_WAVE_MMVQ` 判定を経て multi カーネル（`ncols > 1`）や single-column の small 経路へ進みます。wide 経路に `n_out` の下限条件はありません。ただし各 MMVQ 関数は先に shape・ポインター・stream を検証し、`n_out <= 0` なら例外にします。根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1874-1887,3036-3050,3259-3272,3350-3364`。

## 実行時の詳細

`native_mmvq()` は GGML type 12 を `Q4_K`、13 を `Q5_K`、23 を `IQ4_XS` の専用関数へ振り分けます。それぞれの関数が `try_wide()` を呼び、条件を満たせば `ncols` に対応する wide カーネルを起動して戻ります。wide カーネルでは 32 lane の sub-group で 1 row を計算します。条件に合わないと `try_wide()` は false を返し、各関数の従来カーネル選択へ続きます。根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1836-1887,3036-3049,3259-3272,3350-3364,3685-3702`。

判定結果は `wide_k()` 内の function-local `static const bool` に保存されます。したがって変数は最初の対象呼び出し時に一度だけ評価され、その後のプロセス内変更は反映されません。ログ出力や子プロセスへの値の転送は、この実装にはありません。

このコードは SYCL 側の native MMVQ 実装 `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあります。SYCL の CMake 設定は `native_mmvq` カーネルソースをビルド対象に含めています（`sycl/CMakeLists.txt:205-214`）。調査対象ソースで、この変数の読み取りはこの helper 1か所のみでした。

## 文書・測定値

`docs/INTEL.md` は wide カーネル導入後の段階別測定を記録し、最終的な各カーネル測定値の復帰スイッチとして `STRATA_MMVQ_WIDE_K=0` を挙げています。記録では wide K カーネル導入段階で decode が 57.1 から 62.6 tok/s になっていますが、この値は他の段階変更も含む一連の測定表の一項目です。`STRATA_MMVQ_WIDE_K` 単独の効果としては扱えません。カーネル別には IQ4_XS が 2 columns で 107 から 323 GB/s、Q4_K/Q5_K は 1.3〜1.6 倍と記載されています。これらは同資料に記された Intel B70 / SYCL ポートの測定条件に限る資料上の報告で、一般的な性能保証ではありません。根拠: `docs/INTEL.md:458-481`。

## 根拠

- 値の取得と既定値、static cache: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1870-1873`
- wide 経路の形状条件と column 数ごとの起動: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1874-1887`
- 対象形式の呼び出し、fallback: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3036-3050,3259-3272,3350-3364`
- native MMVQ の type dispatch: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3685-3702`
- SYCL カーネルのビルド対象: `sycl/CMakeLists.txt:205-214`
- 資料上の動作説明と測定記録: `docs/INTEL.md:458-481`
