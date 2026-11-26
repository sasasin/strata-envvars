# `STRATA_PREFILL_STREAM_ALL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL prefill の長い prompt chunk で、VRAM expert cache にない expert を「その chunk が実際に route したものだけ」先読みするか、「全 layer の全 non-resident expert」を layer ごとに順番に ring へ流すかを選ぶ。未設定時は VRAM cache が (layer, expert) ペアの 90% 超を保持する場合に後者を使い、明示値 `1` はこの割合の条件を強制的に越える。明示値 `0` は routed-only staging に留める。実際のストリーミングは chunk 長、ring、expert source にも依存する。読み取りと分岐は `engine/sycl/src/prefill/prefill.cpp` の `ring_slots()` にあり、CUDA/HIP の同名読み取りは見つからなかった（同ファイル以外のソースにはコメント参照があるが、環境からの読み取りではない）。候補一覧と設定レジストリも backend を SYCL としている（`terminal/data/settings-register.json:36843-36852`）。

## 値と判定

関数内 `static const int` の初期化時に `std::getenv` で一度読み、値全体の数値 parse はせず先頭 1 文字だけを見る。変数が存在して先頭文字が `'1'` なら `1`、それ以外（空文字を含む）は `0`。未設定だけが `-1` となり、自動判定に進む（`engine/sycl/src/prefill/prefill.cpp:315-320`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
| --- | --- | --- | --- |
| SYCL `ring_slots()` | `g_nonres_share < 0.10` のとき全 non-resident expert の walk を許可。それ以外は routed-only | 先頭が `1`。例: `1`, `10`, `1anything` | 設定ありで先頭が `1` 以外。例: `0`, `01`, `2`, `true`, ` 1`, `false`, 空文字 |

大文字小文字・空白・後続文字・数値としての妥当性は検査しない。負値や `atoi` のような変換はない。未設定時の割合判定は厳密な `< 0.10`（10%ちょうどでは無効）。`g_nonres_share` は generate 側が `host_res` のうち `r < 0` の個数を全ペア数で割って設定し、`host_res` が空なら `1.0` とする（`engine/sycl/src/program/generate.cpp:6599-6612`）。

ring の決定では `STRATA_PREFILL_RING` が設定されているとその `atoi` 値が ring 候補 `r` となり、値が `STAGE`（8）なら他の条件より先に staging-only を返す。設定がない場合は layer-split の `g_ring_override`、auto scan の `g_ring_budget`、pinned share 由来の ring が候補となる。stream-all walk を許可した後は `r` を `[16, ring_cap()]` に収める。したがって `STRATA_PREFILL_RING=8` は `=1` より優先して walk を止める一方、`STRATA_PREFILL_RING=0` や `abc` は `atoi` 結果が 0 となり 16 slots に clamp される（`engine/sycl/src/prefill/prefill.cpp:291-323`）。

## 有効になる条件

- SYCL backend の prefill 経路であること。対象の実読み取りは `engine/sycl/src/prefill/prefill.cpp` にあり、設定レジストリの backend も `sycl`（`terminal/data/settings-register.json:36843-36852`）。
- `STRATA_PREFILL_STREAM_ALL` が未設定なら、VRAM cache 外のペア比率が 10% 未満であること。`=1` でこの割合条件を上書きできる。`=0` またはそれ以外の明示値では walk を許可しない（`engine/sycl/src/prefill/prefill.cpp:319-321`）。
- 実行 chunk `T` が `STRATA_PREFILL_STREAM_MIN` による閾値以上であること。閾値は未設定で 1024、設定時は `atoll` の結果で、`T < stream_all_min()` なら ring は `STAGE`（`engine/sycl/src/prefill/prefill.cpp:215-218, 323`）。CLI の `--prefill` / `--prefill-auto` などで決まる chunk がこの条件に影響する。
- 有効な ring が `STAGE` より大きいこと。特に `STRATA_PREFILL_RING=8` は全 walk を止める（`engine/sycl/src/prefill/prefill.cpp:309-323`）。
- `Prefill::run` に渡る `m.src` が null でないこと。実処理側は `m.ring > STAGE && T >= stream_all_min() && m.src != nullptr` のときだけ `stream_all` とする（`engine/sycl/src/prefill/prefill.cpp:3090`）。
- `STRATA_PREFILL_RING` が設定されていれば、その ring 値が自動の候補 ring を置き換える。layer split が正の `STRATA_SPLIT_RING` から設定する `g_ring_override` や auto chunk scan の budget より優先される（`engine/sycl/src/prefill/prefill.cpp:291-310`; `engine/sycl/src/program/generate.cpp:7231-7240`; `engine/include/strata/prefill/prefill.hpp:145-150`）。`STRATA_RING_BYTES` は auto chunk scan の ring budget 有効性に関係するが、stream-all 判定自体を上書きしない（`engine/sycl/src/program/generate.cpp:6713-6755, 7317-7327`）。

