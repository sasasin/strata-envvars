# `STRATA_Q36_PEER_SWAP_MIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 engine の peer tier が、routing count に応じて専門家 (expert) blob を2枚目の GPU へ入れ替える際の、1回の peer rebalance あたりのコピー量予算を MiB 単位で指定する。値は `peer_rebalance()` 内でバイト数へ変換され、コピーごとにその expert の blob サイズを差し引く。CPU pool から peer tier へ割り当てられる expert の数や各 layer の slot 数を決める値ではない。`engine/src/qwen35/q36_engine.cu:3506-3524,3567-3579`。

この名前を環境から読む Strata 所有コードは同ファイルの `peer_rebalance()` 内の1箇所。`docs/SETTINGS.md` と `terminal/data/settings-register.json` にも名前があるが、これらは設定一覧・登録データであり読み取り実装ではない。

## 値と判定

初めて条件を通過した `peer_rebalance()` 呼び出しで `std::getenv` の結果を `std::atoi` に渡し、MiB 値を `long long` に変換してから `<< 20` する。環境変数が未設定なら 512 MiB。設定されていれば `atoi` の結果を使い、正の値への clamp や parse 成功の確認はない。`atoi` は先頭の空白と符号を許し、数値でない末尾は変換対象にせず、先頭から数値を読めなければ 0 を返す。したがって空文字、`abc`、`0anything` は 0 MiB、`1anything` は 1 MiB、`  +2tail` は 2 MiB 相当となる。`atoi` の `int` 範囲外の入力は規則外。負数も clamp されず、signed 値の左シフトへ渡るため、コードから移植可能な負値の予算を定められない。大文字小文字の比較は行わない。`engine/src/qwen35/q36_engine.cu:3517-3520`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・注意が必要な値 |
|---|---|---|---|
| peer rebalance が値を読む場合 | 512 MiB | `atoi` が正の `int` を返す文字列。例: `1`, `+16`, ` 32MiB`（各々 1, 16, 32 MiB） | 空文字、`abc`、`0`, `0anything` は 0 MiB。負数は clamp されず、負値に対する signed left shift の規則に依存するため有効値を定められない。`atoi` の `int` 範囲外も規則外。 |

0 MiB は「コピー禁止」を保証しない。budget は swap する前には調べず、layer の swap 候補を処理し終わってから `budget <= 0` を確認する。このため予算が 0 以下でも条件に合う候補があれば、その layer 内では `per` 個までコピーされ得る。正の予算でも1回のコピーサイズを超えた時点で止めるのではなく、layer 内で予算を超えることがある。`engine/src/qwen35/q36_engine.cu:3558-3579`。

## 有効になる条件

- Qwen3.6 engine が hybrid expert placement (`m->hybrid`) で動くこと。peer tier のない通常の配置では `peer_rebalance()` の呼び出し側に到達しないか、関数冒頭の guard で戻る。peer tier は `--peer-device` により `open_peer_tier()` で初期化される。`engine/src/qwen35/q36_engine.cu:1881-1885,4343-4350,4387-4396`。
- `peer_rebalance()` 時点で `peer.comp` と `peer.arena` が非 null、slot 数が正で、slot table が全 layer 分あること。peer 側の計算用 buffer 初期化が失敗すると `peer.comp` を null にして CPU pool が各 entry を処理する。`engine/src/qwen35/q36_engine.cu:3506-3509,4220-4234`。
- `STRATA_Q36_PEER_FIXED` が未設定、warmup 中でない、`rows_deferred` 中でないこと。`getenv(...) != nullptr` 判定なので、`STRATA_Q36_PEER_FIXED` の空文字も固定扱いで rebalance を無効にする。`engine/src/qwen35/q36_engine.cu:3510-3511`。
- `STRATA_Q36_PEER_SWAPS` から得る `per_layer` が正であること。未設定時は 4、設定時は `atoi` 結果を負なら 0 に clamp する。各 layer の swap 数は `min(max_swaps, per_layer)` で、現行 caller の `max_swaps` は 8。したがってこの値が 0 以下なら対象変数の予算値にかかわらず swap はない。`engine/src/qwen35/q36_engine.cu:3512-3516,3521-3522,1884`。
- 各 layer に peer slot があり、peer と card 0 のどちらも持っていない正の routing score の expert が存在し、候補 expert の score が入れ替え対象 slot の resident expert より大きいこと。条件を満たさない候補はコピーされない。`engine/src/qwen35/q36_engine.cu:3531-3566`。
- CLI に予算値を設定する引数はなく、`--peer-device`、`--peer-slots`、`--peer-reserve-mib` は peer tier の有無・slot 構成を通じて間接的に適用可否を変える。peer tier が構築できない場合の初期化エラー経路は `engine/src/qwen35/q36_engine.cu:4119-4144,4229-4234`。引数の解析と peer tier 関連引数は `engine/src/qwen35/q36_engine.cu:5339-5353,5384-5392`。

