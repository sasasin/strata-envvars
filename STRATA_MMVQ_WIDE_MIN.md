# `STRATA_MMVQ_WIDE_MIN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

SYCL backend のネイティブ Q6_K 行列ベクトル・行列行列積（MMVQ）で、wide Q6_K kernel を選ぶための `n_out` の下限を指定します。対象の読み取り箇所は `sycl/src/kernels/cuda/native_mmvq.dp.cpp` の1か所です。このソースは SYCL の `_kernel_cu` 群に含まれる `native_mmvq` の実装です（`sycl/CMakeLists.txt:205-213`）。

## 値と判定

値は `std::atoi` で整数に変換されます。文字列全体の妥当性検査はありません。先頭の空白と符号の後にある10進数字列が変換され、数字列の後ろは無視されます。数字が始まらない値（空文字を含む）は `0` になります。負数もそのまま閾値として使われ、通常の正の `n_out` はすべて `n_out >= wide_min` を満たします。変換後に値域チェックや clamp はありません。

| 環境変数の状態 | `wide_min` |
|---|---:|
| 未設定 | `STRATA_MMVQ_A2` が有効なら `0`、無効なら `4096` |
| 設定あり（空文字を含む） | `atoi` の結果。空文字・数字で始まらない値は `0` |
| 数字の後ろに文字が続く | 数字部分の値（例: `2048xyz` は `2048`） |

`STRATA_MMVQ_A2` 自体は別の関数内で、未設定なら有効、設定時は `atoi(value) != 0` で判定されます。したがって `STRATA_MMVQ_A2=0` では wide kernel の既定下限が `4096` になります。`STRATA_MMVQ_WIDE_MIN` に明示値があれば、その値がこの既定値に優先します。

## 有効になる条件

`wide_min` の判定だけでは wide kernel の起動は決まりません。Q6_K の呼び出しで、先行する packed-weight 経路が処理を終えず、次の条件も満たす必要があります。

- `STRATA_MMVQ_WIDE` による wide 経路が有効。未設定なら有効、設定時は `atoi(value) != 0`。
- `1 <= ncols <= wide_maxc`。`wide_maxc` は `STRATA_MMVQ_WIDE_MAXC` の明示値、または `STRATA_MMVQ_A2` が有効なら `8`、無効なら `4`。
- `n_in` が `256` の倍数。
- `n_out >= wide_min`。

従って、この変数は出力行数のゲートだけを変えます。たとえば閾値を `0` にしても、wide 経路が無効、列数が上限外、または入力幅が256の倍数でなければ wide kernel には進みません。条件に合わない場合、実装は後続の row-warp 経路または通常の Q6_K MMVQ 経路に進みます。なお `n_out <= 0` の検査は wide 分岐より後にあります。通常の正の形状では問題になりませんが、異常な `n_out` と負の閾値を同時に渡すと wide 分岐の条件式を通る可能性があり、通常の不正形状検査に先行します。

## 実行時の詳細

`native_q6_k_mmvq()` は最初に `q6_packed_mmvq()` を試し、登録済み packed weight が一致するなどの条件を満たせば、その経路から戻ります。この場合 `STRATA_MMVQ_WIDE_MIN` の値は参照されません。packed 経路が処理しなかった場合に限り、`wide_min` と `wide_maxc` の関数内 `static const` が初回評価されます。値はそのプロセスでキャッシュされ、後から環境を変更しても再評価されません。

条件を満たしたときは `ncols` に応じて `launch_q6k_wide<1..8>()` を選びます。wide kernel 内では別設定 `STRATA_MMVQ_WIDE_RPW` が行あたりの処理行数を選び、`STRATA_MMVQ_PF` が正の値なら先読み用kernel経路に分岐します。これらは `wide_min` の条件を置き換えません。

変数の読み取りや閾値選択について、専用ログ・警告・エラー出力は見つかりませんでした。コード上、値は kernel 選択にだけ使われます。`native_mmvq()` は GGML type `14` を `native_q6_k_mmvq()` に渡し、モデル層からは `sycl/src/core/layer.cpp:147-161` でネイティブ MMVQ が呼ばれます。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1534-1537`: `STRATA_MMVQ_A2` の未設定時既定値と `atoi != 0` 判定。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1989`: `STRATA_MMVQ_WIDE` の未設定時既定値と設定値の判定。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2699-2722`: packed Q6_K 経路が成立する条件と成功時の早期 return。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3426-3458`: packed 経路の後の `wide_min` 読み取り、wide kernel 選択条件、後続経路。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1689-1695,1701-1735`: wide Q6_K kernel 内の `STRATA_MMVQ_PF` / `STRATA_MMVQ_WIDE_RPW` の分岐。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3685-3702`: GGML type `14` の Q6_K dispatch。
- `sycl/CMakeLists.txt:88-106,205-214`, `sycl/src/core/layer.cpp:147-161`: `.cu` 指定から migrated `.dp.cpp` へのソース解決、SYCL kernel 群への `native_mmvq` 登録、層処理からの呼び出し。

`docs/DETAILS.md` と `docs/INTEL.md` を確認しましたが、`STRATA_MMVQ_WIDE_MIN` の直接説明は見つかりませんでした。性能値はこの変数の資料には記載していません。
