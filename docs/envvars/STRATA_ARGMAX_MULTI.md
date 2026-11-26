# `STRATA_ARGMAX_MULTI`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA sampler の greedy argmax で、条件を満たすときに 1 token 行を 8 CTA の thread-block cluster で処理する経路を選ぶ。未設定または `atoi` が 0 以外になる値ではこの経路を許可し、`atoi` が 0 なら cluster を使わず 1 block の greedy kernel に進む。cluster kernel と 1-block kernel は同じ token を選ぶ実装として記述されており、変わるのは argmax の実行経路である（`engine/src/kernels/cuda/sampler.cu:189-219, 1260-1284`）。

CUDA 以外にも同名の読み取りはあるが、HIP は cluster 関数が即座に `false` を返し、SYCL も現状の `#if 1` stub が `false` を返すため、この変数で実際の kernel 選択は変わらない（`engine/src/kernels/cuda/sampler.cu:1211-1215`, `engine/sycl/src/kernels/cuda/sampler.dp.cpp:1402-1406, 1490-1532`）。

## 値と判定

CUDA と SYCL の `sample_tokens` 内で `std::getenv` の戻り値を調べ、未設定なら `true`、設定済みなら `std::atoi(v) != 0` とする。文字列全体の厳密な数値検証はなく、`atoi` が先頭から変換できた整数部分だけでゼロ判定する。先頭空白と符号は `atoi` の変換規則に従い、変換できない文字列や空文字は 0 となる。たとえば `0`, `0anything`, `0.5`, `true`, 空文字は無効（cluster 不許可）、`1`, `-1`, `2`, `1anything` は有効（cluster 許可）。数値の許容範囲チェックや clamp はない（`engine/src/kernels/cuda/sampler.cu:1273-1279`; SYCL: `engine/sycl/src/kernels/cuda/sampler.dp.cpp:1490-1496`）。

| 実装経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA sampler | cluster を許可 | `atoi` が 0 以外（例: `1`, `-1`, `1tail`） | `atoi` が 0（例: 空文字, `0`, `0tail`, `true`） |
| HIP sampler | cluster 不許可 | 該当なし（cluster 関数が常に `false`） | 該当なし |
| SYCL sampler | cluster 不許可 | 該当なし（cluster 関数が常に `false`） | 該当なし |

## 有効になる条件

- cluster による経路切替があるのは CUDA build であること。HIP build では `__HIPCC__` 分岐により cluster を使わない（`engine/src/kernels/cuda/sampler.cu:1211-1215`）。
- `sample_tokens` が greedy 分岐（`p.greedy` または `p.temperature <= 0.0f`）に入ること。sampling 経路ではこの設定を参照しない（`engine/src/kernels/cuda/sampler.cu:1273-1285`）。
- penalty 用 shared memory が不要（`shmem == 0`）で、`p.logit_bias` がないこと（`engine/src/kernels/cuda/sampler.cu:1270-1284`）。
- CUDA device の compute capability major が 9 以上、cluster kernel の PTX と binary version がともに 90 以上で、occupancy 判定で少なくとも 1 cluster を実行できること。device ごとの判定結果は `ok[dev]` に保存される。`n_tokens > 65535` も cluster を使わない条件である（`engine/src/kernels/cuda/sampler.cu:1216-1249`）。
- `STRATA_EMULATE_CC` は compute capability の host 判定にも影響する。helper は `atoi` 値が 75 以上 120 未満なら実機の major を置き換えるため、90 以上の値は major 条件を満たし得るが、PTX/binary version と occupancy の条件は別に残る。この値も helper の `static` に cache される（`engine/include/strata/core/emulate.hpp:58-77`; 使用箇所: `engine/src/kernels/cuda/sampler.cu:1236-1245`）。
- SYCL (Intel Arc) は cluster kernel が未実装の stub で常に fallback し、この値は実効性を持たない（`engine/sycl/src/kernels/cuda/sampler.dp.cpp:1402-1406, 1490-1532`）。

CLI 引数や別の環境変数による上書きは、この読み取り・分岐にはない。greedy でない場合、penalty または logit bias がある場合、あるいは CUDA device/build の条件を満たさない場合は、値が cluster 許可でも通常の 1-block kernel に fallback する（`engine/src/kernels/cuda/sampler.cu:1273-1284`）。

## 実行時の詳細

設定値はプロセス起動時には読まず、CUDA または SYCL の `sample_tokens` が初めて greedy 分岐に入ったとき、関数内 `static const bool multi` の初期化で読み取る。その後は同一プロセス内で値が cache されるため、初回 greedy 呼び出し後に環境を変更しても反映されない。非 greedy 経路しか通らない間は初期化されない（CUDA: `engine/src/kernels/cuda/sampler.cu:1273-1279`; SYCL: `engine/sycl/src/kernels/cuda/sampler.dp.cpp:1490-1496`）。

CUDA で `multi` が真かつ他の条件を通ると `sample_greedy_cluster` が device 条件を確認して cluster kernel を launch する。条件を満たさない場合は呼び出し側が 1-block `sampler_greedy_kernel` を launch する。cluster launch 自体が CUDA error を返す場合は stderr に `sample_tokens cluster launch: <CUDA error>` を出して `exit(1)` する。後続の通常 sampler launch error は `sample_tokens launch: <CUDA error>` を出して `exit(1)` する（`engine/src/kernels/cuda/sampler.cu:1249-1256, 1280-1284, 1313-1318`）。device 判定失敗や cluster 非対応、設定による無効化は fallback し、専用の理由ログは出さない。

## ログと測定値

環境変数の読み取り・有効化・fallback を知らせるログはない。上記の launch failure 時だけ CUDA error が stderr に出る。`docs/DETAILS.md:1621` は `STRATA_ARGMAX_MULTI=0` を decode cluster kernel の無効化スイッチとして記載するが、この変数単独の測定条件・測定値は示していないため、性能値は記載しない。

## 根拠

- `engine/src/kernels/cuda/sampler.cu:1211-1257, 1260-1319` — CUDA の環境読み取り、cluster 条件、fallback、ログと終了。
- `engine/src/kernels/cuda/sampler.cu:189-219` — cluster kernel が CUDA sm_90 以降向けであること、および one-block argmax と同じ token を返すという実装コメント。
- `engine/include/strata/core/emulate.hpp:58-77` — `STRATA_EMULATE_CC` が compute capability 判定を置き換える条件。
- `engine/sycl/src/kernels/cuda/sampler.dp.cpp:1402-1406, 1472-1532` — SYCL の同名読み取りと常時 fallback。
- `engine/include/strata/kernels/sampler.hpp:47-50` — CUDA/HIP での API と cluster 不成立時の説明。
- `engine/sycl/include/strata/kernels/sampler.hpp:46-49` — SYCL 側 API の説明。
- `docs/DETAILS.md:1621` — 変数と decode cluster kernel 無効化の資料上の記載。
