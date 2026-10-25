# `strata-plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。Strata の作業ツリーは `main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan`（サブコマンドなし） |
| 主な実装 | `src/plan/plan_main.cpp` |
| 用途 | 固定のモデル geometry とメモリ費用から VRAM 計画を表示する診断用 CLI |

## 役割

指定した最大 context と VRAM・費用の値を使い、KV cache、固定 state、expert cache に割り当てるメモリ計画を計算して標準出力に表示します。計画が VRAM pool に収まらない場合は理由を標準エラーに出して失敗します。モデルファイルを読み込んだり GPU を検出したりせず、`Geometry{}` の固定値で計算する単体ツールです（`src/plan/plan_main.cpp:14-16,58,65-67`、`include/strata/plan/plan.hpp:22-59`）。

CMake では `strata-plan` を `strata_plan` header-only target にリンクして生成します。この target 定義には GPU backend 条件がなく、GPU を使わない計画計算として配置されています（`CMakeLists.txt:323-331`）。`docs/cli/000_cli_tools.md` でも、Terminal の製品コマンドではなく CMake 生成の診断・開発用プログラムとして分類されています。

## 使い方

```sh
# 既定の context と VRAM 値で計画を表示
strata-plan

# context と利用可能 VRAM を bytes で指定
strata-plan --max-context 32768 --vram 12000000000

# CLI の使用法を表示
strata-plan --help
```

引数の形式は `strata-plan [--max-context N] [--vram BYTES] [--dense B] [--embd B] [--workspace B] [--state B] [--pool B]` です。`--help` は `-h` も受け付けます（`src/plan/plan_main.cpp:44-50`）。

## 実行モード

この CLI にサブコマンドや対話モードはありません。通常実行は計画を計算して表示するだけです。`--help` / `-h` は usage と `--state` の既定に関する説明を表示し、計画計算をせず終了します（`src/plan/plan_main.cpp:44-50,64-68`）。

## 主な動作

- 既定値は context `20480`、`--vram` 用の値 `12000000000` bytes です。`Costs` の dense、embedding、workspace は初期値 `0` bytes です（`src/plan/plan_main.cpp:14-16`、`include/strata/plan/plan.hpp:61-69`）。
- `--state` を省略すると、固定 geometry から recurrent state の費用を計算します。明示した場合はその値が使われます。state は計画上、cache に回せず eviction できない固定費用として扱われます（`src/plan/plan_main.cpp:17,37-39,56-58`、`include/strata/plan/plan.hpp:71-88,135-145`）。
- `--vram` は free VRAM 相当の bytes、`--dense`、`--embd`、`--workspace`、`--state` はそれぞれ bytes、`--max-context` は token 数として整数を読み込みます（`src/plan/plan_main.cpp:20-39`）。
- `--pool` は名前に反して専用の pool 値へ直接代入する実装ではなく、`--vram` と同じ `free_vram` に値を設定します。その後 dense と embedding の費用を差し引いて pool を求めます。したがって dense/embedding を指定した場合、入力値からそれらも引かれます（`src/plan/plan_main.cpp:29-43,59-66`）。
- pool は free VRAM 値が dense と embedding の合計を超える場合、その差です。超えない場合は `0` となり、計画関数には既定 pool `5943000000` bytes が渡されます（`src/plan/plan_main.cpp:59-66`、`include/strata/plan/plan.hpp:122-130`）。この fallback は pool がゼロのときに適用されるため、`--vram` の値が小さい場合にも既定 pool で計画され得ます。
- 計算では KV + indexer keys と固定費用を pool から引き、残りを expert cache に配分します。要求が収まらない場合や expert cache slot が 1 個も残らない場合は計画を拒否します（`include/strata/plan/plan.hpp:90-100,129-151`）。
- 成功時は `to_string` の計画内訳（context、KV、recurrent state、expert cache、pool、DRAM expert arena）を標準出力へ表示します（`include/strata/plan/plan.hpp:154-165`）。この CLI は計画を表示するもので、GPU memory allocation、model loading、server 起動、ファイル書き込みは行いません（`src/plan/plan_main.cpp:64-68`）。

## 注意点

各値は `std::strtoull(..., 10)` で変換されますが、変換後の文字列全体や範囲を検証する処理はありません。数値として不正な値や単位付き値がどう解釈されるかに依存しないよう、10 進整数のみを指定してください（`src/plan/plan_main.cpp:20-25`）。

この計画は `Geometry{}` の固定 geometry に基づき、実機で測った空き VRAM や選択したモデルの manifest から自動的に値を取り込むものではありません。`--vram` と費用値は利用者が与える数値、またはソースの既定値です（`src/plan/plan_main.cpp:14-16,58,65`、`include/strata/plan/plan.hpp:22-59,61-69`）。

## 出力とエラー

- `--help` / `-h` は usage を標準出力へ表示し、終了コード `0` です（`src/plan/plan_main.cpp:44-50`）。
- 未知の引数は `unknown argument: ...` を標準エラーへ出し、終了コード `2` です。値が必要なオプションの後に値がない場合は `<option> needs a value` を標準エラーへ出し、終了コード `2` です（`src/plan/plan_main.cpp:20-24,51-53`）。
- 計画が成立しない場合は `strata-plan: ...` を標準エラーへ出し、終了コード `1` です。成功時の計画は標準出力、終了コード `0` です（`src/plan/plan_main.cpp:64-72`、`include/strata/plan/plan.hpp:138-149`）。

## 関連文書

- [CLI 索引の `strata-plan` 節](../../README.md#strata-plan-srcplanplan_maincpp)
- [`--dense`](--dense.md)、[`--embd`](--embd.md)、[`--help`](--help.md)、[`--max-context`](--max-context.md)、[`--pool`](--pool.md)、[`--state`](--state.md)、[`--vram`](--vram.md)、[`--workspace`](--workspace.md)

## 根拠

- `src/plan/plan_main.cpp:13-72` — 既定値、引数処理、state の既定計算、pool 算出、計画表示、失敗時の出力と終了コード。
- `include/strata/plan/plan.hpp:22-59,61-88` — 固定 geometry、費用の既定値、state 費用の導出。
- `include/strata/plan/plan.hpp:90-100,115-165` — KV 費用、pool 既定値、成立条件、計画内訳の生成。
- `CMakeLists.txt:323-331` — GPU backend 条件外の `strata-plan` target 定義。
- `docs/cli/README.md:1404-1415`、`docs/cli/000_cli_tools.md:25` — 索引上の階層・オプション一覧と診断用ツールとしての分類。