## 実行時の詳細

`ring_slots(T)` が stream-all 判定まで到達した最初の呼び出しで環境変数を読み、関数内 static に保存する（`STRATA_PREFILL_RING` が `STAGE` の場合はその前に返る）。リング容量は prefill の sizing / `bytes_needed` 判定でも照会され、最終的には `Prefill::init()` が `m.ring` に保存し、ring 用 device buffer を確保する（`engine/sycl/src/prefill/prefill.cpp:291-323, 1780-1797, 2484-2489`; `engine/sycl/src/program/generate.cpp:6718-6755, 7391-7393, 7496-7504, 13354-13357`）。プロセス実行中に環境を変更してもこの値は再読込されない。`--serve` でもプロセス内の同じ SYCL prefill 実装を使うため、リクエスト単位の設定ではない。

`stream_all` になると、layer 順・expert ID 順に全 expert を走査し、cache にあるものと peer が保持するものを飛ばして残りを stream sequence に加える。その後の ring は先読み copy と compute の進行に使われる。stream-all が無効な場合はこの全 expert walk を選ばず、staging 経路を使う（`engine/sycl/src/prefill/prefill.cpp:3086-3092, 3145-3164, 3303-3314`）。環境変数は expert routing や cache の収容数を直接変更せず、prefill で先読みする non-resident expert の範囲を選ぶ。

ring が大きくなった場合、`Prefill::init()` の device buffer 確保量も増える。確保が成立しない場合は `prefill: device buffers for a chunk of ... tokens do not fit (...)` を `err` に設定し、generate 側で `strata generate: <err>` として stderr に出して終了コード 1 で戻る（`engine/sycl/src/prefill/prefill.cpp:1841-1845`; `engine/sycl/src/program/generate.cpp:13354-13358`）。この変数固有の有効・無効ログは実装にない。`docs/INTEL.md` は未設定時の 90% 条件と `=0` / `=1` の強制を説明しているが、先頭文字判定、空文字、評価時 cache、chunk/ring/source 条件は上記ソースで補った（`docs/INTEL.md:454`）。

## 根拠

- 読み取り・値判定・ring の優先順位: `engine/sycl/src/prefill/prefill.cpp:291-323`
- long-prompt 閾値: `engine/sycl/src/prefill/prefill.cpp:215-218`
- `host_res` からの non-resident 比率: `engine/sycl/src/program/generate.cpp:6599-6612`
- 実際の stream 判定と全 expert sequence: `engine/sycl/src/prefill/prefill.cpp:3086-3092, 3145-3164`
- ring の割当・buffer sizing: `engine/sycl/src/prefill/prefill.cpp:1780-1797, 2484-2489`
- init 失敗の文言と generate の返却: `engine/sycl/src/prefill/prefill.cpp:1841-1845`; `engine/sycl/src/program/generate.cpp:13354-13358`
- SYCL backend 登録と利用者向け説明: `terminal/data/settings-register.json:36843-36852`; `docs/INTEL.md:454`
