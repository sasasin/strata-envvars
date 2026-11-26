# `STRATA_FILE_TIER_IDLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

file-tier の全 expert が GPU cache に載っている間、Linux の既定 I/O prefetch と、明示的に要求されていない routing-aware look-ahead を休止する policy を有効にする。未設定では有効、`0` では policy 全体を無効にする。値を読むのは `engine/src/program/generate.cpp` の `generate` 処理で、GPU cache の residency 判定と `refresh_file_tier` が実際の切替を行う（`engine/src/program/generate.cpp:10251-10258,10275-10286,10341-10379`）。

## 値と判定

`std::getenv` の戻り値を `std::atoi(v) != 0` で判定する。未設定 (`nullptr`) は有効、設定された値は `atoi` の結果が非ゼロなら有効。従って空文字、`0`、`0anything`、`true`、数字で始まらない文字列は無効になり、`1`、`-1`、`1anything` は有効になる。先頭の空白と符号は `atoi` の変換規則に従い、数字の後ろは検査しない。数値として表現範囲を超える入力は `atoi` の仕様上、結果を規定できない（`engine/src/program/generate.cpp:10258`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `generate` 内の全経路 | 有効 | `1`, `-1`, `1junk` | 空文字, `0`, `0anything`, `true` |

この変数を上書きする CLI 引数はなく、コード内でもこの変数名を読む箇所は1箇所だけ。`STRATA_IO_PREFETCH` と `STRATA_LOOKAHEAD` は休止対象を個別に明示要求できるが、`STRATA_FILE_TIER_IDLE` 自体の判定を上書きしない（`engine/src/program/generate.cpp:10258-10260,10288-10290,10343-10344`）。

## 有効になる条件

- file-tier 用 `FileExpertSource` (`srcp == &src`) を使う経路で policy が動く。通常は `--mmap-experts`、または RAM 不足時に mmap 経路へ fallback した場合が該当する。resident arena 経路 (`srcp != &src`) では適用されない（`engine/src/program/generate.cpp:8621-8647,8740-8747,10275-10276,10343-10345`）。
- GPU cache の全 slot が全 layer の全 expert を保持しているときだけ休止する。判定は各 layer について primary の stage cache（単一 GPU では `xcache`）を選び、各 `(layer, expert)` の slot が `kNotResident` でなく、かつ live slot 数未満かを数え、合計を `g.n_layers * g.n_expert` と比較する（`engine/src/program/generate.cpp:10262-10278`）。
- I/O prefetch の休止対象は `STRATA_IO_PREFETCH` 未指定または空文字のときに選ばれた Linux 既定値のみ。明示的な `STRATA_IO_PREFETCH` が非ゼロなら、`io_pf_by_default` は false となり、この policy は prefetch を止めない（`engine/src/program/generate.cpp:8693-8704,10278-10280`）。Linux 以外では `FileExpertSource::linux_io_defaults()` が false を返すため、この Linux 既定 prefetch は選ばれない（`engine/include/strata/core/expert_source.hpp:1081-1094`）。
- routing-aware look-ahead は `STRATA_LOOKAHEAD` が未設定または `atoi` で非ゼロで、file source が `warms()` を返す場合に開始対象になる。全 expert が GPU にある状態で開始済みでも、`STRATA_LOOKAHEAD` または `STRATA_IO_PREFETCH` の非空・非ゼロ値で要求されている場合、`STRATA_FS_SLOTS` の `atoi` が正で `STRATA_FS_AHEAD` が未設定または `atoi` で非ゼロの場合、もしくは `STRATA_LOOKAHEAD_STATS` の `atoi` が非ゼロの場合は切り離さない（`engine/src/program/generate.cpp:10288-10303,10328-10338,10359-10360`）。

## 実行時の詳細

対象値は `generate` の当該実行に入ったとき一度読み、ローカルの `const bool` に保存する。`static` cache や各リクエストでの再読込はないため、実行中に環境値を変更しても反映されない（`engine/src/program/generate.cpp:10258`）。

初期化時に file-tier 経路かつ policy 有効なら GPU residency を数える。全 expert が GPU にあれば `io_pf_by_default` が true の場合に限って `src.set_io_prefetch(false, 0)` を呼ぶ。また、既定動作として開始した look-ahead は、明示要求や Foresight・計測条件がなければ `drive.d.lookahead` から外す（`engine/src/program/generate.cpp:10275-10286,10302-10303,10328-10330`）。

serve の `GEN` / `GENI` リクエストを処理する直前に `refresh_file_tier()` が呼ばれ、同じ residency 判定で状態変化を確認する。全 expert が GPU に揃ったときは既定 prefetch を停止し、既定 look-ahead を切り離す。GPU cache から expert が欠けた状態になると、停止していた prefetch を再開し、look-ahead を再接続する。I/O prefetch 再開時の `STRATA_IO_PF_THREADS` の既定は `0`（setter 側では自動値として扱う）である。切替はリクエスト境界で行われ、リクエスト中の各 adaptive swap の直後にこの lambda が呼ばれる箇所はない（`engine/src/program/generate.cpp:10341-10377,18808-18812`）。

## ログと測定値

初期状態で全 expert が GPU cache にあり、既定 I/O prefetch を停止した場合は stderr に `strata generate: every expert is in the GPU caches (%lld of %lld): the file tier's Linux defaults (io prefetch, the decode gate) are off, the decode reads nothing from it (STRATA_IO_PREFETCH=1 keeps them)` を出す（`engine/src/program/generate.cpp:10278-10285`）。serve 中の切替では実際に切替が発生した場合に限り、stderr に `strata serve: every expert is in the GPU caches again (%lld of %lld): the file tier's Linux defaults are off` または `strata serve: %lld of %lld experts are in the GPU caches now: the file tier's Linux defaults are on again` を出す（`engine/src/program/generate.cpp:10351-10362,10363-10377`）。この変数固有の警告、終了、エラー経路はない。性能測定値は記載しない。

## 根拠

- `engine/src/program/generate.cpp:10251-10260` — policy の範囲、対象値の読み取り、状態変数。
- `engine/src/program/generate.cpp:10262-10286` — GPU residency と初期休止、ログ。
- `engine/src/program/generate.cpp:10288-10339` — look-ahead の有効条件と明示要求。
- `engine/src/program/generate.cpp:10341-10379,18808-18812` — residency 変化時の再開・休止と serve 呼び出し箇所。
- `engine/src/program/generate.cpp:8621-8647,8693-8704,8740-8747` — mmap file-tier 経路と Linux 既定 prefetch。
- `engine/include/strata/core/expert_source.hpp:1081-1094` — Linux 専用既定値の条件。
