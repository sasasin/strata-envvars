# `STRATA_POOL_STATIC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

native expert pool の gate/up 行処理と down 行処理で、各 worker に全 expert 共通の固定した行範囲を割り当てる要求フラグ。Strata は `generate.cpp` の pool 初期化時に読み取り、native layout のときだけ `ExpertPool::set_static_slices(true)` を呼ぶ。これは CPU pool の仕事の分け方を変える設定で、GPU の expert 選択や routing を変更する処理ではない。`STRATA_L3_PF` が有効な場合も同じ固定分割が必要とされるため、`STRATA_POOL_STATIC` が 0 でも静的分割が要求される（`engine/src/program/generate.cpp:10410-10424`）。

設定が実際に有効なのは `ExpertPool::run_split_multi_native` が mode 5/6 の二つの行処理 phase を実行する経路。通常の native expert pool の一括処理や非 native の分割処理にはこの設定による worker 固定割当は適用されない（`engine/src/kernels/cpu/pool.cpp:1559-1601`、`engine/include/strata/kernels/cpu/pool.hpp:254-259`）。

## 値と判定

Strata は起動時に `std::getenv` で値を取得し、`std::atoi(st_env) != 0` で判定する。文字列全体の検証やエラー処理はない。`atoi` が先頭の整数部分を変換するため、`1`、`01`、`-1`、`1tail` は非ゼロ、`0`、`0tail`、空文字、`true`、`tail` は 0 になる。先頭空白と符号は整数変換に従い、例えば `  +1tail` は非ゼロ。数値の範囲外を含め、変換エラーは Strata 側で検査しない。`STRATA_L3_PF` が有効な場合はこの値にかかわらず静的分割が要求される（`engine/src/program/generate.cpp:10414-10420`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_L3_PF` が無効 | 静的分割を要求しない | `atoi` の結果が非ゼロ（例: `1`, `-1`, `1tail`） | `atoi` の結果が 0（例: 空文字, `0`, `true`, `tail`） |
| `STRATA_L3_PF` が有効 | 静的分割を要求する | 同左 | 値が 0 でも `STRATA_L3_PF` により要求される |

この変数自体に CLI 引数や別設定による値の上書きはない。実際に有効になるかは次節の条件でさらに絞られる。`STRATA_L3_PF` の明示値は空でなければ `atoi` の非ゼロ判定、未設定または空文字なら GPU 容量・常駐 slot 数・pool worker 数による自動判定（13 GiB 以下、expert の 50% 超が非 resident、worker 8 個以上）となる（`engine/include/strata/core/low_vram_rules.hpp:118-125`）。

## 有効になる条件

- pool が `--no-pool` で無効化されていないこと。`--no-pool` では静的分割設定を呼ばない（`engine/src/program/generate.cpp:10401-10406,10420-10424`）。
- `expert_layout().native` が true であること。非 native layout ではこの設定ブロックは `set_static_slices` を呼ばない（`engine/src/program/generate.cpp:10420-10424`）。
- `ExpertPool` に NUMA split がなく、worker が 2 個以上あること。setter は `on && numa_n_ == 0 && n_ > 1` のときだけ設定を保持し、それ以外では false にする（`engine/include/strata/kernels/cpu/pool.hpp:258-259`）。
- 実際の行割当変更には `run_split_multi_native` が呼ばれること。同関数は固定分割時に worker 数ぶんの task を作り、mode 5/6 を `per_worker` で実行する。`STRATA_POOL_DEP` の一括 mode 7 は `!static_slices_` の場合だけ選ばれるので、固定分割が有効ならその経路を通らない（`engine/src/kernels/cpu/pool.cpp:1568-1597`）。

## 実行時の詳細

値は `generate.cpp` の pool 設定ブロックで読み、起動中に再読込しない。関数内 cache ではなく、起動時に一度取得した値から `pool` オブジェクトの設定を行うため、プロセス実行中に環境を変更しても反映されない（`engine/src/program/generate.cpp:10413-10424`）。子プロセスへの転送・上書きはこの読み取り箇所にはない。

静的分割が有効なら、gate/up phase では worker `j` が `n_ff * j / n` から `n_ff * (j+1) / n`、down phase では同様に `n_embd` を分割した行範囲を、各 expert について処理する。mode 5 の後で activation の量子化を行い、続けて mode 6 を処理するため二つの phase になる。静的分割が無効なときは task 数を `phase_tasks` または NUMA plan から求める（`engine/src/kernels/cpu/pool.cpp:1313-1326,1559-1601`）。

要求値が非ゼロでも NUMA split 中または worker が 1 個なら無効になり、startup log は `off (the NUMA split, or one thread)` と表示する。`--no-pool` または非 native layout の場合は setter とこの log 自体が呼ばれず、環境変数を無視する（`engine/src/program/generate.cpp:10420-10424`、`engine/include/strata/kernels/cpu/pool.hpp:258-259`）。

## ログと測定値

静的分割を要求し、pool が有効かつ native layout のとき、stderr に次の行を出す。setter が条件を満たせば `on`、NUMA split 中または worker が 1 個なら `off (the NUMA split, or one thread)` となる。要求されない場合や、`--no-pool`・非 native layout の場合はこの行を出さない（`engine/src/program/generate.cpp:10420-10424`）。

```text
strata generate: expert pool: static row slices on
strata generate: expert pool: static row slices off (the NUMA split, or one thread)
```

`docs/DETAILS.md:1245,1608` は `STRATA_POOL_STATIC=1` 単独を A/B 用の固定分割として説明し、単独設定では効果がなかった測定を記録している。該当する記録は 0.1.61 の一回ずつの測定で、chat prompt の decode が固定分割なし `64.71 / 64.65 / 64.64 tok/s`、固定分割あり `65.17 / 60.66 / 64.30 tok/s`。同資料は `STRATA_L3_PF` の測定と区別しており、この値を一般的な性能差とは扱えない。現行コード上の `STRATA_POOL_STATIC` は行分割の要求として機能し、実際の適用は前節の条件に従う。

## 根拠

- `engine/src/program/generate.cpp:10401-10424` — pool hook、両環境変数の読み取り、優先関係、設定条件、startup log。
- `engine/include/strata/core/low_vram_rules.hpp:118-125` — `STRATA_L3_PF` の自動判定条件。
- `engine/include/strata/kernels/cpu/pool.hpp:254-259` — 固定 row slice の意味と NUMA / worker 数による setter の制限。
- `engine/src/kernels/cpu/pool.cpp:1313-1326,1559-1601` — worker ごとの行範囲処理、native row phases、および `STRATA_POOL_DEP` 経路との条件。
- `docs/DETAILS.md:1245,1608` — 設計概要と条件付きの測定記録（コード上の現行動作を決める根拠ではない）。
