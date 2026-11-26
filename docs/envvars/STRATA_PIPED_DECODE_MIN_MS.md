# `STRATA_PIPED_DECODE_MIN_MS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--batch-groups` で GPU stage 間に pipelined slot groups を作り、さらに `STRATA_PIPED_READ_PIECE` で prompt read を複数 piece に分けたとき、piece 間に slot groups を decode させる時間の下限（ミリ秒）を指定する。通常の decode 予算 `STRATA_BATCH_DECODE_SHARE × piece の所要時間` が短い場合にも、この下限まで decode を続ける。生成 token や slot の選択規則を直接変更する値ではなく、prompt read と decode の時間配分を変える。読み取りと適用は `engine/src/program/generate.cpp` の request prompt-read 処理にある。

## 値と判定

`std::getenv` の結果を `std::atof` で変換し、`std::max(0.0, 値)` を適用する。未設定は `0`。設定済みの空文字、数値に変換できない文字列、負数も変換後または clamp 後に `0` になる。`atof` のため文字列全体の妥当性検査はせず、数値部分の後ろに文字があっても数値部分を採用する（例: `50ms` は `50`、`0anything` と `no` は `0`）。先頭の空白は数値変換で読み飛ばされる。正数はそのままミリ秒として使われる（`1` は 1 ms）。`NaN` はこの `std::max(0.0, ...)` で `0` になり、`inf` は正の無限大として扱われるため、batch decode が続く間は予算時間だけで decode loop を終えない値になる。大文字小文字を区別する比較や整数丸めは行わない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| `generate.cpp` の piped prompt-read 経路 | `0 ms` | `1` → `1 ms`, `50`, `50.5`, `50ms` → `50`, `.5` → `0.5 ms`, `inf` → 無限大 | 空文字、`true`, `false`, `no`, `0`, `0anything`, `-1`, `NaN` → `0 ms` |

値の読み取りは関数内 `static const` 初期化で一度だけ行われ、最初にその宣言へ到達した時点の値がプロセス内で cache される。以後の環境変更は反映されない。`STRATA_PIPED_DECODE_MAX_MS` は share 由来の予算に上限を付けるが、通常の piece 間予算ではこの下限を最後に適用するため、min が max より大きければ min が max を超える（`generate.cpp:21288-21295`, `batch_read.hpp:72-75`）。

## 有効になる条件

- `--batch` が正数で、`--batch-groups` の解決結果が 1 より大きく、layer split の stage が存在して piped 経路 (`piped`) が成立すること（`generate.cpp:17529-17533`）。
- Prompt-read piece 化も有効であること。これは `STRATA_PIPED_READ_PIECE` が正数 (`pr_piece > 0`) の場合だけで、未設定や 0 以下では piece 全体を一度に読むため、この変数は piece 間 decode 予算に使われない（`generate.cpp:21284-21300`, `21342-21345`）。
- piece の後に batch decode が継続中である場合に限り、計算した予算時間まで `pump(true)` を繰り返す。`batch_on()` がすでに false なら、下限が正でも追加 decode 時間は保証されない（`generate.cpp:21303-21320`, `21373-21387`）。
- CLI 引数や別設定による値の上書きはない。`STRATA_BATCH_DECODE_SHARE` が share 由来の時間を、`STRATA_PIPED_DECODE_MAX_MS` がその時間の上限を決める。通常の piece 間では min が最後に適用される。連続する prompt read の先行 decode でも同じ budget helper を使うが、プロセス内で前回の piece 実績がない場合の初回 lead-in は別式で決まる（次節）。

## 実行時の詳細

piece 後に slot が動作中なら、Strata は `piped_decode_budget_ms(piece_ms, decode_share, pr_cap, pr_floor)` を呼ぶ。計算は `max(0, share) × max(0, piece_ms)` を基礎に、正の max があれば cap し、その後 `max(0, floor)` を適用する。したがってこの環境変数は負の share や小さい share で生じる短い予算を引き上げる。算出予算を使って `pump(true)` を少なくとも一度実行し、batch decode が続き、経過時間が予算未満の間は繰り返した後、pipeline を drain してから次の prompt piece に進む（`batch_read.hpp:69-75`, `generate.cpp:21302-21320`, `21379-21387`）。

連続 prompt read の lead-in では、過去の piece 実績があれば同じ helper で予算を出す。過去実績がない場合は、`STRATA_PIPED_DECODE_MAX_MS` が正ならその値を使い、そうでなければ `max(pr_floor, 200 ms)` を使う。この初回 lead-in 式では max が正の場合に min floor を再適用しない（`generate.cpp:21322-21340`）。Read piece を有効にした prompt が終わると、その終了時刻を次回 lead-in 判定用に保存する（`generate.cpp:21406-21407`）。

値は子プロセスへ転送されず、このコード内で読み取られて使われる。対象コードにこの変数固有の警告や parse error はない。pipeline decode / drain に失敗すると `a pipelined batch window failed` をエラーにし、server 経路で stderr に `strata serve: a pipelined batch window failed`、stdout に `ERR a pipelined batch window failed` を出して失敗終了する（`generate.cpp:21307-21315`, `21593-21604`）。

## ログと測定値

下限値そのものを表示するログはない。piece 間に slot decode が行われた場合は stderr に `strata batch: piped read N tokens in X ms (to Q of T), then the slots decoded R rows in Y ms` が出る。slot decode が動作していない場合は decode 部分を省いた `strata batch: piped read N tokens in X ms (to Q of T)` が出る（`generate.cpp:21373-21387`）。

## 根拠

- `engine/src/program/generate.cpp:17529-17533` — piped 経路の成立条件。
- `engine/src/program/generate.cpp:21279-21300` — 環境変数の static 読み取り、piece 有効条件。
- `engine/include/strata/program/batch_read.hpp:69-75` — decode budget の計算式。
- `engine/src/program/generate.cpp:21302-21340` — decode pump / drain と連続 read の lead-in。
- `engine/src/program/generate.cpp:21373-21387` — piece 間の適用とログ。
- `engine/src/program/generate.cpp:21406-21407`, `21593-21604` — lead-in 用状態と失敗時の観測結果。