## 実行時の詳細

`after_rows()` は hybrid mode で kept rows を routing score に加算し、`pos` が 32 の倍数になった境界で card 0 の stream を同期して通常の `rebalance(8)` に続けて `peer_rebalance(8)` を呼ぶ。warmup 中にもこの呼び出し経路はあるが、`warming` guard によりそこで戻る。`engine/src/qwen35/q36_engine.cu:1866-1885,4026-4045`。

対象値は関数内 `static const long long` で初回評価時にキャッシュされる。評価は peer tier が存在し、`fixed` / warmup / deferred の guard を通過した呼び出しまで遅延する。その後プロセス内で環境を変更しても値は再読込されない。CLI 引数や別環境変数による cap の上書きはない。`engine/src/qwen35/q36_engine.cu:3506-3524`。

各 rebalance ではキャッシュ済み cap を新しい `budget` にコピーする。各 layer で候補と最少 routing count の peer resident slots を並べ、score が高い未配置 expert を slot に載せ替え、その blob を pinned host arena から peer GPU arena へ `cudaMemcpyAsync` する。コピー byte 数を budget から減らし、layer 処理後に budget が 0 以下なら後続 layer を止める。したがって cap は rebalance 全体に対する目安で、layer 内の `per` 上限まで超過し得る。slot table と `P.exp_in_slot` も host 側で更新され、peer の次の `peer_share()` がその配置を使う。card 0 の slot 配置はこの peer swap では変更しない。`engine/src/qwen35/q36_engine.cu:3531-3581`。

## ログと測定値

`STRATA_Q36_PEER_SWAP_QUIET` が未設定なら、swap ごとに stderr へ `strata-q36: peer swap ...` の行を出す。設定されている場合（空文字を含む）はこの行を抑制する。rebalance 内で1件以上 swap した場合は累計 MiB 等の `strata-q36: peer tier: ...` 行が出る。engine の終了時にも swap 数が 0 より大きければ `strata-q36: peer tier motion: ...` を報告する。予算超過や0予算を理由にした専用警告・エラーはない。`engine/src/qwen35/q36_engine.cu:3524,3575-3587,5550-5552`。

この環境変数自体の性能測定値は、対象 commit の読み取り実装からは確認できないため記載しない。

## 根拠

- `engine/src/qwen35/q36_engine.cu:3506-3524` — peer tier / 固定条件、他の上限値、対象環境変数の読み取り・変換・cache。
- `engine/src/qwen35/q36_engine.cu:1866-1885,3531-3587` — rebalance の呼び出し境界、slot 交換、コピー予算の消費とログ。
- `engine/src/qwen35/q36_engine.cu:4119-4144,4220-4234,4343-4350,4387-4396` — peer tier と hybrid 配置の初期化条件・失敗時の経路。
- `engine/src/qwen35/q36_engine.cu:5550-5552` — 終了時の peer swap 集計ログ。
