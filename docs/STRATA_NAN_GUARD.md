# `STRATA_NAN_GUARD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の verify window の head logits に NaN や infinity が含まれるかを GPU で検査します（#879、既定 ON）。flag された window はその token を一切出力せず、request を `DONE ... nonfinite` で終え、cached state を drop して次の request が prompt を token 0 から読み直します。poison が conversation の K/V と recurrent state に残ると後続 turn がずっと汚染される（#606 で token 0 の繰り返しを観測）ことへの guard です。

判定結果は `nan_guard_on()` 内の `static const bool` に保存され、graph が一度 capture されるので最初に呼ばれたとき一度だけ read されます。

## 値と判定

`getenv()` が未設定なら ON。設定されている場合は `std::atoi` の結果が 0 でなければ ON、0 なら OFF。

| 入力 | `atoi` | guard |
|---|---|---|
| 未設定 | — | ON（既定） |
| `1`, `2`, `1anything` | 非 0 | ON |
| `0` | 0 | OFF |
| 空文字 | 0 | OFF |
| 非数字（例 `abc`, `true`, `false`） | 0 | OFF |

文字列全体を parse せず、`atoi` が 0 を返す値（`0`、空文字、先頭が数字でない文字列）は OFF になります。先頭文字比較ではなく数値 parse です。

根拠: `src/core/verify.cpp:3107-3113`、注釈 `3106`。

## 有効になる条件

- `--serve` の window だけで action します。one-shot の command line（`strata` を `--serve` なしで）と Intel（SYCL）port の `sycl/` は check しません（`docs/DETAILS.md:765`）。SYCL 実装に `nan_guard_on` は存在しません。
- layer split では head を持つ stage（last stage）が検査します。head を持たない stage は何も check しません（`src/core/verify.cpp:3139` の `!last_stage()`）。
- OFF のとき kernel が記録されず、`nonfinite_row()` は常に -1（`include/strata/core/verify.hpp:104`）。
- debug 用の `STRATA_NAN_INJECT=<n>[,<n>...]` は、guard が検査する n 番目の window（process 全体で 1 から数える）の row 0 を non-finite として報告します。guard OFF では inject も効きません（`note_nonfinite` が `nan_guard_on()` で early return）。

## 実行時の詳細

- kernel 記録: window の greedy pick のそばで `logits_nonfinite_rows(head_logits_, T, n_vocab_, m_nf_, cs)` を graph に入れます（`src/core/verify.cpp:1795`）。flag は mapped memory（`kVerifyMaxT * kNonfiniteBlocks` の uint32）に書かれ、window がすでに行う sync の後に host が読みます（追加 sync なし）。
- flag 読み取り: `note_nonfinite` が row mask を作り、最初の non-finite row を `nf_row_`、その position を `nf_pos_` に入れます（`src/core/verify.cpp:3135-3155`）。
- serve での action: `nonfinite_hit` が stderr に `strata serve: non-finite logits (#879) in a <what> window at position <p> (row <r>): its tokens are not emitted, the request ends (DONE nonfinite) and the next request reads its prompt from token 0` を出します（`src/program/generate.cpp:7991-8001`）。batch slot は `BDONE <slot> <n> nonfinite`（`9445,9603`）。server は何も送っていない request を 1 回 transparently retry し、reply が始まっていたら `"length"` で終えます（`docs/DETAILS.md:756-758`）。

## 測定値

`docs/DETAILS.md:759-764` の記載: kernel は flag だけ書き host は読むだけなので、NaN を含まない answer は `STRATA_NAN_GUARD=0`（kernel を記録しない）と同一。RTX 3080、RVN IQ3_S config、fixed expert sets、16K-token system prompt の 8-turn chat replay で、guard on/off が 3 pairs で byte-identical answers（1 pair は `STRATA_ROUTE_TAIL_SKIP=0`、1 pair は `STRATA_SH_STREAM=0`）。もう 1 つの guard-off run は最初の answer から他と異なり、2 つ目の guard-off run は guard-on と一致したので run 間の差で guard の差ではない。cost: window あたり平均 4.8 us（最大 7.8 us）の GPU time、decode time の 0.009%（Nsight Systems、424 windows）。これは記載された測定環境での値です。

## 根拠

- parse と既定: `src/core/verify.cpp:3107-3113`、注釈 `3106`。
- kernel 記録: `src/core/verify.cpp:1795`。flag 読み取り: `3135-3155`（`last_stage` 条件 `3139`）。
- serve での action とログ文言: `src/program/generate.cpp:7991-8001`、`9445`、`9603`。
- 設計・境界（--serve 限定、one-shot と SYCL は check しない、inject）: `include/strata/core/verify.hpp:100-107`、`docs/DETAILS.md:746-765`。
