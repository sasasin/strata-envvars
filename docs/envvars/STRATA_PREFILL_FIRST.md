# `STRATA_PREFILL_FIRST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の prompt prefill で、通常の `m.T` トークン単位の chunk より短い最初の chunk を指定する。対象 chunk が実行された後は残りを通常の `m.T` 単位で処理する。`Prefill::run_impl` の `chunk_len` が長さを決め、ループが各 chunk を処理する（`engine/sycl/src/prefill/prefill.cpp:2784-2797,2826-2829`）。

この分割により、PLE が有効な場合、最初の chunk の PLE 行読み込みは layer 0 の処理と並行して始まり、layer 1 で必要になる時点まで非同期に進む。PLE が無効でも chunk 長を決める分岐自体は実行されるが、PLE 読み込みとの重複は起きない（同 `:2772,2798-2812,2922-2929,3371-3375`）。この変数専用のログはない。

## 値と判定

`Prefill::run_impl` 内の関数ローカル `static` が最初の呼び出し時に `std::getenv` の返すポインターを一度取得する。各 `run_impl` 呼び出しでは、そのポインターが null かを見て、設定されていれば `std::atoll` で数値化する。unset の場合だけ `all_cached` に応じた既定値を使う（`engine/sycl/src/prefill/prefill.cpp:2791-2795`）。

| 条件 | unset | 有効になる値 | 無効または短縮されない値 |
|---|---|---|---|
| SYCL `Prefill::run_impl` | cache が全 expert を保持すれば 256、それ以外は 0 | `atoll` の結果が正で、かつ `first_chunk < m.T`、`n > 2 * first_chunk` のとき、最初をその token 数にする。例: `256`, `+256`, ` 256xyz` は数値化結果が 256 | 明示値 `0`、負数、数値に変換できない文字列、空文字は結果が 0 となり短縮しない。`first_chunk >= m.T` または prompt 長 `n <= 2 * first_chunk` でも短縮しない |

`atoll` による変換なので文字列全体の妥当性検査はせず、先頭空白と符号を許し、数値後方の文字列は無視する。例えば `256xyz` は 256、`xyz` は 0。大文字小文字の規則は該当しない。値の上限 clamp はこの箇所にはない。明示的な空文字は unset ではなく、`atoll("") == 0` 相当として既定値を無効化する。`m.T` と `n` による適用境界は `chunk_len` に記載された条件そのもの（同 `:2792-2796`）。

## 有効になる条件

- この読み取りは `engine/sycl/src/prefill/prefill.cpp` にあり、ここで確認できる適用先は SYCL の `Prefill::run_impl`。CUDA/HIP 等の別 backend に同名の実読み取りは見つからなかった（同 `:2692-2694,2792-2796`）。
- 短縮 chunk が選ばれるには、設定値または unset 時の既定値が正であること、`m.T` より小さいこと、prompt の残り長 `n` がその値の 2 倍を超えることが必要。満たさない場合は `min(m.T, n-c0)` による通常長になる（同 `:2793-2796`）。
- PLE 読み込みとの並行実行という効果には `ss.ple.ready() && LB <= 1 && 1 < LE` が必要。これを満たさない経路でも chunk 分割の値は計算される（同 `:2772,2922-2929,3371-3375`）。
- 別の最適化 `run_expert_window` のペア実行条件では `!std::getenv("STRATA_PREFILL_FIRST")` が要求される。したがって変数を設定すると、値が空・`0`・不正文字列で短縮 chunk が起きない場合も、その最適化の当該分岐を抑止する。さらに同分岐には `n_expert == 512`、`STRATA_DBG_NAN` 等が未設定、cache が全 expert 分未満など複数条件がある（同 `:5841-5848`）。

## 実行時の詳細

`all_cached` は各 `run_impl` 呼び出しで `m.cache` が存在し、slot 数が `n_layers * n_expert` 以上かを判定する。`STRATA_PREFILL_FIRST` の getenv ポインターは最初の `run_impl` 呼び出し時に static 保存される一方、`atoll` と unset 時の既定値選択は呼び出しごとに行われる（`engine/sycl/src/prefill/prefill.cpp:2791-2796`）。プロセス実行中に環境を書き換えた場合の反映は、この static ポインターを保持する実装から保証できない。

最初の chunk の長さはループの進み幅にも使われ、次の chunk は `c0 + T` から読み込みを始める。PLE が有効なら各 chunk の PLE 行は非同期タスクで集められ、layer 1 で必要になった時に待機・アップロードされる。PLE 行の gather 失敗時は `ple_next_err` を `err` に設定して `run_impl` が false を返す。アップロード失敗も `err` を設定して false を返す（同 `:2798-2812,2826,2922-2929,2931-2937,2945-2969`）。

## ログと測定値

変数の値や選択された初回 chunk 長を直接表示するログはない。通常の進捗経路では chunk ごとに `core::progress_at("reading the prompt (batched): preparing the chunk from token", p0)` が呼ばれる。`STRATA_TRACE` が設定されている場合は各 chunk で `strata trace: prompt chunk %lld of %lld` を stderr に出す（`engine/sycl/src/prefill/prefill.cpp:2826-2829`）。PLE 行の gather / upload の失敗は前節のとおり `err` として返される（同 `:2935-2937,2967-2969`）。

`docs/INTEL.md:210-211,455` は unset 時の 256 / 0 の条件をコードと同様に記載している。同文書には Arc Pro B70・IQ3_S の 4,095-token prompt で 784 から 1,002 tok/s という数値もコードコメントにあるが、これはコメント記載の測定であり、この調査で再計測した値ではない（`engine/sycl/src/prefill/prefill.cpp:2787-2790`）。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:2692-2699` — SYCL prefill の `Prefill::run_impl`。
- `engine/sycl/src/prefill/prefill.cpp:2772-2782` — PLE 適用条件。
- `engine/sycl/src/prefill/prefill.cpp:2784-2812` — 変数、既定値、chunk 長、PLE gather。
- `engine/sycl/src/prefill/prefill.cpp:2826-2829,2922-2969,3371-3375` — chunk 実行、PLE の非同期読み込みと利用・失敗経路。
- `engine/sycl/src/prefill/prefill.cpp:5841-5848` — 設定有無で抑止される別の実行分岐。
- `docs/INTEL.md:210-211,455` — 文書化された既定値の照合。
