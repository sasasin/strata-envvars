# `STRATA_VERIFY_COHERENT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

HIP 版 verifier が使う、GPU と CPU で共有する mapped host memory の割当経路を切り替える診断用 A/B 変数です。`STRATA_USE_HIP` を定義したビルドでのみ値を読み、設定が有効なら `hipHostMalloc` を `hipHostMallocMapped | hipHostMallocCoherent` 付きで直接呼びます。ここで割り当てる verifier の staging 領域には、handshake 用の flags や token/row データが含まれます。通常の CUDA ビルドではこの変数を読みません。根拠: `src/core/verify.cpp:189-199,313-325,627-645`。

## 値と判定

文字列全体や数値としての妥当性は検査しません。共通 helper `env_on()` は、値が設定され、空でなく、先頭文字が `0` でなければ有効とします。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0` または `0` で始まる文字列（例: `0abc`） | 無効 |
| その他の空でない文字列（例: `1`, `false`, `-1`, ` 1`） | 有効 |

大文字小文字、後続文字、数値範囲は判定に影響しません。`g_coherent` は HIP ビルド時のグローバル定数として初期化されるため、起動後の環境変更は反映されません。根拠: `src/core/verify.cpp:192-198`。

## 有効になる条件

- `STRATA_USE_HIP` が定義されたビルドでのみ `g_coherent` が定義されます。CUDA ビルドでは環境変数の読み取りも割当切替もありません。根拠: `src/core/verify.cpp:196-199,313-323`。
- 変数が有効なとき `mapped()` は明示的な HIP coherent allocation を行い、失敗時は `false` を返します。その場合、通常の `cudaHostAlloc` 経路には fallback しません。unset または無効値なら通常経路に進みます。根拠: `src/core/verify.cpp:313-325`。
- SYCL 側の `sycl/src/core/verify.cpp` にも同じ名前の読み取り定義がありますが、そのファイルの `mapped()` は `window_host_uncached()` に応じて `strata::host_malloc_polled()` または `sycl::malloc_host()` を呼び、`g_coherent` を参照しません。このため、SYCL 実装の割当経路はこの値では切り替わりません。根拠: `sycl/src/core/verify.cpp:89-100,229-242`。

## 実行時の詳細

HIP 版 verifier の `mapped()` は、値が有効なら `hipHostMalloc(h, bytes, hipHostMallocMapped | hipHostMallocCoherent | portable flag)` を呼びます。portable flag は `peer_portable()` が真の場合だけ追加されます。無効なら `cudaHostAlloc(..., cudaHostAllocMapped | portable flag)` を呼び、どちらの経路も成功後に host 側をゼロ初期化して device pointer を取得します。staging 領域や plan 領域の割り当て失敗は `verify: mapped staging allocation failed` または `verify: mapped plan allocation failed` として返されます。根拠: `src/core/verify.cpp:313-325,627-655`。

`STRATA_VERIFY_TRACE` も有効で、HIP 版の trace buffer の作成まで進むと、stderr に `coherent words explicit`（本変数が有効）または `coherent words default`（無効）を含む行を出します。本変数だけを設定してもこのログは出ません。根拠: `src/core/verify.cpp:716-731`。

## 根拠

- 値の読み取りと判定: `src/core/verify.cpp:189-199`。
- HIP 版での割当経路: `src/core/verify.cpp:313-325`。
- verifier staging/plan での使用と失敗文字列: `src/core/verify.cpp:627-655`。
- 条件付き trace ログ: `src/core/verify.cpp:716-731`。
- SYCL 版の読取定義と、変数に依存しない割当: `sycl/src/core/verify.cpp:89-100,229-242`。
- HIP 互換ヘッダーでは `cudaHostAlloc` が `hipHostMalloc` に対応付けられます: `include/strata/hip_compat/cuda_runtime.h:65-80`。

この commit の `docs/DETAILS.md` には本変数の説明は見つからず、根拠にできる説明は verifier ソースの #649 コメント（gfx1030 の verify timeout 調査向け A/B）です。性能や timeout への効果を示す測定結果は、この調査では確認できませんでした。
