# `--pool-workers`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（engine の root parser） |
| オプション | `--pool-workers` |
| 別名 | なし |
| 値 | `N`。別引数で渡す整数相当の文字列 |

## 役割

CPU expert pool が起動する worker 数を指定します。これは GPU 数や `--pool-tasks` の task 数ではなく、expert 処理を担当する CPU worker thread 数です。通常は未指定（または `0`）にして、実行環境の CPU topology に基づく自動計画を使います。

## 使い方

```sh
strata generate --pack /path/to/pack --tokens "1,2,3" --pool-workers 6
```

`strata generate` の必須入力は pack と token input です。上のパスは利用環境に合わせて置き換えてください。

## 値と既定値

- `--pool-workers` の直後の引数を `std::atoi` で `int` に変換します。引数がなければ parser の `next()` が `--pool-workers needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420,2510`）。
- 変換後の負数は共通 resource parameter validation で拒否され、`strata generate: invalid sampling or resource parameter` を stderr に出して終了コード 2 になります。`0` は明示しても自動計画を選びます（`src/program/generate.cpp:3352-3359`）。
- `atoi` のため、厳密な整数文法検査はありません。例えば数字で始まらない値は `0` として扱われ、数字の後ろに余分な文字があっても数値部分が使われます。厳密な入力として整数だけを渡してください。
- 同じオプションを複数回指定した場合、parser は各指定を順に代入し、最後の値が残ります（`src/program/generate.cpp:2416-2421,2510`）。`--pool-workers=6` のような等号形式は parser の分岐にないため未知引数として拒否されます（`src/program/generate.cpp:2787-2792`）。
- 自動値は一律の「全物理コア数−1」ではありません。CPU topology、物理 core 数、論理 CPU 数、container CPU quota、socket、hybrid CPU、上限などから計算します。通常の計画では host thread 用に1 coreを除き、worker 数は最大32です。詳細な条件は `include/strata/kernels/cpu/pool_plan.hpp:26-32,76-122` にあります。

## 実行時の動作

値は `Options::pool_workers` に保持され、pool を作るときに `ExpertPool` へ渡されます（`src/program/generate.cpp:518,5971-5974`）。値が正なら指定数が自動計画より優先され、CPU に対して多すぎる場合も数を補正せず、その数の worker を起動します。pool 実装は推奨値を超えた場合に stderr へ一度だけ警告を出しますが、設定数の実行を続けます（`include/strata/kernels/cpu/pool_plan.hpp:125-146`; `src/kernels/cpu/pool.cpp:912-920,923-935`）。

未指定または `0` の場合、基本計画は CPU の物理構成などに応じて選びます。大きな CPU では他の engine thread 用に追加の core を空ける場合があり、container quota や32 worker 上限でも制限されます。hybrid CPU で `--pool-affinity auto` または `p-cores` を選んでいる場合は、既定 worker 数が P-core 数−1 になります（`src/program/generate.cpp:1026-1029`; `src/kernels/cpu/pool.cpp:801-818`; `include/strata/kernels/cpu/pool_plan.hpp:90-121`）。

`--pool-cores` と併用した場合、worker 数を明示しなければ CPU リストの長さが既定数になります。両方を指定すれば `--pool-workers` の数が優先されます。リストより worker 数が多いと、リストに対応する worker だけが pin され、残りは pin されず OS に配置されます（`src/kernels/cpu/pool.cpp:763-779,801-817,923-935,938-945`; `include/strata/kernels/cpu/pool.hpp:116-121`）。

worker 数は host thread を pool の処理に参加させるかどうかとは別です。`--no-host-worker` が pool 設定で host の参加を切り替え、既定では参加します。`--pool-tasks` が `0` の場合、pool と参加する host thread の合計数から phase ごとの task 数を自動設定します（`src/program/generate.cpp:1023-1031,5973-5978`）。

## 適用条件と副作用

- pool の初期化時に worker thread を生成し、既定では各 worker を検出した logical processor に pin します。thread の生成・配置が起動時に行われるため、設定は実行中に動的更新されません（`src/kernels/cpu/pool.cpp:923-935`）。
- 明示した数が CPU topology の計画値を超えると警告が出ますが、実行数は維持されます。`--pool-cores` の指定数を超える場合は一部 worker が unpinned で動きます（`include/strata/kernels/cpu/pool_plan.hpp:125-146`; `src/kernels/cpu/pool.cpp:912-919,938-945`）。
- `--no-pool` を指定すると expert pool の処理 callback は使われず、起動ログに `UNUSED: --no-pool` と表示されます。ただし parser 後の pool 初期化自体は `--no-pool` の分岐より前に行われるため、`--pool-workers` に従う pool thread の生成・CPU 配置は発生します（`src/program/generate.cpp:5971-5974,6928-6936`）。
- 初期化後、stderr に worker 数、参加 thread 数、worker の logical processor 配置などが出力されます。自動計画が何に制限されたかも条件により表示されます（`src/program/generate.cpp:5975-5980,5985-6005`）。

## 出力とエラー

- 負数: `strata generate: invalid sampling or resource parameter`、終了コード 2（`src/program/generate.cpp:3352-3359`）。
- 値の省略: `--pool-workers needs a value`、終了コード 2（`src/program/generate.cpp:2418-2420`）。
- `--pool-workers=...` など parser が認識しない形式: `unknown argument: ...` と usage を stderr に出し、終了コード 2（`src/program/generate.cpp:2787-2792`）。
- 計画値を超える明示数: pool 初期化時に警告を stderr に出しますが、拒否や自動補正はしません（`src/kernels/cpu/pool.cpp:912-920`; `include/strata/kernels/cpu/pool_plan.hpp:125-146`）。

## 根拠

- parser、値変換、missing-value と unknown-argument 経路: `src/program/generate.cpp:2416-2421,2510,2787-2792`
- 負数 validation: `src/program/generate.cpp:3352-3359`
- pool への引き渡し、worker 数と起動時表示: `src/program/generate.cpp:5971-6005,6928-6936`
- topology に基づく既定数、上限、明示値への警告: `include/strata/kernels/cpu/pool_plan.hpp:26-32,76-146`
- 指定値優先、`--pool-cores` との関係、thread 生成・pinning: `src/kernels/cpu/pool.cpp:743-779,801-818,912-945`
- `--pool-cores` の count 関係: `include/strata/kernels/cpu/pool.hpp:116-121`

この文書は索引の `strata-engine/root` scope を対象としています。Qwen3.6 専用 parser にも同名 option がありますが、別 scope として索引にある [`strata-engine/qwen36/--pool-workers.md`](../qwen36/--pool-workers.md) の対象であり、ここではその動作を混在させていません。
