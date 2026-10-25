# `--state`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan` |
| オプション | `--state` |
| 別名 | なし |
| 値 | 10 進整数のバイト数 `B` |

## 役割

メモリ計画に固定コストとして加える recurrent state のバイト数を指定する。これは expert cache の退避可能な容量ではなく、VRAM の固定コストとして KV 等とともに収支計算される。省略時は `strata-plan` 内蔵の既定 geometry から GDN recurrence と convolution history のサイズを算出するため、0 にはならない（`src/plan/plan_main.cpp:56-58`、`include/strata/plan/plan.hpp:71-88,129-145`）。

## 使い方

```sh
strata-plan --state 117669888
```

値はバイト単位。既定の VRAM pool など他の入力はこの例では既定値を使う。

## 値と既定値

- `--state` の直後の引数を `uint64_t` の state byte 数として読み込む。値を省略すると stderr に `--state needs a value` を出して終了コード 2（`src/plan/plan_main.cpp:20-24,37-39`）。
- 数値変換は `std::strtoull(..., 10)`。終端位置や `errno` を検査する validation はなく、厳密な整数形式・上限の検査は行わない。変換できない文字列は 0 となり、数値の後ろに残る文字も拒否されない。負数や範囲外値も CLI では明示的に拒否されない（`src/plan/plan_main.cpp:20-26,37-39`）。
- 複数回指定した場合は各回の値を同じフィールドへ代入するため、最後の指定値が使われる（`src/plan/plan_main.cpp:18-39`）。明示的な `--state 0` は有効で、geometry 既定値への置換を抑止する。
- 省略時は `Geometry{}` の `state_bytes()` が計算する。既定 geometry は 36 GDN 層、各層の recurrence 3,145,728 B と conv history 122,880 B から合計 117,669,888 B（約 117.7 MB）となる（`include/strata/plan/plan.hpp:23-29,49-58,77-88`）。

## 実行時の動作

パーサーが受け取った値は `costs.state_bytes` に入り、未指定時の計算値とともに `make_plan()` に渡される。`make_plan()` は `dense + embd + mtp + workspace + state` を固定コストに加算し、KV コストと合わせて pool 内に収まるか判定する。state を大きくすると expert cache に残る容量・slot 数が減り、固定コストと KV の合計が pool を超える場合は計画が失敗する（`src/plan/plan_main.cpp:37-39,56-66`、`include/strata/plan/plan.hpp:129-149`）。

この CLI が表示する state は一つの計画に与える単一の byte 数であり、値を sequence 数に応じて乗算する処理はない。`--vram`、`--dense`、`--embd`、`--workspace` も pool または固定コストの計算に関わるため、`--state` の影響はそれらの値にも依存する（`src/plan/plan_main.cpp:14-16,27-36,59-66`）。

## 適用条件と副作用

`strata-plan` はメモリ計画を計算して表示する単体 CLI であり、このオプションの処理は数値計算のみ。`--state` 自体によるファイル書き込み、ネットワークアクセス、GPU 上の割り当ては確認できない（`src/plan/plan_main.cpp:1-5,64-73`）。

ヘルプ文字列は省略時の state を GDN recurrence + conv history と説明し、117.7 MB を挙げる（`src/plan/plan_main.cpp:44-50`）。既定値の実装式もこの二項のみで、`Costs::state_bytes` のコメントには replay log も記載されているが（`include/strata/plan/plan.hpp:68,71-88`）、計算関数には replay log の加算はない。

## 出力とエラー

- 計画成立時は `to_string()` の結果を stdout に出し、終了コード 0。state の行には recurrent state の GB 表示が含まれる（`src/plan/plan_main.cpp:64-68`、`include/strata/plan/plan.hpp:154-165`）。
- KV と固定コストが pool を超える場合は stderr に `strata-plan: ...` と必要量・pool、および `reduce --max-context` の案内を出し、終了コード 1。`--state` が原因となる場合もこの経路を通る（`include/strata/plan/plan.hpp:138-143`、`src/plan/plan_main.cpp:69-72`）。
- 固定費控除後の expert cache が 1 slot 未満の場合も `DoesNotClose` となり、stderr と終了コード 1（`include/strata/plan/plan.hpp:144-149`、`src/plan/plan_main.cpp:69-72`）。

## 根拠

- `src/plan/plan_main.cpp:13-26,37-58` — CLI の引数処理、10 進変換、値省略時のエラー、既定値。
- `src/plan/plan_main.cpp:59-73` — pool の算出、計画の実行、stdout/stderr と終了コード。
- `include/strata/plan/plan.hpp:23-29,49-58,62-88` — 既定 geometry、Costs、state byte 算出式。
- `include/strata/plan/plan.hpp:129-149,154-165` — 固定コストとの相互作用、失敗条件、表示。
- `CMakeLists.txt:326-331` — `strata-plan` executable target とソース。
- 索引上のコマンド階層とリンク: `docs/cli/README.md:1404-1415`。
