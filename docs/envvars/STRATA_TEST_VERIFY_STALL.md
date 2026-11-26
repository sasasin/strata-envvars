# `STRATA_TEST_VERIFY_STALL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

verify engine の fault-injection 用フック。正の整数 `N` を指定すると、各 `Verifier` の N 番目の verify window で最後の layer step の GPU 向け完了 flag を上げず、GPU の flag wait を意図的に残す。通常の計算結果を得る設定ではなく、window の stall と回復・終了経路を発生させる。実装は CUDA/HIP 共通側と独立した SYCL 側にある。いずれもこの読み取り・分岐に build macro のガードはない（`engine/cmake/strata_gpu_engine.cmake:310-316`、`engine/sycl/CMakeLists.txt:290-299`）。

## 値と判定

両実装ともプロセス起動時のグローバル初期化で `std::getenv` を呼び、設定されていれば `std::atoll` で符号付き 10 進整数へ変換する。文字列全体の妥当性検査、範囲検査、clamp はない。先頭の空白と符号は変換関数の規則に従い、数値の後ろは検査されない。空文字や数値に変換できない先頭文字列は通常 `0` となる。結果は `g_test_stall > 0` のときだけ比較に使われるため、0 以下は無効。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP verify (`engine/src/core/verify.cpp:654-657`) | `0`（注入なし） | 正の整数が window 番号に一致。`1` は最初、`3` と `3tail` は3番目 | 空文字、`0`、`-1`、`true`、`tail3` は `0` 以下または数値変換されず無効 |
| SYCL verify (`engine/sycl/src/core/verify.cpp:399-402`) | `0`（注入なし） | 同じ規則。`1` は最初、`3` は3番目 | 同じ規則 |

小数点や後続文字は全体検査されず、たとえば `2.9` は `2` として扱われる。大文字小文字の区別はない。`atoll` の結果が正でも、その番号の window が実行されなければ発火しない。変換範囲外の値に対する Strata 独自のエラー処理はない。

## 有効になる条件

- 対応する CUDA/HIP または SYCL engine が使われ、その `Verifier` の `run()` が対象番号の window まで進む必要がある。番号は各 verifier の `windows + 1` と比較される（CUDA/HIP: `engine/src/core/verify.cpp:3865`、SYCL: `engine/sycl/src/core/verify.cpp:2622`）。
- CUDA/HIP では対象 window に対する all-resident の早期 flag 経路を避け、通常の layer serving 経路に入る（`engine/src/core/verify.cpp:3865-3868,3979-3993`）。SYCL では all-resident 経路を避ける。`STRATA_VERIFY_STEPPED` が選ぶ stepped all-resident 経路も対象 window では無効化される（`engine/sycl/src/core/verify.cpp:2480,2622-2637`）。一方、非 all-resident の `stepped_run` 経路（`g_stepped`、segment があり、`STRATA_VERIFY_EAGER` 未設定）はこのフックを参照せず、通常の flag 抑止 loop にも入らないため、この環境変数による stall 注入は行われない（`engine/sycl/src/core/verify.cpp:2476-2480,2622-2637`）。
- SYCL の `STRATA_VERIFY_NO_HOST` が有効だと CPU layer-serving loop は実行されないが、対象窓で all-resident の flag を出す分岐も避けられるため、後続の window 同期が待ち続ける（`engine/sycl/src/core/verify.cpp:2620-2637,2749-2755`）。
- CLI 引数や別の設定値でこの環境変数を上書きする処理は、対象名の全参照にはない。`STRATA_VERIFY_TIMEOUT_S`（CUDA/HIP）や `STRATA_RING_TIMEOUT_S`（SYCL）は GPU の layer doorbell を host が待つ時間を決める別の経路で、このフック自体の値判定には使われない。

## 実行時の詳細

値は CUDA/HIP の `g_test_stall`（`engine/src/core/verify.cpp:654-657`）または SYCL の `g_test_stall`（`engine/sycl/src/core/verify.cpp:399-402`）へプロセス内で一度だけ保存される。各 window や request ごとの再読み込みではなく、起動後の環境変更は反映されない。

対象窓では CUDA/HIP は `test_stall` により early/all-resident flag の発行経路を避け、全 layer step のうち最後だけ `*flag = want` を省略する（`engine/src/core/verify.cpp:3865-3868,3979-3993,4118-4119`）。SYCL も同様に最後の step の flag を省略する（`engine/sycl/src/core/verify.cpp:2622-2637,2744-2745`）。そのため、その window の GPU 処理は flag wait で完了できず、CUDA/HIP は stream 同期、SYCL は queue 同期で待つ（`engine/src/core/verify.cpp:4150-4166`、`engine/sycl/src/core/verify.cpp:2749-2755`）。

通常の serve engine では、request の進捗が既定 60 秒止まると watchdog が stall report を出し、GPU wait を解放してから engine を abort する。`STRATA_WATCHDOG_S=0` なら watchdog thread は開始されない（CUDA/HIP: `engine/src/program/generate.cpp:16268-16277,16313-16321`、SYCL: `engine/sycl/src/program/generate.cpp:9548-9571`）。watchdog が無効な場合、verify の window 同期自体に Strata 側の期限はなく、待ちが続く経路が残る。個別 verifier の待ち時間や GPU 完了をこの環境変数が延長するわけではない。

## ログと測定値

この変数を読んだ時点ではログを出さない。stall が watchdog に検知されると、stderr に `strata serve: no progress for ... s during a request (...) - stopping the engine so the server starts it again (issue #29)` が出て、stall report と GPU wait 解放の報告の後に `std::abort()` する。既定期限は60秒で、`STRATA_WATCHDOG_S` が有効期限を変える（`engine/src/program/generate.cpp:16268-16275,16313-16321`、SYCL: `engine/sycl/src/program/generate.cpp:9548-9569`）。

## 根拠

- 候補名の全実装参照と値の読み取り: `engine/src/core/verify.cpp:652-657`、`engine/sycl/src/core/verify.cpp:397-402`。
- `terminal/data/settings-register.json:49402-49412` にも名前が登録され、上記 CUDA/HIP 読み取り箇所を列挙している。値を環境から読む挙動の根拠は C++ 実装。
- 対象 window の判定と flag 抑止: `engine/src/core/verify.cpp:3865-3868,3979-3993,4118-4119`、`engine/sycl/src/core/verify.cpp:2480,2620-2637,2744-2745`。
- window 同期と watchdog の終了経路: `engine/src/core/verify.cpp:4150-4166`、`engine/sycl/src/core/verify.cpp:2749-2755`、`engine/src/program/generate.cpp:16261-16277,16313-16321`、`engine/sycl/src/program/generate.cpp:9543-9571`。
- engine へのソース組み込み: `engine/cmake/strata_gpu_engine.cmake:310-316`、`engine/sycl/CMakeLists.txt:290-299`。
