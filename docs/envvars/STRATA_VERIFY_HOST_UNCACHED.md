# `STRATA_VERIFY_HOST_UNCACHED`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL verifier の mapped host buffer を確保するとき、`STRATA_VERIFY_STEPPED` が有効な場合にも uncached host memory を使うかを選びます。これは stepped mode 自体を有効にする変数ではありません。stepped mode が無効なら、この変数の値によらず verifier は uncached allocation 関数を選びます。

## 値と判定

共通の `env_on()` は `getenv()` で値を読み、未設定・空文字・先頭文字が `0` の値を false、それ以外を true とします。文字列全体や数値としての妥当性は調べません。

| `STRATA_VERIFY_STEPPED` | `STRATA_VERIFY_HOST_UNCACHED` | `window_host_uncached()` の結果 |
|---|---|---|
| 無効 | 任意（未設定を含む） | true |
| 有効 | 未設定、空文字、`0` または `0...` | false |
| 有効 | 先頭が `0` 以外の非空文字列 | true |

したがって、stepped mode が有効なときは `1`、`true`、`false`、`-1` などはいずれも true になり、`0foo` は false です。大文字小文字、空白、後続文字は検査されません。

## 有効になる条件

- 対象は SYCL backend の verifier 内です。CUDA/HIP 側の同名変数の読み取りはこの commit では確認できません。
- `STRATA_VERIFY_STEPPED` が無効ならこの変数は結果に影響しません（短絡評価によりこの変数の `getenv()` 自体も呼びません）。有効時にだけ、この変数が uncached allocation の選択を上書きできます。
- `window_host_uncached()` の結果が true でも、Level Zero 上で実際に uncached allocation を得るかは別条件です。`strata::host_malloc_polled()` は `STRATA_HOST_UNCACHED` を別途評価し、その値が先頭 `0` でなく、queue backend が Level Zero の場合に Level Zero の uncached host allocation を試します。条件不成立または割り当て失敗時は `sycl::malloc_host()` に fallback します。

## 実行時の詳細

`STRATA_VERIFY_STEPPED` は `verify.cpp` の namespace-scope `const bool` として初期化時に一度読み取られます。対象変数は `window_host_uncached()` 内の function-local `static const bool` として、最初の呼び出し時に一度だけ評価されます。どちらも値をキャッシュするため、プロセス起動後の環境変更は再評価されません。

この結果は `mapped()` が verifier 用の mapped buffer を確保する際に使われます。true の場合は `strata::host_malloc_polled()`、false の場合は直接 `sycl::malloc_host()` を呼びます。確保に失敗するか host pointer が null の場合、初期化側は `verify: mapped staging allocation failed`（または plan buffer 用の `verify: mapped plan allocation failed`）をエラーとして返します。`mapped()` 内で発生した SYCL exception は stderr に例外内容とソース位置を出して `exit(1)` します。

`STRATA_VERIFY_STEPPED` のソースコメントは、stepped window では各 segment が待つ host flag を submit 前に立て、segment 完了後に GPU の ring/payload を host が読むため、走行中の host/GPU 相互参照用 uncached memory が不要になると説明しています。対象変数を true にすると、この方式でも uncached allocation 関数を選び続けます。変数自体が変更するのは buffer allocation 経路であり、stepped mode の segment 実行方法ではありません。

## 根拠

- `sycl/src/core/verify.cpp:93-105` — `env_on()` の規則と `STRATA_VERIFY_STEPPED` のプロセス内初期化。
- `sycl/src/core/verify.cpp:219-242` — 対象変数を含む判定、allocation 関数の選択、失敗時の戻り値と例外処理。
- `sycl/src/core/verify.cpp:459-542,549-550,621-625` — verifier の mapped staging、plan、trace buffer で `mapped()` を使う箇所。
- `sycl/src/core/verify.cpp:1752-1759,2065-2084` — stepped mode の capture/実行経路と remote expert opt に関する制限。
- `sycl/include/strata/sycl_queue.hpp:63-78` — `host_malloc_polled()` の `STRATA_HOST_UNCACHED`、Level Zero 条件、fallback。
- `sycl/include/strata/core/verify.hpp:358-363` — stepped mode の設計説明。`docs/DETAILS.md` にはこの変数の個別説明を確認できませんでした。
