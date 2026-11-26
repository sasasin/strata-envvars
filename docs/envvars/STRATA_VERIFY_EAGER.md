# `STRATA_VERIFY_EAGER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

SYCL backend の `strata::core::Verifier` が通常の decode verify window を実行するとき、window body を command graph として capture/replay する代わりに、`record_window()` を各回そのまま呼び出して queue に処理を投入します。カーネルや window の演算内容を選ぶ設定ではなく、投入経路を切り替える診断用スイッチです（`engine/sycl/src/core/verify.cpp:2098-2112,2384-2398,2587-2591`）。

## 値と判定

7 箇所の実読み取りはいずれも `std::getenv(...) != nullptr` または `== nullptr` の設定有無判定です。文字列の変換や比較はありません。未設定なら通常の graph 経路、設定済みなら有効です。したがって空文字、`0`、`false`、`0anything`、大文字小文字を問わず、どの値でも設定済みとして扱われます。無効値エラー、数値範囲、clamp、CLI 引数による上書きはありません（`engine/sycl/src/core/verify.cpp:1051,2101-2105,2328,2479,2588-2590,2921`）。

| 条件 | unset | 設定済み（例） |
|---|---|---|
| SYCL `Verifier` の通常 window | graph capture/replay。stepped 条件を満たせば segment capture/run | eager queue 経路。`1`、空文字、`0`、`false` を含め有効 |
| slot batch (`run_slot_rows`) | graph replay | この関数は変数を参照せず graph replay |

## 有効になる条件

- 対象は `engine/sycl` の SYCL build に含まれる verifier です。`engine/sycl/CMakeLists.txt` は `src/core/verify.cpp` を engine library のソースに含めます（`engine/sycl/CMakeLists.txt:290-298`）。CUDA/HIP verifier に同名の実読み取りはありません。
- 通常の `Verifier::run()` が処理する decode window で使われます。prompt prefill の別実装や slot batch はこの切替の対象ではありません（`engine/sycl/src/core/verify.cpp:2384-2398,3649-3665`）。
- `STRATA_VERIFY_STEPPED` が有効でも、非 all-resident (`!ar_on()`) の `capture_segments()` と `stepped_run` は本変数が未設定の場合に限られます。設定時は通常の window body を queue に投入します。all-resident 側の `stepped_ar` は別条件で選ばれ、この変数だけでは抑止されません（`engine/sycl/src/core/verify.cpp:2098-2105,2476-2495,2587-2591,2618-2625`）。
- graph は `warm()` や最初の `run()` から `capture()` を呼んで準備します。変数が設定済みなら capture は成功扱いで戻り、window graph を作りません（`engine/sycl/src/core/verify.cpp:2098-2112,3272-3277`）。
- stage timing を併用する場合は別途 `STRATA_VERIFY_PROFILE` が設定されている必要があります。これは verifier 初期化時に設定有無で計測を有効化します（`engine/sycl/src/core/verify.cpp:816-829`）。この組み合わせで eager 経路は各 stage stamp の前に queue を wait し、host clock を記録します（同 `:1049-1056`）。

## 実行時の詳細

通常 window では `capture()` が graph の有無を確認し、未 capture の場合に `record_window()` を graph recording 内で呼んで graph を作ります。変数が設定されていれば graph の作成を省略します。`run()` の各 window では変数を再確認し、設定済みなら `record_window(T, cs_, err)` を実行、未設定なら保持 graph を replay します（`engine/sycl/src/core/verify.cpp:2098-2118,2384-2398,2587-2591`）。このため切替判定は `capture()` と `run()` では呼び出しごとに行われます。`record_window()` 内の profiling 用 `eager` は function-local `static const` なので、最初にその関数へ入った時点の設定有無を process 内に cache します（同 `:1049-1056`）。起動後に環境を変更する通常の CLI 経路はありません。

この分岐は window body を queue に再投入する方法を選びます。モデル、window size、sampling / commit の処理を本変数で切り替えるコードはありません。`run_slot_rows()` は `exec_bm_` の graph を直接 replay し、本変数を参照しません（`engine/sycl/src/core/verify.cpp:3649-3665`）。

## ログと測定値

本変数だけを有効にしたときの専用ログはありません。`STRATA_VERIFY_PROFILE` も有効で、single-group window (`G == 1`) の profile が記録されると、stderr に `verify stages T=%d (ms/window):%s` の形式で window ごとの stage 表を出します。これは eager stamp の host clock に基づく表です（`engine/sycl/src/core/verify.cpp:2918-2935`）。`STRATA_KPROF` を使う per-kernel 計測も eager decode を必要とする旨がコメントされています（`engine/sycl/include/strata/kprof.hpp:1-8`）。Strata の `docs/A770_SPEED_SPEC.md` には eager + profile で失敗した報告と、`STRATA_DOORBELL_NOCHECK` を追加した計測結果が記載されていますが、これは追加設定・対象機材を伴う同資料の調査記録です。現行 HEAD の本変数単独の性能値として一般化しません（`docs/A770_SPEED_SPEC.md:715-745`）。

実行中に `run()` が失敗すると、呼び出し側は `ERR <理由>` を stdout に出して終了コード 1 を返す通常の失敗経路を通ります。たとえば launch error は verifier が `verify: launch: ...` を返し、SYCL 例外は `record_verify_sycl_exception("window run", ...)` に渡されます（`engine/sycl/src/core/verify.cpp:2587-2607,3000-3003`; `engine/sycl/src/program/generate.cpp:12774-12778`）。本変数固有の無効値エラーや専用 fallback はありません。

## 根拠

- `engine/sycl/src/core/verify.cpp:1049-1056` — profiler 用 eager 判定の static cache と stage stamp。
- `engine/sycl/src/core/verify.cpp:2098-2118` — capture / stepped segment / graph 作成の条件。
- `engine/sycl/src/core/verify.cpp:2327-2336` — profile stamp readback の条件。
- `engine/sycl/src/core/verify.cpp:2384-2398,2476-2495,2587-2591` — 通常 window run と eager / graph / stepped 分岐。
- `engine/sycl/src/core/verify.cpp:2918-2935` — eager 時の stage profile 出力。
- `engine/sycl/src/core/verify.cpp:3649-3665` — slot batch は graph replay を直接行う。
- `engine/sycl/src/program/generate.cpp:12774-12778` — run failure の stdout / exit 経路。
- `engine/sycl/CMakeLists.txt:290-298` — SYCL engine への verifier 実装の組み込み。
- `engine/sycl/include/strata/kprof.hpp:1-8` — per-kernel profiler が eager decode を案内する注釈。
