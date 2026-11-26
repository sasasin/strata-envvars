# `STRATA_SCORES_THREAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA のプロンプト処理で使う block score kernel を、既存の warp scorer から thread-per-head scorer に切り替える。CUDA では `qsa_block_scores` の `active_blocks > 0` の呼び出しで選択され、HIP では実際の有効 block 数・query 数・GPU 世代も満たした場合に選択される。切替先は通常 scorer と同じ score bits を作る実装として記述されている。decode など `active_blocks` を渡さない呼び出しにはこの切替条件が成立しない（`engine/src/kernels/cuda/qsa_select.cu:2152-2154,2261-2275`、呼び出し元 `engine/src/prefill/prefill.cpp:9445-9457`、`engine/src/core/layer.cpp:1277-1280`）。

## 値と判定

| ビルド経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA (`!__HIPCC__`) | `-1` 相当。Turing は `STRATA_SM75_PERF` に従い、Volta は `STRATA_SM70_PERF` / `STRATA_DEFAULTS` に従う。それ以外は off。 | `std::atoi` の結果が 0 以外。例: `1`, `2`, `-1`, `1tail`, ` 1` | `std::atoi` の結果が 0。例: `0`, `0anything`, `true`, 空文字、数字で始まらない文字列 |
| HIP (`__HIPCC__`) | `-1`。gfx12 では候補、gfx1100 では off | `std::atoi` の結果がちょうど 1。例: `1`, `01`, `1tail`, ` 1` | `std::atoi` の結果が 1 以外。例: `0`, `2`, `-1`, `true`, 空文字 |

どちらも文字列全体の妥当性を検査しない。先頭の空白や符号を `atoi` が処理し、数値部分より後ろの文字は判定に使われない。設定された空文字は `atoi("") == 0` となるため無効。CUDA は 0 以外を on と扱う一方、HIP はちょうど 1 だけを on と扱う（`engine/src/kernels/cuda/qsa_select.cu:2164-2166,2233-2237`）。

## 有効になる条件

- **CUDA:** `qsa_block_scores` が `active_blocks > 0` で呼ばれること。値を明示した場合、`atoi` が 0 以外なら GPU 世代による追加制限なしに thread scorer を選ぶ。未設定なら現在の device の compute capability をキャッシュして判定し、Turing (sm_75) は `STRATA_SM75_PERF` が `atoi` で非ゼロ、Volta (sm_70) は `STRATA_SM70_PERF` が未設定または先頭文字が `0` 以外で、かつ `STRATA_DEFAULTS` が文字列 `026` と完全一致しない場合に on。それ以外の世代では off（`engine/src/kernels/cuda/qsa_select.cu:2155-2176`、`engine/include/strata/core/sm75_series.hpp:24-37`）。
- CUDA の通常起動時、GPU が同一世代の Volta で `STRATA_SM70_PERF` が先頭 `0` でなく、`STRATA_DEFAULTS` が未設定または `026` / `0.2.6` / `v0.2.6` のいずれとも一致しない場合、engine の NV defaults は未設定の `STRATA_SCORES_THREAD` に `1` を設定する。既に設定済みなら値を保持する。混在世代 GPU ではこの NV defaults 適用をスキップする（`engine/src/core/nv_defaults.cpp:136-163,222-233`、`engine/src/program/generate.cpp:4428-4453`、`engine/include/strata/core/defaults_026.hpp:21-29`）。
- **CUDA の既定値上の差:** `STRATA_DEFAULTS=0.2.6` または `v0.2.6` は NV defaults の Volta 表を抑止するが、`scores_thread_on()` 自体が見るのは文字列 `026` との完全一致だけ。そのためこの二つの別名では、`STRATA_SCORES_THREAD` が未設定かつ `STRATA_SM70_PERF` が無効指定でなければ、Volta fallback は on になる（同上）。
- **HIP:** `active_blocks` が `16385` 以上かつ `max_blocks` 以下、`nq >= 64` であること。さらに gfx12 は unset または `atoi` が 1、gfx1100 は明示値の `atoi` が 1 の場合に限り on。別の AMD GPU 世代はこの分岐の対象外。確保済み `max_blocks` だけでは足りず、引数 `active_blocks` 自体が閾値以上である必要がある（`engine/src/kernels/cuda/qsa_select.cu:1283-1297,2233-2240`）。
- CUDA/HIP とも、`active_blocks <= 0` かつ `nq <= MQ` の呼び出しは先行する multi/rows/halve 経路へ進み、この変数の分岐に到達しない（`engine/src/kernels/cuda/qsa_select.cu:2201-2229`）。
- CLI 引数による直接の上書きはこの判定箇所にはない。関係する他変数は CUDA の未設定時既定値を選ぶ `STRATA_SM75_PERF`、`STRATA_SM70_PERF`、`STRATA_DEFAULTS` と、HIP で診断行を出す `STRATA_SCORES_THREAD_TRACE`。

