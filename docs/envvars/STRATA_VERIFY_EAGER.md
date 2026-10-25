# `STRATA_VERIFY_EAGER`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL verifier の通常 window 実行で、window を command graph として capture/replay する代わりに、`record_window()` の処理を実行ごとに queue へ再登録します。SYCL の stage profiler が有効な場合は、stage ごとに queue を待ち、ホスト時計で時刻を記録する経路も選びます。CUDA/HIP 実装にこの名前の読み取りはありません。

これは `sycl/src/core/verify.cpp` にある実装上の診断・実験用フックです。`docs/A770_SPEED_SPEC.md` は profiler の調査手段として扱い、受け入れ性能測定では unset にするよう記しています。

## 値と判定

数値や文字列を parse せず、`std::getenv("STRATA_VERIFY_EAGER") != nullptr` で判定します。したがって未設定だけが無効で、空文字、`0`、`false` を含む設定済みの値はすべて有効です。先頭文字、大文字小文字、数値範囲は調べません。

## 有効になる条件

- この判定があるのは SYCL backend の `sycl/src/core/verify.cpp` です。実行時にその verifier が使われる必要があります。
- `Verifier::run()` は window の capture を行ってから、通常は capture 済み graph を launch します。変数が設定されていれば `capture()` は window graph を作らず、`run()` が `record_window()` を直接呼びます。
- `g_stepped && !ar_on()` の場合、unset 時に選ばれる segment capture / stepped segment 実行を抑止し、通常の eager replay 分岐へ進みます。`g_stepped && ar_on()` の別分岐はこの条件で抑止されません。
- pipelined-window 経路は対応しません。`capture_all()` は設定時に window graph を作らずに戻りますが、後続の `pl_launch()` は `exec_[T]` を必要とし、未準備なら `verify: pipelined window not prepared (capture_all)` を返します。
- `STRATA_VERIFY_PROFILE` が有効で、`G == 1` の場合にだけ stage 表示が出ます。`STRATA_VERIFY_EAGER` 単独で profiler を有効にはしません。

## 実行時の詳細

`Verifier::run()` は `capture(T, err)` と commit capture の後、入力を stage します。eager が設定されていると、window の実行時に `record_window(T, cs_, err)` を呼び、戻り値に応じて launch 成否を扱います。unset 時の通常経路は `ext_oneapi_graph()` による graph launch です。eager 判定により、window graph の初回 capture と replay は行われません。`warm()` から `capture()` を呼んでも、eager 設定中は window graph を作りません。

`record_window()` 内の stage stamp は、初回の `record_window()` 呼び出しで `static const bool eager` に保存されます。ここが true なら profiler 有効時に stage ごとに `cs->wait()` して `steady_clock` の時刻を記録します。window 完了時、`prof_on_ && G == 1` なら `verify stages T=%d (ms/window):...` を stderr に出します。その他の capture/run/collect_profile の判定箇所は `getenv()` を都度呼ぶため、実行中に環境を変更した場合、stage stamp のキャッシュと他の分岐が異なる値を見る可能性があります。

この変数が token 計算の算術を変更するとはコードから確認できません。実行経路と同期・計測方法が変わります。性能や出力の同一性はこの調査では実測していません。

## 資料との照合

`docs/A770_SPEED_SPEC.md` は `STRATA_VERIFY_EAGER` を stage timing の候補として挙げ、受け入れ run では unset を指示しています。同資料は当時の build で `STRATA_VERIFY_EAGER=1` を含む profiler 実行が verify error になった記録も載せています（718-732行）。これは資料に記録された試行結果であり、本調査では再現実験をしていません。`docs/INTEL.md` 845行は変数名を列挙していますが、挙動の説明はありません。

## 根拠

- `sycl/src/core/verify.cpp:818-825`: profiler 用 eager 判定の static cache、queue wait とホスト時計による stage stamp。
- `sycl/src/core/verify.cpp:1726-1734`: stepped segment capture の分岐、設定時に window graph capture を省略。
- `sycl/src/core/verify.cpp:1946-1951`: eager 時に profiler device stamp のコピーを省略。
- `sycl/src/core/verify.cpp:1988-1999,2042-2043,2150-2154`: `run()` の capture、stepped 判定、eager replay と通常 graph launch。
- `sycl/src/core/verify.cpp:2401-2404`: profiler 条件と stage 表の stderr 出力。
- `sycl/src/core/verify.cpp:3568-3599,3639-3650`: `capture_all()` と pipelined window launch が window graph を要求する箇所。
- `docs/A770_SPEED_SPEC.md:416-420,654-657,716-732`: profiler 用途、受け入れ run で unset にする指示、資料内の過去の失敗記録。
- `docs/INTEL.md:845`: 変数名の列挙。
