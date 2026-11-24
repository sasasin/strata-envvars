# `INK_SY_PROF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2 の Intel Arc SYCL runner にある decode step profiler を有効にします。`1` は phase group ごとの計測、`2` はそれに mix/router 内の細分化計測を加えます。プロファイラは SYCL queue を待って時間を集計し stderr に出す診断用処理で、推論の分岐や token の選択値を変更する処理はありません。ただし追加の queue wait が実行時間に介入します。読み取りと集計は `ink_sy_common.h` の `sy_prof()` / `sy_prof_*()`、呼び出しは `InkSyRunner::forward_batch()` にあります（`engine/src/inkling2/sycl/ink_sy_common.h:195-223,231-275`; `engine/src/inkling2/sycl/ink_sy_runner.h:467-475,937-940`）。

## 値と判定

`std::getenv("INK_SY_PROF")` の返す文字列の先頭 1 文字だけを比較します。数値変換、文字列全体の比較、空白除去、値域チェックはありません。大文字小文字を区別する比較ですが、受理する文字は数字の `1` と `2` だけです（`engine/src/inkling2/sycl/ink_sy_common.h:212-220`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL runner を含む build | `on=false`, `fine=false`。この変数による計測 wait はなし | 先頭が `1`（`1`, `10`, `1anything`）で phase 計測。先頭が `2`（`2`, `20`, `2anything`）で phase と細分化計測 | 空文字、`0`、`3`、`true`、`false`、` 1` など、先頭が `1`/`2` でない値 |

空文字は unset と同じく無効です。`2` 以外の `1` 始まりはすべて coarse 計測になり、`2` 始まりは後続文字にかかわらず fine 計測になります。SYCL を build しない実行ファイルには、この SYCL profiler の読み取り経路は組み込まれません（`engine/CMakeLists.txt:23-32`; `engine/src/inkling2/CMakeLists.txt:243-248`）。

## 有効になる条件

- `STRATA_ENABLE_SYCL=ON` の build で SYCL サブディレクトリが構成され、Inkling SYCL runner が実行されることが前提です。トップレベルの SYCL build は CUDA/HIP と同時指定できず、SYCL を選ぶと同階層の通常構成を抜けます（`engine/CMakeLists.txt:23-32`; `engine/src/inkling2/CMakeLists.txt:246-248`; `engine/src/inkling2/sycl/CMakeLists.txt:7-9,43-45`）。
- 有効な値でも `forward_batch()` の `M == 1` のときだけ step を数えます。`M <= 0` または `M > max_batch` は profiler 開始より前に失敗扱いで返り、`M > 1` はこの計測対象外です（`engine/src/inkling2/sycl/ink_sy_runner.h:467-475`; `engine/src/inkling2/sycl/ink_sy_common.h:224-227`）。
- CLI の `--bench` 専用ではありません。呼び出し元が単一 token を `forward_batch()` に渡した場合に動き、standalone CLI の decode では `M=1`、prompt prefill は prompt 長 `P` が渡されます（`engine/src/inkling2/sycl/ink_sy_main.cpp:31-57,257-264`）。
- `INK_SY_TIMING` は相互作用します。`INK_SY_PROF` が無効でも `INK_SY_TIMING` の先頭が `1` なら single-token step の host-submit/total 計測と 64 step ごとの要約出力が有効になります（phase wait は増えません）。一方、`INK_SY_PROF` が `1`/`2` なら `q.timing` も自動で true になり、`INK_SY_TIMING` の値で profiler を無効にはできません（`engine/src/inkling2/sycl/ink_sy_common.h:212-220,224-227`）。
- `=2` の細分化 marks は router/mix 内の該当処理が通った場合だけ出ます。たとえば controller の有無で MLP norm と controller 計測の枝が異なり、細分化カテゴリに mark がない場合はそのカテゴリを要約から省きます（`engine/src/inkling2/sycl/ink_sy_runner.h:689-713`; `engine/src/inkling2/sycl/ink_sy_common.h:263-267`）。

## 実行時の詳細

環境変数は `sy_prof()` 内の関数ローカル `static SyProf` 初期化 lambda で読み、プロセス内で一度だけ保存します。最初の `sy_prof()` 呼び出しより後に環境を変更しても反映されません。Strata ソース内にこの名前の設定変更や子プロセスへの明示的な転送はありません（`engine/src/inkling2/sycl/ink_sy_common.h:212-223`; ソース全体の `INK_SY_PROF` 参照は同ファイルと `.github/ci/inkspeed/` の計測スクリプトのみ）。

各 `forward_batch()` の開始で `M==1` かつ `on` または `timing` の場合に step を開始します。`on` なら開始時に `wait()` し、phase mark ごとにも `wait()` して経過時間を加算します。`fine` のときは追加の `sy_prof_fmark()` が同じ wait/集計を行います。最後に head mark、submit 時刻の記録、通常の `wait()` を経て step 集計を終えます。したがって `1` は phase-group 間で同期し、`2` は該当する細分化 mark ごとにも同期します（`engine/src/inkling2/sycl/ink_sy_common.h:193,224-247`; `engine/src/inkling2/sycl/ink_sy_runner.h:937-940`）。

SYCL queue wait は `Q().wait_and_throw()` を呼びます。`INK_SY_PROF=1`/`2` はこれを通常より多くの計測地点で呼ぶため、queue の非同期エラーが追加 wait で表面化する可能性があります。profiler 固有の fallback やエラー文言は定義されていません（`engine/src/inkling2/sycl/ink_sy_common.h:193,231-238`）。

## ログと測定値

single-token step の累積が 64 件に達するごとに stderr に `[ink_sy_prof] steps=... host-submit=... ms total=... ms per step` を出します。`on` のときは続けて phase group ごとの平均値を `| mix=...` などとして付けます。`fine` のときは観測された `fx_*` カテゴリと平均 mark 数を出し、最後に 200 回の `wait()` から求めた `empty_wait=... us` を追記します（`engine/src/inkling2/sycl/ink_sy_common.h:248-275`）。ログに計測値を出すだけで、既定の性能値はありません。

リポジトリの SYCL 計測スクリプトは `INK_SY_PROF=1` と `=2` を bench プロセスに渡し、stderr から `[ink_sy_prof]` 行を拾います。これはスクリプトの利用例であり、追加の Strata runtime 実装ではありません（`.github/ci/inkspeed/b70_speed.sh:58-60`; `.github/ci/inkspeed/b70_mixsplit.sh:32-39,56-59`）。

## 根拠

- 読み取り、値の判定、cache、`INK_SY_TIMING` との関係: `engine/src/inkling2/sycl/ink_sy_common.h:212-223`
- step 条件、phase/fine 計測と同期: `engine/src/inkling2/sycl/ink_sy_common.h:193,224-247`; `engine/src/inkling2/sycl/ink_sy_runner.h:467-475,689-713,937-940`
- stderr 出力: `engine/src/inkling2/sycl/ink_sy_common.h:248-275`
- SYCL build の選択条件: `engine/CMakeLists.txt:23-32`; `engine/src/inkling2/CMakeLists.txt:246-248`; `engine/src/inkling2/sycl/CMakeLists.txt:7-9,43-45`
