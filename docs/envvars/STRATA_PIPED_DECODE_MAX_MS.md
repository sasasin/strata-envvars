# `STRATA_PIPED_DECODE_MAX_MS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--batch-groups` で GPU の layer split 上に作られた slot group が、分割された prompt read の間に pipeline を decode する時間 budget の上限をミリ秒単位で指定する。対象になるのは `STRATA_PIPED_READ_PIECE` によって read が piece に分かれた経路である。未設定または 0 以下ならこの上限を設けない。上限を適用した後に `STRATA_PIPED_DECODE_MIN_MS` の下限が適用されるため、下限が上限より大きい場合、最終 budget はこの変数の値を超える。実装は `engine/src/program/generate.cpp` の `read_part` と `engine/include/strata/program/batch_read.hpp` の `piped_decode_budget_ms` にある（`generate.cpp:21279-21300,21379-21387`; `batch_read.hpp:69-75`）。

## 値と判定

`read_part` 内の関数ローカル `static` が `std::getenv` で読み、設定されていれば `std::atof` で変換して `std::max(0.0, 値)` を取る。文字列全体の妥当性や末尾は検査しない。したがって空文字や数値に変換できない先頭（`true` など）は 0、`12ms` は 12、`0anything` は 0 として扱う。先頭の空白や符号、小数・指数表記は `atof` の数値変換に従う。負数は 0 に丸められる。エラーや fallback のログはない（`engine/src/program/generate.cpp:21288-21291`）。

| 条件 | unset | 変換後の例 | 結果 |
| --- | --- | --- | --- |
| `read_part` の評価時 | 上限値 0.0 | 空文字、`true`、`0`、`0anything`、`-1` | 上限なし |
| `read_part` の評価時 | 上限値 0.0 | `12`、`12ms` | 12 ms の上限 |

`--batch` や `--batch-groups` にこの値を上書きする CLI 引数はありません。decode share は別変数 `STRATA_BATCH_DECODE_SHARE`（未設定時 0.5）、下限は `STRATA_PIPED_DECODE_MIN_MS`（未設定時 0）から読みます。piece 間の budget は share × piece 実測時間を 0 以上にし、この変数が正ならその値で上限を適用し、その後に 0 以上の下限を適用します（`generate.cpp:20742-20745,21292-21295,21379-21383`; `batch_read.hpp:72-75`）。

## 有効になる条件

- `--batch` が正で、解決後の `--batch-groups` が 1 より大きく、layer split の stage が少なくとも 1 つあり、slot groups が pipelined 経路を使うこと（`engine/src/program/generate.cpp:17529-17532`）。`--batch` と `--batch-groups` の引数は `atoi` で読み取られ、groups が layer split を使わない、または batch を割り切らない場合は警告後に 1 group に戻される（`generate.cpp:4041-4048,7995-7998`）。
- `STRATA_PIPED_READ_PIECE` が正になり、prompt read が複数 piece に分割されること。未設定または整数変換後 0 以下では `pr_on` が false になり、この上限を使う piped-piece 処理には入らない（`generate.cpp:21284-21300,21343-21348`; piece のチャンク丸めは `batch_read.hpp:63-67`）。
- piece の後に slot が active であること。active slot がなければ piped read のログを出して次の piece に進み、decode budget を消費しない（`generate.cpp:16856,21373-21378`）。
- 読み取り・budget 適用箇所には OS 固有の条件や、この変数専用の build macro 分岐はない。実際に有効かどうかは上記の pipelined 経路条件による。

## 実行時の詳細

値はプロセス起動時ではなく、pipelined prompt の `read_part` が該当する初回実行に達した時点で評価され、関数ローカル `static` に保持される。以後の read で環境を変更しても再読込されない（`engine/src/program/generate.cpp:21288-21291`）。

piece 間では、前 piece の処理時間と `STRATA_BATCH_DECODE_SHARE` から budget を算出し、本変数の正値を上限としてから `STRATA_PIPED_DECODE_MIN_MS` の下限を適用する。slot が active なら `piped_decode` は pipeline の window を少なくとも一度 `pump(true)` し、budget に達した後 `pipe_drain` してから次の read piece に進む（`generate.cpp:21303-21320,21379-21387`; `batch_read.hpp:72-75`）。この変数が変えるのは slot groups に割り当てる decode 時間であり、prompt piece の token 数や token 選択そのものを変更する処理はここにはない。

連続する piecewise read の先頭でも、直前の piecewise read 終了から 1 秒以内（加えて計算した budget の時間内）なら lead-in decode を行う。前 read の piece 時間が得られていれば通常の cap/floor 計算を使い、そうでなければ正の cap を lead-in budget にし、cap が 0 の場合は `max(floor, 200 ms)` を使う（`generate.cpp:21322-21340`; 窓の判定は `batch_read.hpp:78-85`）。

`pump` または `pipe_drain` が失敗すると `a pipelined batch window failed` をエラーにし、serve 経路は stderr に `strata serve: ...`、stdout に `ERR ...` を出して終了コード 1 で返る（CUDA error が残っている場合は `_Exit(1)`）。上限値の変換失敗自体はエラー経路にならず、0 として扱われる（`generate.cpp:21303-21315,21593-21604`）。

## ログと測定値

この上限値自体を表示するログはない。piece 間で slot decode を実行したときは stderr に `strata batch: piped read ... then the slots decoded ...`、lead-in decode を実行したときは `strata batch: a read right after a read: ... first` が出る。slot が active でないときの piece は `strata batch: piped read ...` として記録される（`engine/src/program/generate.cpp:21334-21340,21373-21387`）。この変数単独の測定値は記載しない。

## 根拠

- `engine/src/program/generate.cpp:17529-17532` — `--batch-groups` による pipelined 経路の条件。
- `engine/src/program/generate.cpp:20742-20745,21279-21300` — 関連環境変数、既定値、読み取りと piecewise 経路の選択。
- `engine/src/program/generate.cpp:21303-21340,21343-21387` — decode・drain、budget 適用、lead-in とログ。
- `engine/src/program/generate.cpp:21593-21604` — serve の失敗出力と終了経路。
- `engine/include/strata/program/batch_read.hpp:63-85` — piece 丸め、cap/floor の順序、lead-in 窓。
- `docs/SETTINGS.md:237` — 設定一覧の backend 分類。
