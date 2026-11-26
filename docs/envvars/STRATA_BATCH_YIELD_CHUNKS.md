# `STRATA_BATCH_YIELD_CHUNKS`

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

--batch の prompt read がレイヤー分割を通り、decode 中の slot がないとき、1 回の read を何個の chunk ごとに区切るかを指定する。区切りごとに BYIELD を確認できるため、短い prompt を待つ要求へ read を譲る機会を作る。read は元の chunk 境界を保ったまま分割される。この値を prompt token に変換する処理はない。実装は request 処理内の read_part にある batch_read_piece 呼び出しと、算術 helper engine/include/strata/program/batch_read.hpp にある。（`engine/src/program/generate.cpp:20737-20741,21284-21300`; `engine/include/strata/program/batch_read.hpp:1-5,13-27`）

## 値と判定

generate.cpp は std::getenv の結果を std::atoi で変換し、負数を std::max(0, ...) で 0 に丸める。未設定は 8。atoi は文字列全体の妥当性を検証せず、数値として読める先頭部分を使う。したがって空文字や数値で始まらない文字列（true、false など）は 0、1 は 1、8abc は 8、0anything は 0 になる。1.5 は先頭の整数 1 として扱われる。先頭空白や符号も atoi の変換規則に従い、大文字小文字の比較はない。0 または負数は helper に 0 を渡し、「残り全部を一回で読む」値になる。数値変換範囲を超える文字列の結果はこの実装から保証できない。（`engine/src/program/generate.cpp:20962-20965`; `engine/include/strata/program/batch_read.hpp:22-27`）

| 実行条件 | unset | 設定値の効果 | 例 |
|---|---:|---|---|
| --batch、非 pipelined、レイヤー分割あり、decode 中の slot なし | 8 chunks / piece | max(0, atoi(value)) 個の chunk / piece。0 は全残りを一回で読む | unset: 8、1: 1、3: 3、0・-2・空文字・true・false: 一回読み |
| --batch なし、または pipelined groups | 既定値の piece 計算は使われない | この変数は piece 幅を変えない | helper は 0 を返す |
| レイヤー分割なし、またはレイヤー分割中に slot が decode 中 | 既定値の piece 計算は使われない | 変数値によらず一 chunk ごとの piece | helper は chunk を返す |

ここでいう pipelined groups は、--batch > 0、--batch-groups > 1、かつ複数 stage がある経路。`STRATA_PIPED_READ_PIECE` が正値なら pipelined 経路専用の piece 計算が選ばれ、この変数の値は使われない。（`engine/src/program/generate.cpp:17529-17532,21284-21300`; `engine/include/strata/program/batch_read.hpp:22-27,56-67`）

## 有効になる条件

- --batch が有効であること。無効なら helper は 0 を返し、残りの prompt を一回で読む。（`engine/src/program/generate.cpp:17529-17532,21296-21300`; `engine/include/strata/program/batch_read.hpp:22-25`）
- --batch-groups による pipelined groups ではないこと。pipelined は helper の対象外で、`STRATA_PIPED_READ_PIECE` が正値ならその token 数に基づく別の piece 幅を使う。pipelined でない layer split の読み取りでも、`STRATA_PIPED_READ_PIECE` は参照されない。（`engine/src/program/generate.cpp:21284-21300`; `engine/include/strata/program/batch_read.hpp:22-27,56-67`）
- 値による chunk 数の指定が効くのはレイヤー分割があり、slot が decode 中でない場合だけ。slot が decode 中なら通常どおり一 chunk ごとに区切り、レイヤー分割のない経路も一 chunk ごとに区切る。（`engine/include/strata/program/batch_read.hpp:14-20,24-27`）
- chunk 幅は計画済み read なら計画 chunk の整数倍、そうでなければ prefill buffer の chunk 幅から決まる。指定値 0 の場合は、レイヤー分割の read 全体を一回にする。（`engine/src/program/generate.cpp:20966-20970,20769-20803`; `engine/include/strata/program/batch_read.hpp:22-27`）
- 読み取り箇所と piece helper に OS / backend の条件分岐はない。適用の分岐は --batch、pipelined、layer split、slot の状態で決まる。（`engine/src/program/generate.cpp:20962-20965,21296-21300`; `engine/include/strata/program/batch_read.hpp:22-27`）
- CLI 引数による値の上書きや、この変数より優先する別の環境変数はない。`STRATA_BATCH_DECODE_SHARE` は slot の decode 時間を決める別設定であり、piece 数は決めない。（`engine/src/program/generate.cpp:20737-20745,21284-21300`）

## 実行時の詳細

環境値は request の read_part 経路にある関数内 static const int64_t 初期化で一度だけ読み取られる。最初にこの宣言へ到達した時点の値がプロセス内で cache され、以後の request や実行中の環境変更では再読込されない。（`engine/src/program/generate.cpp:20960-20965`）

計算された piece 幅が正なら、read をその幅以下の区間で実行し、各区間の終了時に BYIELD <slot> を待ち受ける。BYIELD が来た場合でも、read を譲れるのは残り token 数が max(C_read, --short-read) より大きく、対象 slot が decode 中でなく、要求側 slot が割り当て済みならその slot と一致し、画像要求でなく、prompt cache が有効で、読み済み部分の slot へのコピーにも成功する場合に限られる。譲れると読み済み部分を slot に保存し、stderr に「strata batch: the prompt read gives way at ...」を出して yield 状態で終了する。これらの条件を満たさないかコピーに失敗すると「strata batch: BYIELD ... not taken ...」を出し、read は後続 piece で続く。（`engine/src/program/generate.cpp:20971-21007,21343-21370`）

helper が 0 を返すと read_part は piece ループを使わず、残り全体を一回の run に渡す。指定値が使われて piece 幅が正でも、最後の区間後には次の BYIELD 確認境界はない。（`engine/src/program/generate.cpp:21343-21349`; `engine/include/strata/program/batch_read.hpp:13-27`）

## ログと測定値

この変数の読み取りや設定値を報告する専用ログはない。BYIELD の要求が来て譲れる場合は「strata batch: the prompt read gives way at %lld of %lld tokens; slot %d holds it (copied in %.1f ms)」、譲れない場合は「strata batch: BYIELD %d not taken at %lld of %lld%s%s」が stderr に出る。いずれも値を明示するログではなく、BYIELD がない場合はこの分岐のログも出ない。（`engine/src/program/generate.cpp:20975-21007`）

## 根拠

- 候補名の本番読み取りと parse、既定値: `engine/src/program/generate.cpp:20960-20965`。
- 適用範囲・piece 計算・chunk 境界: `engine/src/program/generate.cpp:21284-21300`; `engine/include/strata/program/batch_read.hpp:13-27`。
- pipelined 経路の別設定: `engine/src/program/generate.cpp:17529-17532,21284-21300`; `engine/include/strata/program/batch_read.hpp:56-67`。
- BYIELD の成立条件と観測ログ: `engine/src/program/generate.cpp:20971-21007,21343-21370`。
