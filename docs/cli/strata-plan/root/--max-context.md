# `--max-context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan`（CMake 生成の単体 CLI） |
| オプション | `--max-context` |
| 別名 | なし |
| 値 | `N`。10進整数として `uint64_t` に変換される。明示的な範囲検証はない |

## 役割

メモリ計画に使う最大コンテキスト長（トークン数）を指定します。planner はこの値から KV と indexer key の容量を算出し、固定費用と合わせて VRAM pool に収まるか判定します。`strata-plan` は GPU を測定せず、既定のモデル geometry と指定または既定の容量値で計画を表示する独立した CLI です（`src/plan/plan_main.cpp:1-5,13-16,65-68`）。

## 使い方

ビルド済みの `strata-plan` を使い、たとえば次のように指定します。

```sh
strata-plan --max-context 32768
```

使用形式は `strata-plan [--max-context N] ...` です。CMake は `src/plan/plan_main.cpp` から `strata-plan` 実行ファイルを生成します（`CMakeLists.txt:330-331`、`src/plan/plan_main.cpp:45-49`）。

## 値と既定値

- 省略時は `20480` です（`src/plan/plan_main.cpp:14`）。
- 値は `std::strtoull(..., nullptr, 10)` で変換され、変換終了位置も `errno` も検査されません（`src/plan/plan_main.cpp:20-26`）。したがって、整数の全体が有効か、値が正か、planner が扱える範囲かを CLI は検証しません。数字以外で始まる値は変換結果が 0 になり、数字の後ろに余分な文字がある場合もその部分は検査されません。符号・桁あふれを含む入力を厳密に拒否する parser ではありません。
- 同じオプションを複数回指定すると、ループ中に同じ `ctx` が上書きされるため最後の値が使われます（`src/plan/plan_main.cpp:18-28`）。
- 値を省略すると stderr に `<option> needs a value` を出し、終了コード 2 で終了します（`src/plan/plan_main.cpp:20-24`）。

## 実行時の動作

CLI は受け取った値を `make_plan(ctx, ...)` に渡します（`src/plan/plan_main.cpp:64-66`）。planner は `kv_bytes_per_token(geometry) * max_context` を KV・indexer key の費用として計算し（`include/strata/plan/plan.hpp:90-100,129-135`）、固定費用と合算します。必要量が VRAM pool を超える場合、または expert cache に1 slotも残らない場合は計画を拒否します（`include/strata/plan/plan.hpp:138-150`）。成功時の表示には指定（または既定）の `--max-context` と計算した容量が含まれます（`include/strata/plan/plan.hpp:154-165`）。

既定の pool 入力は nominal 12,000,000,000 bytes です。`--vram` または `--pool` を指定すると、その値を free VRAM として使い、そこから `--dense` と `--embd` の値を差し引いて pool を作ります。`free_vram` が `dense_bytes + embd_bytes` 以下で pool が 0 になる場合は `vram_pool_bytes()` の 5,943,000,000 bytes を使います。`--dense`、`--embd`、`--workspace`、`--state` は固定費用にも影響するため、同時指定時にはコンテキスト容量とともに可否を左右します（`src/plan/plan_main.cpp:15-16,29-43,56-66`、`include/strata/plan/plan.hpp:62-69,122-150`）。

## 適用条件と副作用

`--max-context` は `strata-plan` の計算にだけ使われ、エンジン起動や GPU 配置を行いません（`src/plan/plan_main.cpp:1-5,64-68`）。この CLI は既定 geometry を使用します（`src/plan/plan_main.cpp:65-66`）。

`--state` を省略すると、CLI は既定 geometry から GDN recurrence と convolution history の state bytes を導出します。`--state 0` を明示すると自動導出を抑止して 0 bytes を使います。そのため同じ `--max-context` でも state の指定によって計画結果や成立可否が変わります（`src/plan/plan_main.cpp:17,37-40,56-58`、`include/strata/plan/plan.hpp:71-88`）。

## 出力とエラー

- 成功時は計画を stdout に出し、終了コード 0 を返します（`src/plan/plan_main.cpp:64-68`）。
- 指定値などにより計画が成立しない場合は `strata-plan: <理由>` を stderr に出し、終了コード 1 を返します。理由には pool 超過時の必要 byte 数と「reduce --max-context」、または cache slot 不足が含まれます（`src/plan/plan_main.cpp:69-72`、`include/strata/plan/plan.hpp:138-150`）。
- 未知の引数は `unknown argument: ...` を stderr に出し、終了コード 2 を返します（`src/plan/plan_main.cpp:51-54`）。
- `--help` / `-h` は使用形式を stdout に出し、終了コード 0 で終了します（`src/plan/plan_main.cpp:44-50`）。

## 根拠

- `src/plan/plan_main.cpp:13-28` — 既定値、値の取り込み、変換方法。
- `src/plan/plan_main.cpp:29-66` — 関連する VRAM/cost オプション、state の既定化、planner 呼び出し。
- `src/plan/plan_main.cpp:44-54,64-72` — help、未知引数、成功・失敗時の出力と終了コード。
- `include/strata/plan/plan.hpp:62-100,115-150,154-165` — cost/state/KV の算定、成立条件、表示形式。
- `CMakeLists.txt:330-331` — `strata-plan` の build target。
- 索引上のスコープ: `docs/cli/README.md:1404-1415` — CMake 生成の単体 CLI と `strata-plan` のオプション一覧。
