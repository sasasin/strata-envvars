# `STRATA_INK_PROF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling2 の診断用計測を有効にする。CUDA backend では CUDA Graph を無効にし、GPU event による runner の処理区間計測と、host 側の logits / step 計測を有効にする。値の先頭文字が `2` の場合は、追加で大きな prefill chunk の区間表示も行う。生成や sampling の選択方法を変える設定ではなく、測定・ログ出力を追加する（`engine/src/inkling2/cuda/ink_cuda_backend.cu:311-319`、`engine/src/inkling2/cuda/ink_runner.cuh:1913-1924`）。

serve ループにも独立した読み取りがある。ここでは値の内容にかかわらず、変数が設定されていれば sampling と protocol を含む host 側の集計を有効にする（`engine/src/inkling2/ink_serve.h:1132-1141`）。

## 値と判定

読み取り箇所ごとに判定が異なる。CUDA backend は初期化時に `std::getenv` の戻り値の先頭 1 文字だけを検査し、serve ループは各集計対象ステップで null かどうかだけを見る。文字列全体の parse、数値変換、空白除去、大文字小文字変換はない。

| 読み取り箇所 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA backend の runner 計測 | `prof_enabled=false`。CUDA phase / host backend timing を追加しない | 先頭が `1` または `2`。例: `1`, `2`, `1anything`, `2xyz` | 先頭がそれ以外。例: 空文字、`0`, `true`, ` 1`, `3`。CUDA backend の計測は有効にならない |
| `ink_serve.h` の sampling / protocol 計測 | `on=false` | 空文字を含む、環境から取得できる任意の値。例: ``, `0`, `false`, `1` | `getenv` が null の場合のみ |

CUDA backend では先頭だけを見るため、`10` も `1` と同じ分岐、`20` も `2` と同じ分岐になる。空文字は CUDA backend では無効だが、serve 側では設定済みとして有効。これらは同じプロセスで併用される独立した判定である（`engine/src/inkling2/cuda/ink_cuda_backend.cu:311-314`、`engine/src/inkling2/ink_serve.h:1141`）。

## 有効になる条件

