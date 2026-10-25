# `strata-plan --dense`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan`（トップレベル） |
| オプション | `--dense` |
| 別名 | なし |
| 値 | 10 進数で解釈するバイト数。省略時は `0` |

## 役割

計画計算に与える dense 重みのサイズをバイト単位で指定します。値は `Costs::dense_bytes` に設定され、VRAM pool の算出と計画の固定コストに使われます。`strata-plan` は CMake の `strata-plan` 実行ターゲットで、メモリ計画を表示する単体 CLI です（`CMakeLists.txt:330-331`、`src/plan/plan_main.cpp:1-5`）。

## 使い方

```sh
strata-plan --dense 1500000000
```

## 値と既定値

- 値は次の argv 要素から読み、`std::strtoull(..., nullptr, 10)` で符号なし整数へ変換します。単位はバイトです（`src/plan/plan_main.cpp:20-26,31-32`）。
- 既定値は `Costs::dense_bytes = 0` です（`include/strata/plan/plan.hpp:61-69`）。同じ `--dense` を複数回指定した場合は、ループ内で同じフィールドを更新するため最後の値が残ります（`src/plan/plan_main.cpp:18-43`）。
- 値が欠けると stderr に `<option> needs a value` を出し、終了コード `2` で終了します（`src/plan/plan_main.cpp:20-24`）。
- 数値変換の終端位置・`errno` は検査されません。したがって、不正な数値や数値の後ろに文字が続く値を明示的に拒否する validation はありません。`strtoull` の変換結果がそのまま使われます（`src/plan/plan_main.cpp:25`）。

## 実行時の動作

1. parser は値を `costs.dense_bytes` に保存します（`src/plan/plan_main.cpp:31-32`）。
2. pool はまず `free_vram > dense_bytes + embd_bytes` の場合に限り、その差 `free_vram - dense_bytes - embd_bytes` として計算されます。条件を満たさず差が `0` になる場合、`make_plan` には `vram_pool_bytes()` の固定値（`5,943,000,000` bytes）が渡されます（`src/plan/plan_main.cpp:59-66`、`include/strata/plan/plan.hpp:122-127`）。`--pool` を指定した場合も、この同じ pool 算出を通ります。
3. `make_plan` はさらに `dense_bytes` を `embd_bytes`、`mtp_bytes`、`workspace_bytes`、`state_bytes` と合わせて固定コストに含め、KV cache とともに pool 内に収まるか確認します（`include/strata/plan/plan.hpp:129-151`）。つまり `--dense` は pool 算出時に差し引かれ、続く固定コストの判定にも使われます。
4. 成功時は計画を stdout に出力します。出力の `expert arena (DRAM)` 行の値は `dense_bytes + embd_bytes` です（`include/strata/plan/plan.hpp:134-145,154-165`）。

## 適用条件と副作用

この値は `strata-plan` 内の算術計画にのみ渡されます。調査した CLI 実装では、`--dense` の値をファイルや GPU に読み込む処理はありません（`src/plan/plan_main.cpp:13-73`）。単体 planner は GPU なしでテスト可能とする説明があります（`src/plan/plan_main.cpp:1-5`）。

`--embd` は同じ pool 算出で dense 値と合算され、`--pool` は元の `free_vram` を置き換えます（`src/plan/plan_main.cpp:29-43,59-63`）。`--max-context` などとの組み合わせで固定コストと KV が pool を超えた場合、計画は失敗します（`include/strata/plan/plan.hpp:134-143`）。

## 出力とエラー

- 計画が成立すれば `memory plan` と各コストを stdout に出して終了コード `0` です（`src/plan/plan_main.cpp:64-68`、`include/strata/plan/plan.hpp:154-165`）。
- pool 内に要求された最大 context と固定コストが収まらない場合、stderr に `strata-plan: ... reduce --max-context` を出して終了コード `1` です（`include/strata/plan/plan.hpp:138-143`、`src/plan/plan_main.cpp:69-72`）。
- 固定コストを差し引いた後、expert cache slot が 1 つも残らない場合も `DoesNotClose` となり、stderr と終了コード `1` の経路を通ります（`include/strata/plan/plan.hpp:144-150`、`src/plan/plan_main.cpp:69-72`）。

## 根拠と調査範囲

parser と使用箇所は `src/plan/plan_main.cpp:13-73`、コストの既定値・計画計算・出力は `include/strata/plan/plan.hpp:61-69,129-165`、実行ターゲットは `CMakeLists.txt:330-331` を確認しました。索引のコマンド階層およびリンクは [`docs/cli/README.md`](../../README.md) の `strata-plan` 節に従っています。

同一 revision の `strata-plan --help` 実行や Release 配布物は確認していません。help 表示は parser 実装内の文字列を参照しました（`src/plan/plan_main.cpp:44-50`）。
