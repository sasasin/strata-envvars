# `FNX_PF_STAGE_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

split engine の batched prefill で、ExpertCache の GPU slot に載っていない expert を GPU にコピーして保持する stage バッファの上限を、カードごとに MiB 単位で指定する。各カードの上限は「どの layer でも slot 外にある expert の合計バイト数の最大値」と指定上限の小さい方で、`prefill_stages()` はそのサイズのバッファを 2 個ずつ確保する。上限を 0 にすると stage バッファを確保せず、slot 外の expert は RAM 上のデータをその場で読む経路になる。expert の選択や重みの値を変える設定ではなく、コピーして読む量を制御する（`engine/src/split/src/prefill.cu:1232-1245`, `1247-1258`, `1452-1501`）。

## 値と判定

`env_int()` は `getenv()` で値を取り、符号付き base-10 整数を文字列全体から parse する。任意の `+` / `-` と数字列のみを受け付け、空白、空文字、末尾の文字、整数範囲外は整数として受け付けない。未設定なら既定値 `384`。parse 後に負数は専用の `runtime_error` になる。`0` 以上には明示的な上限検査がなく、実際の byte 数は `most` との `min` で制限される（`engine/src/split/src/env.hpp:15-22,33-40`; `engine/src/split/src/prefill.cu:1242-1244`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `pf_stage_bytes()` が ExpertCache slot のあるカードで評価される | `384` MiB | `0` 以上の整数。例: `0` は stage 無し、`1` は最大 1 MiB、`+384` は 384 MiB 上限 | 空文字、`true`、`false`、`0anything`、空白付きの値、`long long` 範囲外は `env_int()` の整数 parse error。`-1` は `FNX_PF_STAGE_MIB: want MiB >= 0, got -1` で失敗 |
| `w.ec.n_slots == 0` | 読み取りなし | 該当なし | 値の parse も負数検査も行われず、変数はこのカードの stage サイズに影響しない |

正の整数に対する独立した clamp はありません。cap は `(size_t) stage_mib << 20` として byte に変換されます。非常に大きい値に対する上限チェックもないため、`size_t` の幅を超える MiB 変換を通常の巨大な上限として扱える保証はありません（同 `prefill.cu:1242-1244`）。

## 有効になる条件

- `Engine::pf_stage_bytes()` を通る split engine の実行で有効。`w.ec.n_slots` が 0 のカードでは関数が先に `0` を返し、環境変数を読みません（`engine/src/split/src/prefill.cu:1232-1244`）。
- stage 自体は `Engine::prefill()` の batched prompt path で使われる。card 0 の stage buffer が確保され、かつ prompt の token 数が `FNX_PF_STAGE_ROWS` 以上であることが必要。`FNX_PF_STAGE_ROWS` は unset で `2048`、この変数自身とは別に `0..INT32_MAX` の整数検査がある。条件を満たさない prompt は expert を RAM 上でその場読みする（`engine/src/split/src/prefill.cu:1123-1142,1300-1309,1452-1455`）。
- 値を渡す CLI 引数による上書き経路は見つからなかった。`FNX_PREFILL=0` などで呼び出し元が batched prefill 自体を使わない場合、この stage 制御も実行されない（`engine/src/split/tools/fnx_run.cpp:1003-1018`）。
- CUDA / HIP の split prefill 実装にある設定。`FNX_PF_STAGE_MIB` の箇所自体に `FNX_HIP` による判定差はない。Metal 実装での参照は見つからなかった（`engine/src/split/src/prefill.cu:1232-1258`）。

## 実行時の詳細

Engine 構築時、arena を使う場合は slot 配置の空き VRAM 見積もりに `2 * pf_stage_bytes(c)` を加算し、expert の再配置後に `prefill_stages()` が最終サイズを計算して確保する。arena を使わない場合は `prefill_stages()` でサイズを計算して確保する。したがって arena 経路では環境値を配置前の見積もり時と配置後の確保時に読み、再配置ループの反復中にも読み得る。関数内 cache はなく、Engine 構築後に環境を変えても既存 stage サイズは変わらず、次の Engine 構築時に評価される（`engine/src/split/src/engine.cu:326-359,390-392`; `engine/src/split/src/prefill.cu:1232-1258`）。

prefill 時、slot にある expert はその GPU slot を参照する。slot 外 expert のうち layer ごとの byte budget に収まる分は `stage[l & 1]` に順番にコピーし、残りは `w.ec_host_gu` / `w.ec_host_dn` の RAM 上のデータを直接参照する。stage の 2 面は layer ごとに交互に使われる。従って値を小さくするとコピー対象が減り、0 ではすべての slot 外 expert が直接参照経路になる（`engine/src/split/src/prefill.cu:1452-1501`）。

## ログと測定値

この変数専用の通常ログはない。`FNX_PF_TIMING` が有効で、stage byte 数が 0 でない場合に限り、stderr に `prefill on card %d: passes of %d chunks, stages of %zu MiB` を出す。0 byte の場合は確保前に continue するため、この行も出ない（`engine/src/split/src/prefill.cu:1247-1258`; `engine/src/split/src/env.hpp:51-52`）。

無効な文字列では `env_int()` が `<変数名>: '<値>' is not a whole number` を投げる。負数では `FNX_PF_STAGE_MIB: want MiB >= 0, got <値>` を投げる。`fnx_run` は stderr に `fnx_run: <理由>` を出して status 1 で終了し、`sfnx` の engine 初期化失敗は `ERR <理由>` を stdout、`sfnx: failed: <理由>` を stderr に出して status 1 で終了する（`engine/src/split/src/env.hpp:33-39`; `engine/src/split/src/prefill.cu:1242-1244`; `engine/src/split/tools/fnx_run.cpp:1364-1373`; `engine/src/split/tools/sfnx.cpp:1094-1102,1122-1136`）。対象変数について Strata の資料に条件付き測定値は見つからなかった。

## 根拠

- `engine/src/split/src/env.hpp:15-22,33-40,51-52` — 整数の字句・範囲判定、未設定時 fallback、env flag。
- `engine/src/split/src/prefill.cu:1123-1142,1232-1258,1300-1309,1452-1501` — ExpertCache 条件、stage サイズと確保、prompt 条件、slot / RAM / stage の選択とコピー。
- `engine/src/split/src/engine.cu:326-359,390-392` — arena 時の stage 予算見積もりと Engine 構築中の確保。
- `engine/src/split/tools/fnx_run.cpp:1003-1018,1364-1373`; `engine/src/split/tools/sfnx.cpp:1094-1102,1122-1136` — 呼び出しと失敗の観測経路。
