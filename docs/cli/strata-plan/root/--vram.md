# `strata-plan --vram`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan`（ルート） |
| オプション | `--vram` |
| 別名 | なし |
| 値 | 10 進整数で指定するバイト数。コード上の変数名は `free_vram` |

## 役割

メモリ計画に使う VRAM 容量の入力値を指定します。`strata-plan` は GPU を検出せず、値から planner 用 pool を計算します。省略時の入力値は 12,000,000,000 bytes です（`src/plan/plan_main.cpp:13-16,29-30`）。この実行ファイルは CMake の独立した `strata-plan` target です（`CMakeLists.txt:326-331`）。

## 使い方

```sh
strata-plan --vram 16000000000 --dense 4000000000 --embd 1000000000
```

この例の数値は入力例です。実機の空き VRAM と対象モデルの値を自動取得するものではありません。

## 値と既定値

- 値は次の argv 要素から `std::strtoull(..., nullptr, 10)` で変換され、`free_vram` に格納されます（`src/plan/plan_main.cpp:20-30`）。単位はバイトです。
- `--vram` を省略したときの `free_vram` は 12,000,000,000 bytes です。ソースコメントは RTX 5070 の nominal 値としていますが、実機計測値ではありません（`src/plan/plan_main.cpp:13-16`）。
- 値を省略すると stderr に `--vram needs a value` を出して終了コード `2` で終了します（`src/plan/plan_main.cpp:20-24`）。
- parser は変換後の終端位置や `errno` を検査せず、範囲・値域の validation も行いません。不正文字列や数値に続く文字列を CLI が拒否する実装ではなく、変換結果が使われます（`src/plan/plan_main.cpp:20-26`）。
- 複数回指定した場合は同じ変数へ順に代入され、最後に処理された `--vram` または `--pool` の値が残ります（`src/plan/plan_main.cpp:18-43`）。

## 実行時の動作

1. parser は値を `free_vram` に保存します。GPU・ドライバの問い合わせはこの CLI 経路にはありません（`src/plan/plan_main.cpp:13-30,59-66`）。
2. 全引数の処理後、`free_vram` が `dense_bytes + embd_bytes` より大きければ、その差を `pool` にします。差が 0 以下の場合は `pool` が 0 になり、`make_plan` には代わりに固定値 `vram_pool_bytes()`（5,943,000,000 bytes）が渡されます（`src/plan/plan_main.cpp:59-66`、`include/strata/plan/plan.hpp:122-127`）。そのため `--vram` が dense と embedding の合計以下でも、計算 pool が 0 のまま渡される挙動にはなりません。
3. `make_plan` は `dense_bytes` と `embd_bytes` を `workspace_bytes`、`mtp_bytes`、`state_bytes` と合わせて固定費に含め、KV cache と合計して pool に収まるか判定します（`include/strata/plan/plan.hpp:129-151`）。つまり dense / embedding の値は pool 算出時に控除され、さらにこの固定費判定にも含まれます。
4. 成功時の出力には pool、KV + indexer keys、expert cache の計画が表示されます（`include/strata/plan/plan.hpp:154-165`）。

`--pool` は同じ `free_vram` 変数を設定します。両方を指定したときは引数列で後に現れた `--vram` / `--pool` が入力値となりますが、その値は上記の dense / embedding 控除と 0 pool fallback を経由します（`src/plan/plan_main.cpp:29-43,59-66`）。

## 適用条件と副作用

この値は `strata-plan` の算術計画だけに適用されます。ソースで確認した parser と計画処理には、GPU、ファイル、ネットワークへのアクセスはありません（`src/plan/plan_main.cpp:13-73`）。planner は既定の `Geometry` を使って KV と state を計算します（`src/plan/plan_main.cpp:58,65-66`、`include/strata/plan/plan.hpp:22-59,83-100`）。

極端な値の加算・減算について専用の overflow validation は確認できません。特に `dense_bytes + embd_bytes` の unsigned 加算を用いるため、通常のメモリ量を超える入力の計画結果は保証されません（`src/plan/plan_main.cpp:61-63`、`include/strata/plan/plan.hpp:138-146`）。

## 出力とエラー

- 計画が成立すると、計画文字列を stdout に出し終了コード `0` で終了します（`src/plan/plan_main.cpp:64-68`）。
- context に必要な KV と固定費が pool を超えると、`DoesNotClose` の説明を `strata-plan: ...` として stderr に出し、終了コード `1` で終了します。expert cache slot が 1 つも残らない場合も同じ終了コードです（`include/strata/plan/plan.hpp:138-150`、`src/plan/plan_main.cpp:69-72`）。
- 値不足は終了コード `2` です。未知の引数も `unknown argument: ...` を stderr に出し終了コード `2` です（`src/plan/plan_main.cpp:20-24,51-54`）。

## 根拠と調査範囲

- `src/plan/plan_main.cpp:13-30` — 既定値と `--vram` parser。
- `src/plan/plan_main.cpp:20-26` — 値必須処理と数値変換。
- `src/plan/plan_main.cpp:29-43` — `--vram` / `--pool` の共有入力値と上書き順。
- `src/plan/plan_main.cpp:59-72` — pool 控除・fallback、計画出力、失敗処理。
- `include/strata/plan/plan.hpp:61-69,122-151` — 各コストの初期値、pool 定数、計画の固定費と失敗条件。
- `include/strata/plan/plan.hpp:154-165` — 成功時の表示内容。
- `CMakeLists.txt:326-331` — `strata-plan` executable target。
- [`docs/cli/README.md`](../../README.md) — `strata-plan` のトップレベル parser scope と対象リンク。

同一 revision の `strata-plan --help` は実行していません。help の構文・説明は parser に埋め込まれた文字列をソースで確認しました（`src/plan/plan_main.cpp:44-50`）。Release 配布物の有無や内容はこの調査では確認していません。
