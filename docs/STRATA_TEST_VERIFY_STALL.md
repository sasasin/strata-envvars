# `STRATA_TEST_VERIFY_STALL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Verifier の指定 window で、最後の layer を処理した後に GPU へ送る完了フラグを意図的に省きます。GPU の verify graph を未完了のまま待たせ、停止検出後に GPU wait を解放してエンジンを終了する #267 の経路を確認するためのテストフックです。通常利用者向けの性能設定ではありません。

CUDA/HIP 系の `src/core/verify.cpp` と SYCL 版 `sycl/src/core/verify.cpp` に同じ環境変数の読み取りがあります。どちらも verifier の標準 `Verifier::run()` 内で使われます。`run()` が持つ window カウンターを基準にし、値 `N` はその verifier の N 番目の window（1始まり）を指します。

## 値と判定

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | 無効（内部値 0） |
| 空文字、数値に変換できない文字列 | 無効（`std::atoll` が 0 を返す） |
| 正の整数に変換される値 `N` | `windows + 1 == N` となる window で発動 |
| `0` または負数に変換される値 | 無効（発動条件が `g_test_stall > 0`） |

値は `std::atoll` で10進数として変換され、文字列全体の厳密な検証はありません。先頭の空白や符号を受け付け、数字の後ろに文字が続いても数字部分を変換します（例: `3junk` は 3）。数字で始まらない文字列は 0 となります。値域外の変換結果は C ライブラリの `atoll` の範囲外規則に従い、Strata 側で別途検査・clamp していません。

この値はプロセス内の namespace-scope `const int64_t` 初期化時に一度読みます。起動後の環境変更は反映されません。Strata は値を子プロセスへ設定・転送しません。

根拠: `src/core/verify.cpp:373-378`、`sycl/src/core/verify.cpp:314-319`、通常 run のカウンター比較と更新は `src/core/verify.cpp:2182,2303-2307` および `sycl/src/core/verify.cpp:2187,2397-2413`。

## 有効になる条件

- 対象バックエンドの verifier 実装がビルドされ、その verifier の標準 `Verifier::run()` が対象 window を処理すること。
- window カウンターが指定値 `N` の直前であること。指定 window を過ぎた場合、後続 window では一致せず発動しません。
- SYCL の stepped all-resident 経路では、指定 window に限って `stepped_ar` を無効化し、通常の layer flag 経路へ戻す処理があります。これにより同じフックを適用できます（`sycl/src/core/verify.cpp:2041-2055`）。

実装上の一致箇所は標準 `Verifier::run()` のみです。バッチや pipelined window の処理箇所にはこの変数の判定がなく、それらの各 window に同じ番号指定で必ず作用するとはコードから言えません。SYCL の `STRATA_VERIFY_NO_HOST` など、別経路で host flag を省く設定との組み合わせも、指定通りに最後の flag wait を発生させる保証は確認できません。

## 実行時の詳細

通常の window 処理では各 layer の CPU 側処理後に GPU 用 `flag` を進めます。指定 window の最後の layer では `*flag = want` を実行しないため、GPU graph はそのフラグを待ち続けます（CUDA/HIP 系: `src/core/verify.cpp:2182-2183,2274-2288`、SYCL: `sycl/src/core/verify.cpp:2187-2190,2298-2308`）。このため通常の token 生成を継続する設定ではなく、意図的に停止を起こします。

標準 run の layer 到達待ちにある 20 秒 timeout は、この最終フラグ欠落ではなく GPU が layer の doorbell に到達しない状況を対象にしています。最終 flag を欠いた場合、ホストは window 完了の同期（CUDA の `cudaStreamSynchronize`、SYCL の queue wait）に入ります。停止回復側が登録する `release_live_verifiers()` は各 verifier の GPU wait フラグを `UINT32_MAX` に上げ、verifier ごとに stream/queue の完了を最大5秒待ちます。CUDA/HIP 系の `release_gpu_waits()` は `src/core/verify.cpp:381-404`、SYCL 版は `sycl/src/core/verify.cpp:322-349`、登録はそれぞれ `src/core/verify.cpp:540-549` と `sycl/src/core/verify.cpp:468-476` です。回復の呼び出し元は停止終了経路で、`include/strata/core/progress.hpp:39-44` に登録 callback の契約があります。

停止が検出された後のエラー文は、layer doorbell timeout 経路では `verify: timed out at layer ...`、既に window 終了同期へ進んだ経路では周辺の停止終了処理に依存します。`STRATA_VERIFY_TRACE` が有効な timeout 経路では `diag(stderr)` と trace dump も出ます（`src/core/verify.cpp:2218-2229`、`sycl/src/core/verify.cpp:2238-2249`）。このテストフック固有の開始ログはありません。

## 根拠

- `src/core/verify.cpp:373-378`: 環境値の読み取りと未設定時の既定値。
- `src/core/verify.cpp:2136-2142,2182-2183,2274-2288`: CUDA/HIP 系標準 `Verifier::run()` での対象 window 判定、最終 flag の省略、window 同期。
- `sycl/src/core/verify.cpp:1996-2005,2041-2055,2187-2190,2298-2308`: SYCL 標準 run と stepped all-resident の扱い。
- `src/core/verify.cpp:343-353,381-404`、`sycl/src/core/verify.cpp:284-295,322-349`: live verifier の登録解除補助、GPU wait release と最大5秒の drain。
- `include/strata/core/progress.hpp:39-44`: 終了前に GPU wait release callback を実行する共通インターフェース。
- `docs/DETAILS.md` と他の Markdown 資料にこの環境変数の説明は見つかりませんでした。上記は現 HEAD の実装から確認した挙動です。
