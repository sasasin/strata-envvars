# `STRATA_PIPED_READ_PIECE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--batch` のスロット群を layer split 上で複数の pipeline group として実行しているとき、プロンプト読込を分割する opt-in 値である。正の値なら一度に読む token 数の目安になり、各片の終わりで pipeline を drain して、待機中リクエストへの譲渡や既存スロットの decode を可能にする。未設定または 0 以下では、従来どおりプロンプト区間を一度の read で処理する。読み取りと分割処理は `engine/src/program/generate.cpp` の `read_part` 内にある（同ファイル 21279-21300 行）。

## 値と判定

`read_part` が初めてこのコードに到達したとき `std::getenv` で読み、関数内 `static const int64_t` に保存する。未設定は 0。設定済みなら `std::atoi` を使い、結果を `max(0, ...)` で負値から 0 にする。したがって空文字、数値に変換できない文字列、`0`、`0anything`、`-1`、`true` は無効。`1`、`+1`、`1anything`、先頭空白の後の正数は有効になる。`atoi` は先頭の整数部分だけを読むため、末尾の文字や小数部分は検査しない。整数として表現できない大きさの入力に対する `atoi` の結果は保証されない。実際に有効になるかはさらに pipeline 条件に依存する（21284-21299 行）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| `read_part` の値判定 | 0（分割しない） | `1`, `4096`, `1tail` | 空文字, `0`, `0anything`, `-1`, `true` |
| pipeline 条件を満たさない場合 | 分割しない | なし（正数でも無視） | なし |

正の値 `N` は `piped_read_piece(N, C)` に渡る。`C` は通常 `max(sp.chunk(), 1)`、read plan 使用中は plan の chunk グリッドに揃えたサイズである。実際の片の長さは `floor(N/C)` 個の chunk を基準にし、chunk 数を最低 1・最大 32 に clamp して `C` を掛けた値となる。従って `N<C` でも 1 chunk 読み、`N` が 32 chunks を超える指定は 32 chunks に制限される。端数 token は chunk 境界に丸められる（`engine/include/strata/program/batch_read.hpp:56-67`; `engine/src/program/generate.cpp:20966-20970,21296-21300`）。

この変数を上書きする CLI 引数はない。`--batch`、`--batch-groups` と layer split の構成は値自体を変えず、分割を適用できる pipeline を選ぶ（`generate.cpp:17529-17533,21296-21300`）。

## 有効になる条件

- `--batch` が正、`--batch-groups` 解決値が 1 より大きく、layer split の pipeline stage 数が 1 より多いこと。実装上の条件は `piped = o.batch > 0 && o.batch_groups > 1 && n_pipe > 1`（`engine/src/program/generate.cpp:17529-17533`）。単一 GPU、serial group、または layer split でない経路では正の値も分割に使われない。
- 条件を満たす構成で `read_part` による実際のプロンプト read があること。cache から復元して read しない区間には作用しない。設定値は `read_part` の `piece_now` で判定される（同ファイル 21296-21300, 21568-21572 行）。
- OS 固有や `#define` による追加 gate はこの読み取り箇所にはない。`docs/BATCHING.md` は NVIDIA/AMD の layer split 利用を記載するが、ここでは backend ではなく上記 pipeline 状態を条件にしている（`docs/BATCHING.md:343-358`）。
- 片の終わりに待機要求へ譲るには、別途 `BYIELD` が届き `give_way` の条件を満たす必要がある。画像なし、prompt cache 有効、未読残量が chunk/short-read の基準を超えることなどが条件で、条件を満たさなければ read は続行する（`engine/src/program/generate.cpp:20971-21007,21353-21370`）。
- 片の間に既存 slot を decode するのは `batch_on()` の場合だけ。decode 時間予算は `STRATA_BATCH_DECODE_SHARE`（unset は 0.5）を基準に、`STRATA_PIPED_DECODE_MAX_MS`（unset は上限なし）と `STRATA_PIPED_DECODE_MIN_MS`（unset は 0）で制限する。これらも `static` 値として初回到達時に読み取られる（`generate.cpp:20737-20745,21288-21294`; `batch_read.hpp:69-75`）。

## 実行時の詳細

読み取った値は `read_part` 内 static に保持されるので、その関数で初回評価した後にプロセス環境を変更しても反映されない。別プロセスでは再評価される。未設定または無効値では `piece <= 0` となり、通常の `run(a0, b0)` 一回に戻る（`engine/src/program/generate.cpp:21284-21287,21343-21345`）。

有効な pipeline read は各片を `run_conc(q, r)` で読み、各片の間で `BYIELD` を確認する。待機要求へ譲る場合は、既読部分を slot に保持してこの read を終了し、サーバーは後続処理でその slot から続行する（`generate.cpp:21345-21370,20971-21002`）。譲らなかった場合、slot が動作中なら pipeline の `pump(true)` を decode 予算まで回し、その後 `pipe_drain()` で in-flight group を完了してから次片を読む。slot が動作中でなければ decode phase はなく、分割 read のみ行う（同ファイル 21302-21320,21371-21388）。

連続する piecewise read が前回の終了から 1 秒以内（または decode budget を加えた時間内）に始まる場合は、次の読込前にも decode budget を一度与える。これにより連続する read の間で slot 群が停止し続けないようにする（`generate.cpp:21322-21341`; `batch_read.hpp:78-85`）。片ごとの pipeline drain が入るため、長い prompt read の所要時間は増える可能性がある。Strata の `docs/BATCHING.md` はこれを待機要求の応答性と decode 機会との交換として説明している（343-370 行）。

## ログと測定値

有効な分割では、中間片ごとに stderr に `strata batch: piped read N tokens in X ms (to Q of T)` を出す。slot が decode した場合は `, then the slots decoded R rows in Y ms` が続く。最後の片では `q >= b0` となり、この piece ログを出さない。BYIELD 成功時は `strata batch: the prompt read gives way at ...`、不成立時は `strata batch: BYIELD ... not taken ...` を出す（`engine/src/program/generate.cpp:21343-21388,20998-21007`）。

read または pipeline window が失敗すると、serve 経路は stderr の `strata serve: <理由>` と stdout の `ERR <理由>` を出し、通常は status 1 で終了する。CUDA error が残っている場合は flush 後 `_Exit(1)` を使う。pipeline window の失敗理由は `a pipelined batch window failed`（同ファイル 21302-21315,21593-21605）。

`docs/BATCHING.md:374-401` には 2x RTX 5090、Windows 11、CUDA 13.0、Swift 1.5 IQ3_S などの条件を付けた比較測定がある。本調査ではその数値を再測定しておらず、文書には一般化した速度・token 同一性の主張を追加しない。

## 根拠

- `engine/src/program/generate.cpp:17529-17533` — pipeline group の成立条件。
- `engine/src/program/generate.cpp:20737-20745,20960-20970` — decode share と read chunk の決定。
- `engine/src/program/generate.cpp:21279-21300` — 対象変数の読み取り、static cache、関連設定、分割判定。
- `engine/src/program/generate.cpp:21302-21320,21322-21388` — decode budget、drain、連続 read の lead-in、piece loop とログ。
- `engine/src/program/generate.cpp:20971-21007,21353-21370,21568-21605` — BYIELD、read 呼出しと失敗経路。
- `engine/include/strata/program/batch_read.hpp:56-85` — chunk 丸め、上限、decode budget、lead-in 判定。
- `docs/BATCHING.md:343-370,374-401` — 設計説明と条件付き測定のソース照合。
