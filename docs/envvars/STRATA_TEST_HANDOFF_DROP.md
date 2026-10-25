# `STRATA_TEST_HANDOFF_DROP`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の overlapped layer split で、書き込み側 stage が次 stage に hand-off 完了を知らせる flag を、指定した window で意図的に立てないテスト用フックです。データの publish を失った状態を作り、読み取り側の bounded wait と window のエラー処理を確認する用途です。通常利用者向けの性能設定ではありません。

## 値と判定

プロセス起動時の静的初期化で `getenv()` を一度呼び、値を `std::atoll()` で `int64_t` に変換します。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | `0`。フック無効 |
| 空文字、数値として読めない文字列 | `atoll` の変換結果は `0`。フック無効 |
| 整数の先頭部分が正数（例: `2`, `2junk`, `+2`） | その整数を対象 window 番号として使う |
| `0`、負数、または変換結果が `0` 以下 | フック無効 |

`atoll` による変換なので文字列全体の厳密な数値検証はせず、先頭の空白や符号を許し、数値部分の後ろに続く文字は判定しません。大文字小文字の比較はありません。値は起動時に読み取った後キャッシュされ、プロセス実行中の環境変更は反映されません。

## 有効になる条件

値が正数でも、overlapped layer split の書き込み側 verifier に outgoing hand-off flag があり、`batch_rec_` が無効な経路でのみ使われます。通常の serial split や単一 GPU の経路では、この値に応じた flag 抑止は起きません。

指定した番号は書き込み側 verifier の 1-based window 番号です。該当 window 以外では test word を 0 に戻し、通常どおり flag を公開します。リポジトリの `MULTI_GPU.md` は「first stage」の N-th window と説明しています。

## 実行時の詳細

window の入力 staging 時に、`windows + 1 == N` の場合だけ mapped test word を 1 にします。書き込み側は hand-off payload を GPU kernel で引き続きコピーしますが、指定 window では最後の publish flag を書かずに戻ります。これは payload の破損ではなく、通知 flag の欠落を模擬します。

読み取り側 graph は hand-off flag が立つまで GPU 上で待ちます。`STRATA_SPLIT_WAIT_MS` の期限までに flag が来なければ、GPU wait は error word を立てて戻り、window の graph 完了後にホスト側が window を失敗として返します。エラー文は待ち先 layer と timeout を示し、`STRATA_SPLIT_OVERLAP=0` で serial 順序を使うよう案内します。失敗 window の古い hand-off データは使用されません。期限は `STRATA_SPLIT_WAIT_MS` で決まり、既定値は 30000 ms、0 は GPU wait の期限なしです。通常は別途ホスト側の stalled-window watchdog が先に GPU wait を解放する場合があります。

## 根拠

- `src/core/verify.cpp:457-462` — `getenv` / `atoll` による起動時読み取りと値のキャッシュ。
- `include/strata/core/verify.hpp:473-482` — incoming/outgoing flag、error word、test word の役割。
- `src/core/verify.cpp:805-811` — overlapped split 用 mapped test word の確保。
- `src/core/verify.cpp:1077-1083,2090-2099` — 読み取り側の hand-off wait と書き込み側の publish 経路。
- `src/core/verify.cpp:2523-2531` — window ごとの test word 設定。`N` が正のとき N-th window だけを指定。
- `src/kernels/cuda/verify_kernels.cu:1183-1198,1200-1218` — bounded wait と、payload コピー後に flag を抑止する処理。
- `src/core/verify.cpp:2605-2611,2890-2910` — timeout を検出し、window を失敗扱いにする処理。
- `docs/MULTI_GPU.md:239-244` — timeout とテストフックの説明。GPU が期限切れで戻ること、server が engine を再起動する旨も記載。
