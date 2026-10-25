# `STRATA_BATCH_ATTN_ROWS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソースです。

## 役割

バッチ検証 window の QSA 層で、各シーケンスの行ごとに実行していた block score、top-k、decode attention を複数行まとめて処理する opt-in です。各行はそれぞれ自分の indexer key と K/V pool を使い、出力先も行ごとに分かれます。環境変数を有効にしても、通常の単一シーケンス経路や QSA を持たない層には適用されません。

## 値と判定

値は `std::atoi(v) != 0` で判定され、文字列全体の厳密比較ではありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、`0`、`+0`、`-0`、数値で始まらない文字列（例: `true`） | 無効（`atoi` が 0 を返す） |
| 0 以外の整数として読める値（例: `1`, `-1`, `+2`） | 有効 |
| 数字の後ろに文字が続く値（例: `1extra`） | 数字部分が 0 以外なら有効。後続部分は `atoi` の判定に使われない |
| 数字の前に空白や符号がある値（例: ` 1`, `+1`） | `atoi` が 0 以外を返す場合は有効 |

ソースでは無効値をエラーにせず、通常の処理経路を使います。変数の値は `record_window()` 内の関数ローカル `static const bool` に保存されるため、初回評価後のプロセス環境の変更は反映されません。評価箇所は同関数の QSA 層ループ内です（`src/core/verify.cpp:1684-1687`）。

## 有効になる条件

- `record_window()` がバッチ window を記録していること（`batch_rec_` が true）。バッチ graph の capture 中にこのフラグが設定されます（`src/core/verify.cpp:3258-3271`）。
- 処理中の層が QSA 層であり、対象 window の行数 `te - tb` が `kAttnRowsMax` 以下（現在 8）であること（`src/core/verify.cpp:1688`, `include/strata/kernels/qsa_decode_attn.hpp:34-38`）。
- 対象行の QSA state のいずれも KV streaming mode (`kv_mode == 1`) でないこと。1行でも該当すれば、この分岐を使いません（`src/core/verify.cpp:1688-1690`）。

条件を満たさない場合は別のバッチ slot 経路、または各行を個別に処理する経路へ進みます（`src/core/verify.cpp:1708-1753`）。環境変数が有効でも、1回の処理行数が8を超える範囲はこの rows 経路の対象外です。

## 実行時の詳細

有効条件を満たすと、各行について `QsaScoreRows` と `QsaAttnPoolsRows` を組み立て、`qsa_block_scores_rows()`、`qsa_block_topk()`、`qsa_decode_attn_batch_rows()` を呼び出します（`src/core/verify.cpp:1691-1707`）。score と attention は各行の別々の indexer key / K/V pool を参照します。top-k は行ごとの score・step buffer をまとめて渡します。

このフラグ自体の読み取りや有効化を知らせるログはありません。kernel launch が失敗した場合には通常の kernel error が stderr に出て終了します。attention の row kernel は `STRATA_ATTN_LANECELL=1`、ビルド時の pre-sm_75 経路、または HIP gfx906 では内部で各行の `qsa_decode_attn_batch()` に戻します。そのため、外側の rows 分岐が選ばれても、decode attention まで常に単一 launch になるとは限りません（`src/kernels/cuda/qsa_decode_attn.cu:1136-1151`）。

既存の `docs/BATCHING.md` は `=1` の opt-in、最大8行、KV streaming で per-row launch を保つ点を説明しています（`docs/BATCHING.md:476-489`）。実装の判定は `=1` との完全一致ではなく `atoi(v) != 0` です。同資料は温度0で4 concurrent prompts、`--batch 4` と `--batch 8` のとき切替前後で同じ bytes だったと記載しています。また RTX PRO 6000 Blackwell (96 GB)、IQ3_S、int8 KV、262144 context、MTP/spec 4、HTTP server などの条件で、両スイッチを有効にした場合の測定表を掲載しています。これは資料に記載された条件での結果であり、この調査で再測定した値ではありません（`docs/BATCHING.md:488-505`）。

## 根拠

- `src/core/verify.cpp:1680-1707` — 環境変数の読み取り、適用条件、rows 用の各 kernel 呼び出し。
- `src/core/verify.cpp:1708-1753` — 条件不成立時の batched-slot / per-row fallback。
- `src/core/verify.cpp:3258-3271` — バッチ window の graph capture と `batch_rec_` の設定。
- `include/strata/kernels/qsa_decode_attn.hpp:34-38,78-81` — rows 構造体の最大行数と attention API。
- `include/strata/kernels/qsa_select.hpp:26-36,62-69` — score rows と top-k API。
- `src/kernels/cuda/qsa_select.cu:1810-1821` — 複数行の block score kernel 呼び出し。
- `src/kernels/cuda/qsa_decode_attn.cu:1117-1166` — attention rows の検査、variant 条件での per-row fallback、kernel launch。
- `docs/BATCHING.md:476-505` — 用途説明と記載済みの測定条件。
