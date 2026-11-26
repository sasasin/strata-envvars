# `STRATA_VERIFY_STEPPED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL verifier の speculative window 実行を、doorbell の各 serve point で分割した command graph として実行するための opt-in です。window 内の各 segment を完了させてから CPU experts を処理し、後続 segment を投入するため、segment 実行中に host と kernel が互いの store を読む構成を避けます。変数が有効でも、all-resident 経路では CPU serve はなく、window 開始時に host flag を立てる処理になります。通常の未設定時は既存の graph / host wait 経路です。実装は `engine/sycl/src/core/verify.cpp` の `Verifier::capture` と `Verifier::run` にあります（`verify.cpp:192-194`, `2098-2105`, `2476-2494`）。

この読み取りは SYCL 実装にあります。CUDA/HIP 側がこの名前を読む実装は確認できません。設定レジストリ上の名前の登録は実際の環境読み取りではなく、実際の読み取り箇所は SYCL verifier の `env_on("STRATA_VERIFY_STEPPED")` です。

## 値と判定

`env_on` は `std::getenv` で取得し、値が存在し、先頭文字が NUL でも `'0'` でもなければ true にします。文字列全体や数値としての parse はしません（`engine/sycl/src/core/verify.cpp:151-154`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL verifier | false | `1`, `true`, `false`, ` 0`, `01` | 空文字、`0`, `0anything` |

大文字小文字や空白を検査しません。したがって `false` や先頭が空白の ` 0` も有効、`01` は先頭が `0` のため無効です。境界は先頭 1 文字だけで決まり、値の残りは無視されます。`g_stepped` は翻訳単位の初期化時に一度だけ評価されるため、プロセス起動後の環境変更は反映されません（`verify.cpp:191-194`）。

## 有効になる条件

- この読み取りがあるのは `engine/sycl` の verifier です。SYCL 以外の backend で有効になるとはソースから確認できません（`engine/sycl/src/core/verify.cpp:187-194`）。コメントは Arc A-series / DG2 を動機として挙げていますが、値判定自体に GPU 型の guard はありません（`engine/sycl/include/strata/core/verify.hpp:400-405`）。
- `STRATA_VERIFY_EAGER` が未設定で all-resident でない場合、`capture` が segment capture を選びます。`STRATA_VERIFY_EAGER` が空文字を含め設定されている場合はこの分岐を抑止し、通常の capture ではなく eager replay を選びます（`verify.cpp:2098-2105`, `2479-2480`, `2587-2590`）。
- all-resident 判定 (`ar_on()`) は `all_resident_ && !ar_off_` です。そこで verifier は serve segment ではなく全体の graph を使い、`STRATA_VERIFY_STEPPED` が有効なら launch 前に host flag を立てます。all-resident 状態は verifier 初期化時の residency 表と各 window 前の更新で決まります（`engine/sycl/include/strata/core/verify.hpp:364-370`, `engine/sycl/src/core/verify.cpp:897-917`, `2035-2048`, `2479-2490`）。
- `STRATA_VERIFY_EAGER` が未設定で segment 方式が選ばれても、`remote_opt_` が設定されていると stepped run は `false` を返し、`verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` をエラーにします（`verify.cpp:2493-2495`）。
- `STRATA_VERIFY_SPLIT` の初期値は未設定時 true で、値の先頭が `0` の場合だけ false です。true なら CPU serve point に加えて VRAM expert group 後にも split point を記録します（`verify.cpp:2067-2077`）。
- `STRATA_VERIFY_PIPE` は segment 間に split point があるとき、値の先頭が `0` でなければ CPU pool 処理を helper thread と次の GPU segment に重ねます。未設定・空文字・`true` は有効、`0` や `0anything` は無効です。未設定時に helper thread を使わない serial 経路ではなく、split point のある場合は helper thread 経路が既定です（`verify.cpp:2525-2557`）。
- `STRATA_VERIFY_HOST_UNCACHED` が未設定または `env_on` 判定で無効なら stepped 時の window host buffer は通常の host USM 側を選びます。有効なら uncached host allocation を維持します。この判定は関数内 static cache です（`verify.cpp:309-330`）。

## 実行時の詳細

`g_stepped` はプロセス開始時に読み取られます。doorbell 経路では `capture_segments` が command graph の記録を始め、record 中の `step_hook_` が各 CPU serve 後の境界を記録します。`STRATA_VERIFY_SPLIT` が有効なら `step_hook2_` が VRAM expert group 後の境界も記録します。segment graph は window token 数 `T` ごとの `seg_[T]` に保持され、既存の segment があれば再 capture しません（`verify.cpp:2051-2087`, `2098-2105`）。

実行時は各 serve segment を投入し、serve point で queue drain を待って doorbell sequence を確認し、plan を設定して CPU pool にその layer/group の CPU experts を処理させます。次 segment が split point なら `STRATA_VERIFY_PIPE` の設定に応じ CPU pool を helper thread で GPU segment と重ね、そうでなければ順に実行します。その後 flag B と通常の window flag を上げて GPU 側を進めます（`verify.cpp:2493-2586`）。通常の分割なし経路では host が各 layer の ring を spin wait するコードがありますが、stepped run はその逐次 wait loop を通りません（`verify.cpp:2623-2645`）。

変数が有効でも、test stall 条件が成立した all-resident window は `stepped_ar` が false になり、通常の stall 用処理に進みます（`verify.cpp:2479-2480`, `2620-2637`）。doorbell stepped run が remote expert opt で拒否された場合や segment capture / 実行で失敗した場合は verifier が false とエラー文字列を返します。GPU window 全体の同期失敗も `verify: ...` のエラーで返されます（`verify.cpp:2082-2095`, `2493-2495`, `2583-2586`, `2753-2781`）。

## ログと測定値

この変数自体を有効化したことを示す専用ログはありません。別途 `STRATA_VERIFY_NODES` が設定されている場合、segment capture 時に stderr へ `strata verify: the %d-token window as %zu graph segments` を出します。このログ条件は値ではなく設定有無です（空文字でも出力。`verify.cpp:2089-2090`）。remote expert opt の拒否時は上述のエラー文字列が verifier の呼び出し元へ返ります。

ソースコメントには、Arc A770 / xe / Coder IQ1_M / 8K prompt で host memory を uncached にした場合 GPU が window あたり約 70 ms CPU を待ち、uncached を外すと約 42 ms、decode が 22.8–25.0 から 26.9–28.9 tok/s と記録されています。これはコメントに記載された条件下の値であり、本調査で再測定した値ではありません（`verify.cpp:309-314`）。

## 根拠

- `engine/sycl/src/core/verify.cpp:151-154` — `env_on` の値判定。
- `engine/sycl/src/core/verify.cpp:191-194` — `g_stepped` の初期化時読み取り。
- `engine/sycl/src/core/verify.cpp:2051-2095`, `2098-2105` — segment graph capture と eager / all-resident 分岐。
- `engine/sycl/src/core/verify.cpp:2384-2400`, `2476-2495`, `2525-2586`, `2623-2645` — window 実行、CPU serve、helper、失敗条件。
- `engine/sycl/include/strata/core/verify.hpp:364-370`, `400-411` — all-resident 定義と stepped hook の説明。
