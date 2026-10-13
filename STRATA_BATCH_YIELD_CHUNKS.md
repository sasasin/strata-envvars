# `STRATA_BATCH_YIELD_CHUNKS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--batch` のプロンプト読み込みで、layer split があり、かつ他の slot が decode 中でない場合に、一度の `sp.run()` で読むチャンク数を指定します。小さい値ほど読み込みを細かく区切り、区切りごとに `BYIELD` を調べるため、待機中の短い request に処理を譲る機会が増えます。既定値は 8 チャンクです。

この値が使われるのは `read_part()` の経路です。window 単位で読む `read_windows()` の経路には使われません。値は関数内の `static const int64_t` に保存され、プロセス内で初めて `read_part()` が実行されたときに一度だけ読み取られます。その後の環境変更は反映されません。

## 値と判定

読み取りは `std::getenv()` と `std::atoi()` によります。文字列全体の妥当性検査はなく、変換結果に `std::max(0, ...)` を適用します。

| 環境変数の状態・値 | `chunks_per_piece` |
|---|---:|
| 未設定 | 8 |
| 空文字 | 0 |
| 整数に変換できない文字列（例: `abc`） | 0 |
| 0 または負数 | 0 |
| 正数 | その値 |

`atoi` は先頭の空白と符号を許し、数値の後ろにある非数字部分を無視します。したがって `  +4junk` は 4、`4.5` は 4 として扱われます。負数は parse 後に 0 に clamp されます。正数に対する明示的な上限 clamp はありません。

## 有効になる条件

`batch_read_piece()` は次の順で分割幅を決めます。

- `--batch` が無効、または pipelined groups (`--batch-groups` による `piped`) の場合は 0 を返し、対象区間全体を一度の `sp.run()` で読みます。
- layer split がない場合、または batch slot が decode 中の場合は、環境変数にかかわらず 1 prompt chunk ずつ読みます。
- `--batch` が有効で、layer split があり、pipelined groups ではなく、batch slot が decode 中でない場合、正数ならその数の chunk を一度に読みます。0 なら区間全体を一度に読みます。

ここで chunk 幅 `C` は `max(sp.chunk(), 1)` です。正数の場合の piece 幅は `C * STRATA_BATCH_YIELD_CHUNKS` tokens です。実際の read 区間末尾では残り token 数に合わせて短くなります。

## 実行時の詳細

各 piece は `sp.run()` で処理されます。piece の終わり（残りがあれば）で入力キューを確認し、`BSTOP` を反映し、`BYIELD` があれば slot に読み込み済み prefix を保存して request を yield できるか判定します。yield できた場合、stderr に `strata batch: the prompt read gives way at ...` を出し、処理を中断します。yield 条件を満たさない場合は `strata batch: BYIELD ... not taken at ...` を出して次の piece に進みます。

したがって、この変数は prompt の chunk 自体や model 計算の結果を変えず、layer split の batch prompt read における `sp.run()` のまとまりと `BYIELD` を確認する頻度を変えます。値 0 は区間を一度に読むため、その read 区間の途中では `BYIELD` を確認しません。層分割時に slot が decode 中なら常に 1 chunk ごとの読み込みとなるので、この変数による幅の変更はありません。

## 根拠

- `src/program/generate.cpp:10842-10855`: 環境変数の読み取り、既定値 8、負値 clamp、chunk 幅の取得、piece ごとの `sp.run()`。
- `src/program/generate.cpp:10857-10919`: piece 境界での `BSTOP` / `BYIELD` 処理、yield の結果とログ、slot decode の処理。
- `src/program/generate.cpp:9236`: `batch_on()` は active slot があるかを返す。
- `src/program/generate.cpp:9552-9558`: batch group が複数の pipelined group となる条件。
- `include/strata/program/batch_read.hpp:13-28`: `batch_read_piece()` の条件と戻り値。
- `src/program/generate.cpp:11038-11054`: `read_windows()` と `read_part()` の選択。
- `docs/BATCHING.md:126-135`: batch admission の prompt chunk 処理と BYIELD の概要。文書は `STRATA_BATCH_YIELD_CHUNKS` の値や既定値を説明していない。
