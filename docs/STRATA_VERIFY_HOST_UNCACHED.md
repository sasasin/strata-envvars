# `STRATA_VERIFY_HOST_UNCACHED`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

SYCL verifier の window buffer を uncached host allocation にするか、doorbell payload を uncached store にするかを選びます。`STRATA_VERIFY_STEPPED` が有効な場合、この変数が未設定または無効値なら、window buffer に通常の host USM を使い、segment 内の payload を通常 store にします。stepped mode が無効ならこの変数に関係なく uncached 側の経路です。

対象実装は `sycl/src/core/verify.cpp` のみです。CUDA/HIP 実装でこの名前を読む箇所は見つかりませんでした。

## 値と判定

`env_on()` は `getenv()` の値が null でなく、空文字でなく、先頭文字が `0` でない場合に true を返します。文字列全体や数値としては parse しません。

| 値 | `STRATA_VERIFY_STEPPED` が有効な場合 |
|---|---|
| 未設定 | 無効。通常 host USM と通常 payload store の経路 |
| 空文字 | 無効 |
| `0`, `0anything` | 無効 |
| `1`, `true`, `false`, `2`, ` 0` | 有効。先頭文字が `0` 以外で空でないため |

大文字小文字、空白、数値としての妥当性は検査しません。`STRATA_VERIFY_STEPPED` が無効なら、`!g_stepped || env_on(...)` の短絡評価により本変数を読みません。この場合は値の内容にかかわらず uncached 側が選ばれます。

根拠: `sycl/src/core/verify.cpp:92-95,103,224-227`。

## 有効になる条件

- SYCL verifier のコード経路で使われます。`STRATA_VERIFY_STEPPED` が有効な場合に、この変数が既定の uncached 選択を上書きします。
- stepped mode の window buffer 割り当ては `Verifier::init()` の mapped staging で行われます。`STRATA_VERIFY_EAGER` が設定されて stepped segment capture を使わない場合でも、mapped buffer の割り当て選択自体には影響します。
- `STRATA_HOST_UNCACHED` は下位の `host_malloc_polled()` が Level Zero の uncached host allocation を使うかに影響します。したがって本変数が uncached 側を選んでも、`STRATA_HOST_UNCACHED=0`、非 Level Zero backend、または Level Zero allocation の失敗時は、実際の割り当てが `sycl::malloc_host()` に fallback する場合があります。
- `STRATA_DOORBELL_PLAIN` が明示されると、doorbell payload store の通常/uncached 判定にも影響します。getter は設定値の先頭が `1` なら通常 store、そうでなければ uncached store を選びますが、stepped capture 中の通常 store 指定も別途 OR されます。

## 実行時の詳細

`g_stepped` はプロセス初期化時に `STRATA_VERIFY_STEPPED` を `env_on()` で読みます。本変数の判定結果は `window_host_uncached()` 内の function-local `static const bool` に保存され、最初の呼び出し後は環境を書き換えても反映されません。最初の呼び出しは mapped buffer の確保時です。

`window_host_uncached()` が true なら、`mapped()` は `strata::host_malloc_polled()` を呼びます。Level Zero backend かつ下位 helper が uncached allocation を有効にしていれば `ZE_HOST_MEM_ALLOC_FLAG_BIAS_UNCACHED` を指定した割り当てを試み、それ以外や失敗時は helper 内で `sycl::malloc_host()` に fallback します。false なら `mapped()` が直接 `sycl::malloc_host()` を使います。対象 buffer には token、step、position、commit、PLE、output、activation、expert IDs/weights、handshake flags、plan などが含まれます。

stepped mode の segment graph capture 中、`PlainPayload` は `window_host_uncached()` が false の場合に payload の通常 store を有効にします。これらの payload は segment 完了後に host が読むためです。true の場合はこの scoped 指定を行わず、通常は uncached store が使われます。ただし `STRATA_DOORBELL_PLAIN` の明示設定は別途作用します。

実装コメントには、Arc A770（xe）、Coder IQ1_M、8K prompt の条件で、uncached 設定時は GPU が window あたり約70 ms CPU を待ち、外した場合は約42 ms、decode が22.8–25.0から26.9–28.9 tok/sになったと記録されています。これはソースコメントに記載された測定であり、一般的な性能保証ではありません。`docs/DETAILS.md` にはこの変数名や上記の測定値に対応する記述を確認できませんでした。

根拠: `sycl/src/core/verify.cpp:218-241,533-549,1687-1693,1734-1742`; `sycl/include/strata/sycl_queue.hpp:63-78`; `sycl/include/strata/sycl_doorbell.hpp:100-112`; `sycl/src/kernels/cuda/elementwise.dp.cpp:628-635,735-740,763-767`。