- CUDA phase 計測は Inkling2 が `INKLING_ENABLE_CUDA` でビルドされ、`make_default_backend` が CUDA backend を選び、その backend の `init` が呼ばれる場合に限る。backend 選択は build macro と `force_cpu` に従う。`--cpu` などで CPU backend を選ぶ経路や、HIP / Metal / SYCL backend では CUDA backend 側の読み取り・GPU phase 計測はない（`engine/src/inkling2/ink_backend.h:198-215`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:311-319`）。
- CUDA backend で先頭文字が `1` / `2` なら、runner の `prof_enabled` を設定し CUDA Graph を無効にする。通常の Graph 可否（GPU 条件、EP2 / layer-split 等）にかかわらずこの代入を行い、eager launch 側で event 計測する（`engine/src/inkling2/cuda/ink_cuda_backend.cu:303-319`）。
- `2` の prefill 区間表示は `forward_seq` が eager 経路に入り、`M >= 64` のときだけ。`1` では prefill chunk の個別表示をしない（`engine/src/inkling2/cuda/ink_runner.cuh:3693-3708`）。
- serve の sampling / protocol 集計は backend の種類に関係なく `run_serve_loop` で変数が設定されていて、`n_want > 0` のステップがある場合に記録する。したがって空文字や `0` でもこの集計は有効だが、CUDA phase 計測は有効にならないことがある（`engine/src/inkling2/ink_serve.h:1132-1141`）。
- CLI 引数や別の環境変数による値の上書きは、この変数の読み取り箇所にはない。CUDA backend が選ばれない場合にも serve 側の計測は独立して適用される。

## 実行時の詳細

CUDA backend は `init` 中に一度値を読み、runner の `prof_enabled` / `prof_prefill` に保存する。この設定は runner の実行中に再読込されない。`prof_mark_start` / `prof_mark_end` は CUDA event を stream に記録し、`prof_flush` が stream を同期して event の経過時間を集計する。区間には residual/control/norm、dense QKV、sconv/KV、attention、dense WO、MoE、unembed、および MoE 内の router/bin/gate-up/down の分類がある（`engine/src/inkling2/cuda/ink_runner.cuh:1913-1953,1956-1964`）。

CUDA backend の追加 timing は full logits 出力経路および batched decode 経路にも入る（candidate rows の経路では full logits 用の host timing guard を通らない）。logits の unembed、device-to-host copy、caller へのコピーを32 logits batchごとに集計して出力し、batched eager forward の所要時間も32 stepごとに出す。これらの backend host 集計カウンターは出力ごとにリセットされず、プロセス内の累積平均である。計測中は該当処理の後で CUDA stream を同期するため、ここに出る値は通常経路の非同期実行そのものではなく、この計測経路で同期を含めて得た時間である（`engine/src/inkling2/cuda/ink_cuda_backend.cu:800-805,827-843,988-1004`）。

serve ループ側は各ループ反復で `getenv` の有無を検査し、`SampleProf` の終了時に `n_want > 0` の場合だけ集計する。64 stepごとに forward_batch と sampling+protocol の平均を stderr に出す。この集計カウンターは出力ごとにリセットされず、プロセス内の累積平均である。この読み取りは backend 初期化時の CUDA 判定とは別で、プロセス内で環境値が変更された場合は次の反復から判定が変わる。Strata 内にこの変数を書き換える処理は確認できなかった（`engine/src/inkling2/ink_serve.h:1132-1141`）。

CUDA runner の通常の `forward_seq` は単一 token (`M == 1`) を100 stepごとに出力し、`forward_batched` は50 stepごとに出力する。`2` での prefill は各 eager chunkを個別表示する。CUDA phase 出力は全て stderr で、ログに含まれる `/ iters` は累積値を iteration 数で割った値（`engine/src/inkling2/cuda/ink_runner.cuh:1943-1964,3693-3708,3863-3874`）。

## ログと測定値

CUDA backend で先頭文字が `1` または `2` の場合、初期化時に次を stderr に出す（値が `2` でも文言は `=1` のまま）。

```text
[InkCUDA] STRATA_INK_PROF=1: eager launches, per-phase timing (runner phases every 50 batched steps, host phases every 32)
```

その後の代表的な出力は `[PROF DECODE-M1 / ...]`、`[PROF DECODE-B... / ...]`、`[PROF PREFILL-M... / 1 iters]`、`[InkCUDA PROF host] ...`、`[InkCUDA PROF step] ...`。serve ループの集計は `[ink_serve PROF] ...`。前記の通り、実装上 `forward_seq` の単一 token は100回ごと、batched decode は50回ごとであり、起動メッセージの “runner phases every 50 batched steps” は両方の頻度を説明していない。測定値の資料・測定条件はこの調査範囲で確認できなかったため、性能値は記載しない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:319,839-840,1002`、`engine/src/inkling2/cuda/ink_runner.cuh:1958-1963,3697-3708,3865-3873`、`engine/src/inkling2/ink_serve.h:1138-1140`）。

計測で使う CUDA event の作成・記録・同期・経過時間取得は `INK_CK` で検査される。失敗時は `strata-inkling CUDA error <code> at <file>:<line>: <runtime error>` を stderr に出して終了する。serve の fatal device error 経路では stderr にも説明を出し、stdout に `ERR fatal GPU error: ...` を出して `_Exit(3)` する（`engine/src/inkling2/cuda/ink_cuda.cuh:34-42`、`engine/include/strata/core/device_error_exit.hpp:26-33`）。

## 根拠

- すべての実行時読み取り: `engine/src/inkling2/cuda/ink_cuda_backend.cu:311-319`、`engine/src/inkling2/ink_serve.h:1132-1141`。
- backend 選択と build 条件: `engine/src/inkling2/ink_backend.h:178-215`。
- runner の event 計測とログ: `engine/src/inkling2/cuda/ink_runner.cuh:1913-1964,3693-3708,3863-3874`。
- CUDA backend の host timing と同期: `engine/src/inkling2/cuda/ink_cuda_backend.cu:800-843,988-1004`。
- CUDA profiling API のエラー経路: `engine/src/inkling2/cuda/ink_cuda.cuh:34-42`、`engine/include/strata/core/device_error_exit.hpp:26-33`。
- serve の起動経路: `engine/src/inkling2/ink_main.cpp:1086-1094`。
