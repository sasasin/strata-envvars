# `STRATA_INK_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 版 Inkling-2 の `InkHybridEngine` で、CPU worker が RAM 上の expert を処理するとき、1 expert の行を複数 worker に分割する方式を有効・無効にします。既定値は有効です。有効でも条件を満たさない訪問では行分割せず、既存の expert 単位の処理へ進みます。これは CPU worker 内の処理分担を選び、router が選んだ expert やその選択自体を変更する設定ではありません（実装: `engine/src/inkling2/cuda/ink_hybrid.cuh:1630,1657-1679,1923-1953`）。

実際の読み取りは `InkHybridEngine::start_workers()` にあります。同関数は CUDA Inkling-2 runner から host expert がある場合に呼ばれます（`engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1784`; `engine/src/inkling2/cuda/ink_runner.cuh:497-503,622-628,1374-1381,1588-1595`）。

## 値と判定

`std::getenv("STRATA_INK_SPLIT")` で設定有無を調べ、値が存在すれば先頭文字だけを `e[0] != '0'` で判定します。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1784`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA `InkHybridEngine::start_workers()` | `split_experts` の初期値 `true` のまま | 空文字、`1`、`true`、`false`、`off`、` 0` など先頭文字が `0` でない値 | `0`、`0anything`、`00` など先頭文字が `0` の値 |

空文字は「設定あり」ですが、先頭文字が NUL なので `!= '0'` は真となり、有効です。`false` や `off` も先頭が `0` ではないため有効です。先頭の空白は除去されないため、` 0` も有効になります。境界は文字列全体の数値範囲ではなく、先頭 1 文字だけです（同上）。

## 有効になる条件

- CUDA 版 Inkling-2 の `InkHybridEngine` が使われ、`start_workers()` に到達すること。runner は `n_host_experts > 0` の場合に worker を開始します。GPU 上だけで全 expert を処理する構成では、この読み取り経路に入りません（`engine/src/inkling2/cuda/ink_runner.cuh:497-503,622-628,1374-1381,1588-1595`）。
- 行分割には `split_experts == true`、worker 数 `n_threads >= 2`、対象訪問の `cur_nj >= 1` が必要です（`engine/src/inkling2/cuda/ink_hybrid.cuh:1658-1660`）。`n_threads` は `start_workers()` の引数または既定値から始まり、`STRATA_INK_THREADS` が設定されていれば `atoi` した値を 1〜128 に clamp して上書きします。この分割には結果が 2 以上である必要があります（例: 未設定時は引数または CPU 数由来の既定値、`STRATA_INK_THREADS=1` や非数値文字列は 1、`2` 以上なら分割可能性を残します。`engine/src/inkling2/cuda/ink_hybrid.cuh:1781-1784`）。
- 対象訪問の全 expert について host body が存在し、cold-slot を使っておらず、`host_eval::expert_splittable(...)` が真である必要があります。いずれかを満たさない場合 `plan_row_tasks()` は偽を返し、expert 単位の処理へ進みます（`engine/src/inkling2/cuda/ink_hybrid.cuh:1660-1663,1925-1953`）。
- `STRATA_INK_SPLIT` に対応する CLI 引数や別の優先設定は読み取り箇所にありません。`start_workers()` の `active` 早期 return 後は再評価されないため、同じ engine の worker 起動後にプロセス環境を変更しても設定は反映されません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1784,1978-1979`）。
- 候補一覧以外の Strata 側の記載では `docs/SETTINGS.md:408` が適用 backend を「NVIDIA and AMD」、`terminal/data/settings-register.json:17519-17526` が `cuda-hip` としています。しかし、この commit で名前を実際に読む箇所は CUDA の `engine/src/inkling2/cuda/ink_hybrid.cuh:1784` だけで、HIP ソースには同名の読み取りがありません。したがって、ここでソースから裏付けられる適用範囲は CUDA 実装です。AMD/HIP での効果は確認できません。

## 実行時の詳細

`split_experts` は engine インスタンスのメンバーとして `true` で初期化され、worker pool の開始時に環境変数があれば上書きされます。起動処理の後半で `active = true` となり、後続の `start_workers()` 呼び出しは先頭で戻るため、この値は当該 engine の worker pool に対して初回開始時に固定されます（`engine/src/inkling2/cuda/ink_hybrid.cuh:1630,1779-1784,1978-1979`）。

有効で、対象 expert 群が分割可能な場合、`plan_row_tasks()` は各 expert の gate/up と down の行範囲を chunk に分けて task 化します。master と worker がこれらの task を実行し、down 側 task は同じ expert の gate/up task 完了を待ってから処理します。条件不成立または設定無効時は、master/worker が従来の expert 単位の doorbell job を処理します（`engine/src/inkling2/cuda/ink_hybrid.cuh:1633-1654,1657-1679,1923-1953`）。

## ログと測定値

この変数の値や有効・無効を直接示すログ、警告、エラーは該当コードにありません。測定値も、参照した `docs/DETAILS.md` にこの変数の記載はありません。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:1630,1657-1679,1779-1789,1923-1953,1978-1979` — 既定値、値判定、worker 起動時の読み取り、適用条件と row task / fallback。
- `engine/src/inkling2/cuda/ink_runner.cuh:497-503,622-628,1374-1381,1588-1595` — host expert がある場合の worker 起動。
- `docs/SETTINGS.md:408`、`terminal/data/settings-register.json:17519-17526` — AMD/HIP も含める設定資料上の表記。読み取り実装を示す根拠ではありません。
