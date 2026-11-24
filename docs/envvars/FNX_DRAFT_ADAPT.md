# `FNX_DRAFT_ADAPT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`Session::generate` が MTP draft chain の長さを受理率に合わせて毎回選ぶか、上限 `K` まで固定するかを切り替える。未設定時は適応選択が有効。`0` のときは通常 MTP chain を常に `K` 個、DFlash2 chain を信頼度条件で得られる最大数まで使う。`K` 自体は変更せず、sFNX の `--spec K`（既定 6）などで与えた上限に従う。読み取りと選択処理は `engine/src/split/src/session.cpp` の `Session::generate` にある（`engine/src/split/src/session.cpp:398-417, 581-612`; `engine/src/split/tools/sfnx.cpp:67-90, 453-457`）。

対象はこの split-engine の `Session` 経路である。sFNX の単独 decode は `Session::generate` を呼ぶ。バッチ decoder が有効な複数 slot 経路は別の `BatchDecoder` planner を使い、この変数を読まない（`engine/src/split/tools/sfnx.cpp:448-458, 860`; `engine/src/split/src/batch.cpp:65-87, 260-301`）。`fnx_run decode` も `Session::generate` を使う。候補名のソース全体検索では他の読み取り箇所は見つからなかった。

## 値と判定

`fnx::env_int` は `getenv` で取得し、`parse_whole` が符号付き base-10 整数として文字列全体を `strtoll` で変換する。先頭・末尾の空白、空文字、数値の後ろの文字、整数範囲外は受け付けず、`FNX_DRAFT_ADAPT: '<値>' is not a whole number` の例外になる。変換後は `!= 0` 判定であり、値域 clamp はない（`engine/src/split/src/env.hpp:15-21, 33-40`; `engine/src/split/src/session.cpp:416`）。

| 条件 | unset | 有効になる値（適応選択） | 無効になる値（固定上限側） |
|---|---|---|---|
| split `Session::generate` | `1`（既定） | 任意の非ゼロ整数。例: `1`, `-1`, `+2` | `0`, `+0`, `-0` |

`true`、`false`、空文字、`1x`、` 1`、`1 ` は整数全体でないため「無効側」ではなくエラーになる。負数を含む任意の非ゼロ整数は適応を有効にする。`--spec`/`K` は chain の上限として適用され、環境変数による `K` の上書きはない（`engine/src/split/src/session.cpp:419-427, 589-612`; `engine/src/split/tools/sfnx.cpp:67-90`）。

## 有効になる条件

- `Session::generate` が呼ばれること。適応値は生成呼び出しの先頭で毎回読み取られるため、draft を使わない場合でも不正値なら例外になる（`engine/src/split/src/session.cpp:398-416`）。
- MTP chain が候補になること。通常の MTP chain は `e_.draft` で d1 を作り、lookup draft が見つからない場合に chain を伸ばす（`engine/src/split/src/session.cpp:596-619`）。
- DFlash2 を使う場合は `e_.df2_on()` が真であること。DFlash2 は累積確率が `FNX_DF2_CONF` 未満になるまでの候補数を先に定め、その数を適応選択または固定選択で制限する（`engine/src/split/src/session.cpp:453-456, 565-593`）。
- `FNX_SPECULATE=0` では検証後に draft を保持せず次の round に進むため、chain 長の選択結果は利用されない。値の読み取り自体は行われる（`engine/src/split/src/session.cpp:142, 565-569, 596-600`）。
- lookup draft が見つかった round は MTP chain の長さ選択へ進まず、lookup drafts が使われる（`engine/src/split/src/session.cpp:575-580, 601-607`）。`--lookup` は lookup の上限を設定する（`engine/src/split/tools/sfnx.cpp:67-90, 453-457`）。
- sFNX で `--batch > 1` かつ `FNX_BATCH_DRAFTS` により `BatchDecoder` が使われる経路には適用されない。そこでは `choose_rows` による別の計画処理を行う（`engine/src/split/tools/sfnx.cpp:448-458`; `engine/src/split/src/batch.cpp:65-87, 260-301`）。

## 実行時の詳細

環境値は `Session::generate` の各呼び出しで一度読み、ローカル定数 `adapt` に保持する。関数内 static cache はなく、プロセス環境を次回呼び出しまでに変更すれば次の呼び出しで再評価される。呼び出し中の変更は反映されない（`engine/src/split/src/session.cpp:398-417`）。

適応有効時、生成呼び出しごとに各 chain 位置の `tried` / `stood` を初期化し、draft の受理結果で更新する。`chain_len` は長さ 1..`K` の期待 token 数を定数の round・verify row・draft call コストで割り、最大率の長さを返す。通常 MTP では選択長に最大 `K` を適用し、4 chain ごとに次の位置を測るため 1 個追加して `K` 以下に制限する。`FNX_DRAFT_ADAPT=0` ならこの選択を行わず通常 chain は `K` 個を作る（`engine/src/split/src/session.cpp:417-427, 529-535, 608-619`）。

DFlash2 では `FNX_DF2_CONF`（既定 `0.35`）と最大 `K` / drafter の `kDrafts` から `kmax` を求める。適応有効時は `chain_len(0.0)` と 4 chain ごとの探索分を使って `kmax` 以下にし、無効時は `kmax` を採る（`engine/src/split/src/session.cpp:453-456, 581-593`）。ドラフトは検証 window に加えられ、メインモデル側で受理・拒否された結果だけが出力されるため、この変数はドラフト提案数の選択を変え、sampling 設定そのものは変えない（`engine/src/split/src/session.cpp:467-471, 490-525, 536-557`）。

## ログと測定値

有効・無効を示す専用ログはない。値が整数でない場合、helper が例外 `FNX_DRAFT_ADAPT: '<値>' is not a whole number` を投げる。`fnx_run` は `fnx_run: <例外>` を stderr に出して終了コード 1 を返す（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/tools/fnx_run.cpp:1364-1373`）。sFNX は要求処理中の未処理例外を `ERR <例外>` と stderr の `sfnx: failed: <例外>` で通知し、終了コード 1 で終了する（`engine/src/split/tools/sfnx.cpp:1094-1103, 1160-1165`）。

ソースコメントには Q4 lab の通常 MTP chain 長固定時の round 時間 `K=1/2/3/4: 12.47/14.76/16.60/18.34 ms`（2026-10-25）と記されているが、コメントだけでは測定環境・回数などを特定できないため、一般的な効果の測定値としては扱わない（`engine/src/split/src/session.cpp:412-417`）。

## 根拠

- `engine/src/split/src/session.cpp:398-427, 467-525, 529-619` — 読み取り、適応選択、MTP / DFlash2 / lookup 経路。
- `engine/src/split/src/env.hpp:15-21, 33-40` — 整数全体の変換、未設定時既定値、無効値例外。
- `engine/src/split/tools/sfnx.cpp:67-90, 448-458, 860, 1094-1103, 1160-1165` — sFNX の K/lookup 設定、Session と batch decoder の選択、失敗経路。
- `engine/src/split/tools/fnx_run.cpp:461-492, 1364-1373` — `fnx_run decode` の Session 使用と失敗表示。
- `engine/src/split/src/batch.cpp:65-87, 260-301` — batch decoder が使う別 planner。
