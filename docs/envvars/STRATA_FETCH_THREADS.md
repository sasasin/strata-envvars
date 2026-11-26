# `STRATA_FETCH_THREADS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--mmap-experts` 系のファイル読み込みで、staging buffer に読み込む expert 群を処理する worker 数を指定する。既定は 8。CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL の `engine/sycl/src/program/generate.cpp` が値を `FileExpertSource` に渡し、通常の mapped-file 読み込みでは `fill_many` の同時 worker 数の上限として使う。GPU cache の容量や prompt 用の staging thread 数を設定する変数ではない（読み取りと setter: `engine/src/program/generate.cpp:8628-8631`, `engine/sycl/src/program/generate.cpp:4726-4736`; worker 数の使用: `engine/src/core/expert_source.cpp:2745-2757`, `engine/sycl/src/core/expert_source.cpp:1030-1041`）。

## 値と判定

両方の読み取り箇所で `getenv` が null でないことに加え、`std::atoi(v) > 0` を要求する。通過した値を `set_fetch_threads` に渡し、setter は 1 未満を 1 にするが、呼び出し側の条件により実際に渡るのは正数だけ。未設定、空文字、`atoi` が 0 を返す文字列、負数は setter を呼ばず、メンバー初期値 8 のままになる（`engine/src/program/generate.cpp:8628-8631`, `engine/sycl/src/program/generate.cpp:4733-4736`, `engine/include/strata/core/expert_source.hpp:910-911,1187`, `engine/sycl/include/strata/core/expert_source.hpp:543-544,647`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---:|---|---|
| `engine/src` と SYCL の mmap expert source 初期化 | 8 | `1`, `8`, `+3`, ` 4`, `12x`（`atoi` が正数を返す） | 空文字、`0`, `-2`, `true`, `0anything`, `x12`（`atoi` が 0 以下） |

文字列全体の妥当性検査はなく、`atoi` が認識する先頭の整数部分が使われるため、`12x` は 12、先頭空白と符号も受け付ける。大文字小文字の概念はない。正数への上限 clamp はない。`atoi` の表現範囲を超える入力の結果はコードで検査・定義していないため、範囲外値は指定しないこと。無効値を示す警告やエラーはこの判定箇所からは出ない。

## 有効になる条件

- `engine/src` では `o.mmap_experts` の分岐に入ることが必要。通常は `--mmap-experts`、`--ssd-experts`、`--resident-experts`、`--resident-budget-gib` などがこの状態を作る。CUDA 系では expert arena を RAM 不足で開けず file source に fallback する経路も同じ設定を読む（`engine/src/program/generate.cpp:4218-4257,8876-8911`）。
- SYCL では `o.stream_experts && !o.mmap_experts` が優先される。この分岐は `GgufExpertSource` を使い、`STRATA_FETCH_THREADS` を読む mmap 分岐には進まない。mmap 側に入るには `o.mmap_experts` が必要（`engine/sycl/src/program/generate.cpp:4711-4736`）。
- mapped reads で `fill_many` が処理する todo がある場合、実 worker 数は `min(todo の件数, fetch_threads_)`。このため指定値より todo 件数が少なければ指定値全員は起動しない（`engine/src/core/expert_source.cpp:2692-2758`, `engine/sycl/src/core/expert_source.cpp:979-1041`）。
- `direct_` が有効な unbuffered 読み込みでは、この変数による上限は使われず、16 blob 単位の direct batch を最大 4 worker で処理する。CUDA の非同期 prefetch 経路も direct reads なら同じ 4 worker 上限を使う（`engine/src/core/expert_source.cpp:2581-2611,2692-2719`; SYCL: `engine/sycl/src/core/expert_source.cpp:979-1004`）。
- 同じ source の RAM copy にある expert、override 済みの expert、既に staging 中／済みの expertは todo に追加されないため、その読み込みに worker は使われない（`engine/src/core/expert_source.cpp:2513-2542`; SYCL: `engine/sycl/src/core/expert_source.cpp:920-943`）。
- CLI に fetch thread 数を指定する引数はこの設定箇所にはなく、他の環境変数との優先順位や上書きもない。`STRATA_STAGER_THREADS` / `STRATA_STAGER_RING` は prompt 側に別設定として記載されており、この変数からは読み取られない（区別の記述: `engine/src/core/expert_source.cpp:2500-2502`; `docs/UNSLOTH_Q4.md:235`）。

## 実行時の詳細

環境変数は engine の起動処理で mmap source を初期化する際に読み取られ、`FileExpertSource` instance の `fetch_threads_` に保存される。値を `static` cache したり、各 token ごとに環境から読み直したりする実装ではない。通常の `prefetch` は有効な expert のうち必要なものを todo に集めて `fill_many` に渡し、mapped read では最大 `fetch_threads_` 個の worker（そのうち 1 個は呼び出し thread）が `fill_stage` を処理して全 worker を join する。CUDA 系の `prefetch_begin` の非 direct 経路も同じ上限で thread を作る（`engine/src/core/expert_source.cpp:2449-2478,2547-2612,2692-2758`; SYCL: `engine/sycl/src/core/expert_source.cpp:920-944,979-1041`）。

ファイル source の open に失敗すると、通常の mmap 経路では `strata generate: <error>` を stderr に出して終了コード 1。CUDA 系の RAM fallback 後に file source も開けない場合は、別の stderr 文言を出して resident arena 側へ戻す再試行が行われる。この環境変数自体について、値を表示するログや無効値警告はない（`engine/src/program/generate.cpp:8631-8643`; SYCL: `engine/sycl/src/program/generate.cpp:4736-4738`）。

## ログと測定値

設定値や実際に使った fetch worker 数を表示するログは見当たらない。open 成功時には mmap source の使用を示す `strata generate: experts via mmap (...)` が stderr に出るが、thread 数の確認にはならない（`engine/src/program/generate.cpp:8645-8647`, `engine/sycl/src/program/generate.cpp:4740-4741`）。この変数単独の測定値は現行ソース内で確認できない。`docs/UNSLOTH_Q4.md:235` は既定 8 と用途を説明しており、setter の初期値・利用箇所と一致する一方、unbuffered/direct 経路の最大 4 worker という例外もソースにある。

## 根拠

- 値の読み取りと setter: `engine/src/program/generate.cpp:8628-8631`, `engine/sycl/src/program/generate.cpp:4733-4736`
- 既定値・setter: `engine/include/strata/core/expert_source.hpp:910-911,1187`, `engine/sycl/include/strata/core/expert_source.hpp:543-544,647`
- mapped reads と direct reads の worker 数: `engine/src/core/expert_source.cpp:2692-2758`, `engine/sycl/src/core/expert_source.cpp:979-1041`
- prefetch 経路と todo の選別: `engine/src/core/expert_source.cpp:2449-2478,2513-2542,2547-2612`, `engine/sycl/src/core/expert_source.cpp:920-944`
- mmap / stream の条件と観測可能な open 結果: `engine/src/program/generate.cpp:4218-4257,8631-8647,8876-8911`, `engine/sycl/src/program/generate.cpp:4711-4741`
