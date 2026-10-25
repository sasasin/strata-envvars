# `STRATA_TEST_BELL_SLEEP_US`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

パイプライン同時 prompt read 中に doorbell を処理する専用スレッドについて、window がなくなったときの待ち方をテスト用に変更します。通常は次の window launch または読み込み終了を条件変数で待ちます。この変数に正数を設定すると、その待ちを指定マイクロ秒の sleep とポーリングに置き換えます。ソースコメントは「待ち方の A/B テスト」としています。

## 値と判定

環境変数は `std::atoi` で `int` に変換され、`std::max(0, ...)` で負値を 0 にします。値全体の妥当性検査はありません。

| 値 | 結果 |
|---|---|
| 未設定 | 0。通常の条件変数待ちを使う |
| 空文字、数値に変換できない文字列 | `atoi` の結果 0。通常の条件変数待ちを使う |
| 0 または負数 | 0 に clamp。通常の条件変数待ちを使う |
| 正数 | 指定されたマイクロ秒だけ sleep し、ループの先頭に戻る |
| 数字の後ろに文字が続く値 | `atoi` が読む先頭の整数部分で判定する。例: `50us` は 50 |

`atoi` のため、先頭空白や符号を含む整数表記も変換対象です。範囲外の値について、実装に独自の検査や fallback はありません。

## 有効になる条件

この値が使われるのは、`read_part` の中で `piped && pr_conc && req_imgs.empty()` が成立し、prompt read 中の doorbell 専用スレッドが作られた場合だけです。`pr_conc` は `STRATA_PIPED_CONCURRENT` が設定され、`atoi` の結果が 0 以外であることに加え、次の無効化条件がない場合に有効です。

- `STRATA_PREFILL_HELP` または `STRATA_SPLIT_MTP_BATCH` が有効。
- `STRATA_FS_SLOTS` が有効、または `--pcie-mode dma` を指定。
- helper cache を使う（`--expert-cache-device1..3`。`--remote-expert-opt` は helper cache がある場合）。
- GGUF source が blob を stage する（in-place、unbuffered、`STRATA_IO_PREFETCH`）、または GGUF/arena 以外の expert source を使う。

これらは `atoi(value) != 0` で判定されます。画像付き request では `req_imgs.empty()` を満たさず、この doorbell thread 経路を通りません。変数単独で通常の batch read や単独 decode の待ち方は変えません。

## 実行時の詳細

専用スレッドは各 stage verifier を調べ、busy な verifier があれば `batch_serve()` を呼びます。すべて idle のときに本変数を初めて読みます。読み取り結果は関数内の `static const int` に保存されるため、そのプロセスでこの初回評価が済んだ後に環境を書き換えても反映されません。

保存値が正数なら `sleep_for(microseconds(value))` の後にループを続けます。0 なら `bell_cv.wait_for(..., 2ms, ...)` で次の launch またはスレッド終了を待ちます。前者は条件変数による通知を待たずに再確認するため、launch の検知タイミングと待機中のスレッド動作を変えます。環境変数専用のログ出力はありません。

`docs/BATCHING.md` は、この値を 50 にした同じ測定ビルドで、prompt read 中の stream throughput が 85–92 tok/s から 64–67 tok/s になったと記録しています。これは同ドキュメントの 2x RTX 5090 等の測定条件における報告値であり、他環境の性能を示すものではありません。

## 根拠

- `src/program/generate.cpp:12855-12892` — `STRATA_PIPED_CONCURRENT` の判定と無効化条件。
- `include/strata/program/batch_read.hpp:30-54` — 同時 read を無効にする設定と CLI 条件。
- `src/program/generate.cpp:12893-12902` — 同時 read と画像なしの条件、および準備処理。
- `src/program/generate.cpp:12977-13013` — doorbell スレッド、busy stage の処理、環境変数の static 読み取り、sleep と通常の条件変数待ち。
- `docs/BATCHING.md:197-225` — 同時 read の概要、doorbell スレッドと通常の待機方式。
- `docs/BATCHING.md:227-247` — 測定条件と `STRATA_TEST_BELL_SLEEP_US=50` の結果。