## 実行時の詳細

`scores_thread_on()`（CUDA）または `qsa_block_scores` 内の HIP 分岐で環境変数を関数ローカル `static` として初回に読み、その値を以後の呼び出しでも使う。CUDA は未設定時の GPU ごとの既定判定も `ok[dev]` に保存する。HIP の arch 判定は現在の device ごとに host thread local cache を持つ。したがって初回評価後にプロセス環境を変更しても、この値判定には反映されない（`engine/src/kernels/cuda/qsa_select.cu:2164-2176,2233-2237,1283-1297`）。

thread scorer を選ぶと `block_scores_thread_kernel` を起動し、末尾 block は別途 `block_scores_tail_kernel` で処理する。CUDA で起動時エラーがあれば `qsa_block_scores thread: ...` を stderr に出して `exit(1)`。HIP では `qsa exact thread: ...` を出して `exit(1)`。選ばれないときは通常の `block_scores_kernel` へ進む（`engine/src/kernels/cuda/qsa_select.cu:2248-2277`）。

## ログと測定値

HIP の thread scorer が実際に選ばれたとき、`STRATA_SCORES_THREAD_TRACE` が設定されているか、設定変数が unset 由来の既定 on なら stderr に次の行を出す（各 host thread につき一度）。TRACE は値の内容ではなく設定有無で判定するため、空文字でも行が出る。明示的な `STRATA_SCORES_THREAD=1` で TRACE が unset の場合は抑制される（`engine/src/kernels/cuda/qsa_select.cu:2241-2246`）。

```text
qsa exact thread: the prompt's block scorer runs as the four-lanes-per-query kernel (nq=%lld active_blocks=%lld capacity=%lld; the same scores bit for bit; STRATA_SCORES_THREAD=0 turns it off)
```

CUDA にはこの kernel の選択だけを知らせるログはない。ソースコメントは gfx12 の R9700 上で warp scorer と bitwise equal と記し、parity の 35 cases と 70K / 131K token の exact residual dumps、および scorer stage 3.6–4.4x・prompt read +8–15% という測定結果も記載する。ただしコメントだけでは OS、モデル、量子化、測定回数などの全条件を特定できないため、これらの数値は一般的な性能保証として扱わない（`engine/src/kernels/cuda/qsa_select.cu:1279-1282`）。

## 根拠

- CUDA/HIP の値の変換と dispatch: `engine/src/kernels/cuda/qsa_select.cu:2164-2176,2231-2277`
- HIP の対象 GPU 判定・cache: `engine/src/kernels/cuda/qsa_select.cu:1283-1297`
- prompt から live bound 付きで呼ぶ箇所: `engine/src/prefill/prefill.cpp:9445-9457`
- QSA 切替 kernel の実装: `engine/src/kernels/cuda/qsa_select.cu:1211-1277,1316-1360`
- Volta の既定挿入: `engine/src/core/nv_defaults.cpp:136-163,222-233`; 初期化呼び出し: `engine/src/program/generate.cpp:4428-4453`

`docs/AMD_HIP.md:352-366` の gfx1100 / gfx12 の説明は現行 HIP 分岐の主な閾値と整合する。ただし同資料は `STRATA_SCORES_THREAD_TRACE=1` と記載する一方、実装は値 `1` の比較ではなく設定有無でログを出す。また、同資料の gfx1100 対象が `=1` の場合に限る点は一致する。`docs/DETAILS.md:1336-1344` は Turing 向け `STRATA_SM75_PERF=1` の系列を説明し、現行 CUDA の未設定時 fallback と整合する。
