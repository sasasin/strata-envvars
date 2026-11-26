# `STRATA_TEST_PINNED_SHARE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

プロンプト処理用の expert streamed ring を決める際に使う「pinned expert の比率」を上書きするテスト用フックです。通常は `ExpertSource::pinned()` から各 expert の pinned 状態を数えて比率を計算しますが、この変数が設定されていればその比率を `atof` の結果で置き換えます。コメントも用途を「tests: the Windows-like ring rule」としています。実際の expert の pin/unpin 状態は変えず、比率に応じた ring の sizing 分岐だけを変えます（`engine/src/program/generate.cpp:11120-11131`）。

## 値と判定

変数の有無は `getenv` の非 null 判定です。設定値は文字列全体の検証や範囲制限をせず `std::atof` で `double` に変換し、後段では `share >= 0.9` かどうかだけを使います（`engine/src/program/generate.cpp:11129-11131`、`engine/src/prefill/prefill.cpp:816,873`）。

| 条件 | unset | 高 share 側（`>= 0.9`） | 低 share 側（`< 0.9`） |
|---|---|---|---|
| source があり、`--prefill` 等の設定後に `o.prefill_chunk > 0` | 実際の pinned bytes / total expert bytes。total が 0 なら `1.0` | 例: `0.9`, `1`, `1anything` | 例: 空文字、`0`, `0anything`, `0.89`, `-1`, `true`, 数値で始まらない文字列（判定箇所: `engine/src/program/generate.cpp:4000-4008,11120-11131`） |
| source がない、または `o.prefill_chunk <= 0` | この箇所では環境変数を読まない。共有値は初期値 `1.0` のまま | 該当なし | 該当なし |

`atof` は数値の先頭部分を変換し、後続文字列の妥当性を検査しません。そのため `1anything` は `1`、`0anything` は `0` として扱われ、`true` のように数値変換できない文字列や空文字は `0` になります。負値も拒否・clamp されず低 share 側になります。`nan` 相当の値が変換された場合も比較 `>= 0.9` は成立しません。明示的な無効値に対する警告・fallback はありません（同上）。

## 有効になる条件

- `srcp != nullptr` かつ `o.prefill_chunk > 0` の場合に限り、この変数を読みます。expert source がなくても、prefill chunk が 0 以下でも読みません（`engine/src/program/generate.cpp:11120-11131`）。
- 条件を満たすと、生成経路の setup 中に一度だけ `Prefill::set_pinned_share` へ値を渡します。標準入力で複数要求を処理する `--serve` も同じ `generate.cpp` の実装を通りますが、この値を要求ごとに読み直す箇所はありません（設定箇所: `engine/src/program/generate.cpp:11095-11120`）。
- layer-split の auto placement と startability probe はこの変数の読み取り（11130行）より前に `Prefill::pinned_share()` を参照します。その箇所で `STRATA_PREFILL_LEND_PCT` が未設定の場合に選ぶ 90% / 85% の既定値は、override ではなく初期値 `1.0` に基づきます。後段の `--prefill auto` 用 `kAutoLendPct` は override 後に評価されます。`STRATA_PREFILL_LEND_PCT` が設定されていれば、その `atoi` 値が優先されます（`engine/src/program/generate.cpp:7063-7068,10081-10086,11130-11131,11238-11243`）。
- `STRATA_PREFILL_RING` が設定されると ring 選択ではその値が優先されます。HIP の matrix-core attention 分岐は、明示 ring と layer-split override がない場合に先に ring を返すため、その経路でも pinned share による標準 ring 選択は使われません（`engine/src/prefill/prefill.cpp:843-879`）。
- 通常の ring 選択で auto planner の byte-budget が該当する場合は、その budget が pinned share による既定 slot 数より優先されます。byte-budget の有効条件には `STRATA_RING_BYTES`（未設定または先頭文字が `0` 以外）が含まれます（`engine/src/prefill/prefill.cpp:833-841,873-878`）。
- `generate.cpp` は CUDA/HIP 共通 engine、Metal engine、SYCL engine の各 build 定義に含まれます。共有コードにこの環境変数を除外する OS/backend/build macro guard はありません。HIP 固有の ring 早期分岐は上記のとおり別扱いです（`engine/cmake/strata_gpu_engine.cmake:482,548`、`engine/metal/CMakeLists.txt:143,176`、`engine/sycl/CMakeLists.txt:304,375-377`）。

## 実行時の詳細

実測比率は各 layer/expert の blob byte 数を合計し、`srcp->pinned(l,e)` が true の分を pinned bytes として割って求めます。環境変数があればこの計算結果を置換し、グローバル `g_pinned_share` に保存します。環境変数自体は static cache ではなく setup 時の一度の読み取りです。後からプロセス環境を変えても保存済み値は変わりません（`engine/src/program/generate.cpp:11120-11131`、`engine/src/prefill/prefill.cpp:750,3555-3561`）。ただし、これより前の split auto placement と probe の lend percentage 判定は初期値 `1.0` を使います（`engine/src/program/generate.cpp:7063-7068,10081-10086`）。

保存値は prompt ring の slot sizing に使われます。標準経路では `0.9` 以上なら fused ring の有無に応じて既定 ring を `1024` または `384` slots とし、未満なら `96` slots とします。`STRATA_RING_BYTES` が有効な auto-budget 経路では、高 share 側の byte budget を 1024/384-slot 相当（Q2_0 blob 基準）として pack の blob サイズから slot 数へ換算し、低 share 側の既定 budget はその 1/4 です。通常 ring の slot 数は `ring_cap()` で上限を受け、chunk が `stream_all_min()` 未満なら大きい ring ではなく `STAGE` を返します（`engine/src/prefill/prefill.cpp:808-841,843-879`）。

Prefill layout は選んだ ring 数を `m.ring` に保存し、staging の slot 数と ring buffer の配置・サイズ計算に使います（`engine/src/prefill/prefill.cpp:2865-2889`）。このフック自体が allocation の失敗を処理したり、実際の expert pinning を変更したりする処理はありません。

## ログと測定値

この環境変数を読み取ったことや選択値を表示する専用ログ、警告、エラー終了経路はありません。調査対象のソースと `docs/DETAILS.md` では、この変数の値による測定値も確認できません。

## 根拠

- `engine/src/program/generate.cpp:11120-11131` — 実際の pinned share 計算、条件付き `getenv` / `atof`、Prefill への設定。
- `engine/src/prefill/prefill.cpp:750,816,833-879,2865-2889,3555-3561,3791-3808` — 初期値、ring sizing、setter と planner 用既定値。
- `engine/cmake/strata_gpu_engine.cmake:482,548`、`engine/metal/CMakeLists.txt:143,176`、`engine/sycl/CMakeLists.txt:304,375-377` — 各 backend の build に対象ソースが含まれること。
