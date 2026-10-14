# `STRATA_VERIFY_HOST_UNCACHED`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL verifier の window 用 host buffer と doorbell payload store を、stepped mode でも uncached 向け経路に保ちます。`STRATA_VERIFY_STEPPED` が有効な場合、この変数が未設定または無効値なら、verifier buffer は通常の `sycl::malloc_host` で確保し、window 内の doorbell payload は plain store にします。有効値なら buffer を `strata::host_malloc_polled` 経由で確保し、stepped mode 用の plain store 切り替えを行いません。

この名前を直接読む本番コードは `sycl/src/core/verify.cpp` のみです。CUDA/HIP 実装や同梱ツールでの読み取りは確認できません。

## 値と判定

`env_on()` は `getenv()` の結果が null でなく、かつ先頭文字が NUL と `'0'` のどちらでもない場合に true を返します。文字列全体の parse はしません。

| `STRATA_VERIFY_STEPPED` | 本変数 | `window_host_uncached()` の結果 |
|---|---|---|
| 無効 | 任意（本変数は短絡評価で読まれない） | true |
| 有効 | 未設定、空文字、`0` または `0...` | false |
| 有効 | 先頭が `0` 以外の非空文字列（例: `1`, `true`, `false`, `2abc`） | true |

したがって `false` は有効扱い、`0anything` は無効扱いです。大文字小文字、空白、数値としての妥当性は検査しません。`STRATA_VERIFY_STEPPED` 自体も同じ `env_on()` 判定です（`sycl/src/core/verify.cpp:92-103`）。

## 有効になる条件

- SYCL build の verifier 経路で使われます。ファイルは `sycl/src/core/verify.cpp` にあり、CUDA/HIP の verifier にはこの名前の参照がありません。
- `STRATA_VERIFY_STEPPED` が有効でない場合、`!g_stepped || ...` の短絡評価により本変数を読まず、uncached 経路が選ばれます。
- `STRATA_VERIFY_STEPPED=1` は stepped mode を要求します。実際に window を segment graph として処理する条件はさらに `!ar_on()` と `STRATA_VERIFY_EAGER` 未設定などに依存します。ただし `window_host_uncached()` の判定自体はそれらの条件を参照せず、`g_stepped` だけを参照します。
- `strata::host_malloc_polled()` を選んでも、Level Zero headers がビルド時に使えない場合、queue backend が Level Zero でない場合、または割り当てに失敗した場合には `sycl::malloc_host` に fallback します。Level Zero の uncached allocation を使うかどうかは別変数 `STRATA_HOST_UNCACHED` が制御します。
- doorbell payload の plain store は `STRATA_DOORBELL_PLAIN` によるグローバル判定とも OR で組み合わされます。その設定が plain を有効にすれば、本変数が uncached 経路を選んだ場合でも plain store になり得ます。

## 実行時の詳細

`window_host_uncached()` の結果は関数内の `static const bool` に保存されます。初回呼び出し後の環境変更は反映されません。`g_stepped` は翻訳単位の静的初期化で読み取られます（`sycl/src/core/verify.cpp:92-103,218-227`）。

結果が true なら `mapped()` は verifier の host/device mapped buffers を `strata::host_malloc_polled()` で確保し、false なら `sycl::malloc_host()` を直接呼びます。失敗時は stderr に SYCL exception の内容とソース位置を出し、プロセスを終了します（`sycl/src/core/verify.cpp:229-247,526-548`）。

stepped segment graph の capture 中は `PlainPayload` が `doorbell_plain_payload(!window_host_uncached())` を設定し、capture の終了時に false へ戻します。従って false の場合は、segment が drain して payload を読む設計に合わせて payload を plain store にします。kernel の publish はこの状態を doorbell の各 publish kernel に渡します（`sycl/src/core/verify.cpp:1679-1685`; `sycl/src/kernels/cuda/elementwise.dp.cpp:628-635,735-766`）。true の場合はこの stepped 専用 plain 切り替えをしません。グローバルな `doorbell_plain_payload()` の判定は引き続き適用されます。

ソースコメントは、A770 (`xe`), Coder IQ1_M, 8K prompt の計測として、uncached 設定ありの場合に GPU の CPU 待ちが約70 ms/window、なしで約42 ms/window、decode が22.8–25.0から26.9–28.9 tok/sになったと記しています。この記載はコードコメント上の特定条件の測定値で、一般的な性能保証ではありません（`sycl/src/core/verify.cpp:218-227`）。`docs/DETAILS.md` には本変数名やこの測定の説明を確認できませんでした。

## 根拠

- `sycl/src/core/verify.cpp:92-103` — env 値判定と `STRATA_VERIFY_STEPPED` の読み取り。
- `sycl/src/core/verify.cpp:218-247` — 値の cache、buffer allocator の選択、allocation failure 時の処理。
- `sycl/src/core/verify.cpp:526-548` — verifier buffer の割り当て呼び出し。
- `sycl/src/core/verify.cpp:1679-1685` — segment capture 中の plain payload 設定。
- `sycl/include/strata/sycl_queue.hpp:63-78` — `host_malloc_polled()` の Level Zero 条件、別変数、fallback。
- `sycl/src/kernels/cuda/elementwise.dp.cpp:628-635,735-766` — plain payload flag が publish kernel の引数になる経路。
- `sycl/include/strata/core/verify.hpp:358-364`; `sycl/src/core/verify.cpp:1729,2042-2043` — stepped window の背景と実行時の追加条件。
