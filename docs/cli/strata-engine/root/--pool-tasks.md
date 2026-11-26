# `strata generate --pool-tasks`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--pool-tasks` |
| 別名 | なし |
| 値 | 10進整数 `N`、`0..4096` |

## 役割

バッチ化された CPU expert 計算の GU（gate/up）と Down 各フェーズで使う行タスク数を指定します。対象はネイティブ pack の CPU expert pool 経路です。値は各フェーズに対するタスク数の目標であり、CPU worker 数そのものは変更しません（`engine/src/program/generate.cpp:857, 9001-9008`、`engine/src/kernels/cpu/pool.cpp:1559-1597`）。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --pool-tasks 192
```

この例では、pack の処理におけるバッチ化 CPU expert の GU/Down フェーズに、最大 192 個を目安として行タスクを割り当てます。性能が向上するとは限らず、ソースコメントも同じ worker 数で `0` と比較するよう案内しています（`engine/src/program/generate.cpp:1208-1215, 1447-1448`）。

## 値と既定値

- `N` は整数 `0..4096`。`0` は自動設定で、各フェーズを参加スレッドあたり 3 タスクにします（`engine/src/program/generate.cpp:3940-3945`、`engine/src/kernels/cpu/pool.cpp:1516-1518`）。
- `1..4096` は明示値です。通常のバッチフェーズでは各フェーズの行数を上限として `min(行数, N)` がタスク数になります（`engine/src/kernels/cpu/pool.cpp:1516-1518`）。
- NUMA 分割が有効なネイティブ行フェーズでは、明示値を各 NUMA slice に共有し、slice ごとの要求値を `max(1, N / 2)` として、その slice の行数で上限を取ります。自動値は slice の参加スレッドあたり 3 です（`engine/src/kernels/cpu/pool.cpp:1176-1189`）。
- 同じオプションを複数回指定すると、引数を順に読む parser が `o.pool_tasks` を都度代入するため、最後の値が残ります（`engine/src/program/generate.cpp:3842-3849, 3937-3945`）。

## 実行時の動作

parser は `strtol` で値全体を読み、数値がない、末尾に未消費文字がある、または範囲外の場合は拒否します。受理した値は `Options::pool_tasks` に入り、必要に応じて pool affinity の測定にも渡され、`ExpertPool` の `tasks` 引数になります。起動時には stderr にフェーズあたりのタスク数（自動時は参加スレッド数から算出）と参加スレッド数を表示します（`engine/src/program/generate.cpp:3937-3945, 9001-9008`）。

通常の native multi-expert 処理では GU と Down の行数を別々に設定し、それぞれ `phase_tasks` でタスク数を決めて pool に実行させます（`engine/src/kernels/cpu/pool.cpp:1559-1601`）。`--pool-workers` で worker 数が変わると、自動値 `0` のタスク数も参加スレッド数に応じて変わります。`--no-host-worker` も参加スレッド数から host thread を除くため、自動値に影響します（`engine/src/program/generate.cpp:1440-1448, 9001-9008`）。

## 適用条件と副作用

効果があるのは CPU expert pool のバッチ行フェーズです。`--no-pool` を指定すると生成側の pool callback が無効になり、CPU expert pool を使う経路が抑止されるため、この値はその経路のタスク配分を変えません（`engine/src/program/generate.cpp:10467-10484`）。起動時の pool 設定表示自体は `--no-pool` の分岐より前に行われます（`engine/src/program/generate.cpp:9001-9008`）。

このオプションは pool を作るときのタスク目標を渡します。ファイルやネットワークへの副作用はコード上確認できません。タスク数を増やした場合の実性能はソースから確定できず、測定も本調査では行っていません。

## 出力とエラー

- 値を省略すると `--pool-tasks needs a value` を stderr に出し、終了コード `2` で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- 整数として解釈できない値、末尾に余分な文字がある値、または `0..4096` の範囲外の値は、`strata generate: --pool-tasks expects an integer in 0..4096 (0 = automatic)` を stderr に出し、parser から `2` を返します（`engine/src/program/generate.cpp:3937-3945`）。
- 引数が受理されると pool 起動時に `strata generate: CPU pool tasks/phase: ...` が stderr に表示されます（`engine/src/program/generate.cpp:9003-9008`）。

## 根拠

- `engine/src/program/generate.cpp:857, 1447-1448` — 値の説明と既定値を含む help 文言。
- `engine/src/program/generate.cpp:3842-3849, 3937-3945` — parser、値の取得・検証、エラーと代入。
- `engine/src/program/generate.cpp:9001-9008` — pool への値の受け渡しと起動時表示。
- `engine/src/kernels/cpu/pool.hpp:200-203` — `ExpertPool` の task 引数と上限定数。
- `engine/src/kernels/cpu/pool.cpp:1176-1189, 1516-1518, 1559-1601` — NUMA/通常経路のタスク数計算と native GU/Down フェーズでの使用。
- `engine/src/program/generate.cpp:10467-10484` — `--no-pool` 時に pool callback を無効にする箇所。
