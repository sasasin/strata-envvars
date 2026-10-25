# `--embd`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan`（ルート） |
| オプション | `--embd` |
| 別名 | なし |
| 値 | 10進整数。埋め込みテンソルのサイズをバイト数で指定 |

## 役割

トークン埋め込みの常駐サイズを planner に渡します。この値は推論実行や重みの読み込みを行わず、計画上の固定費として扱われます。`--embd` を省略した場合の値は 0 バイトです。

## 使い方

```sh
strata-plan --embd 1200000000
```

`1200000000` は例示用のバイト数です。適切な値は対象モデルの埋め込みテンソルに応じて指定してください。

## 値と既定値

- 値は後続の引数から `std::strtoull(..., nullptr, 10)` で変換し、`Costs::embd_bytes` に格納します。`Costs` の初期値は 0 です。
- 引数がない場合は `--embd needs a value` を標準エラーに出し、終了コード 2 で終了します。
- 数値の範囲・全体が数値であること・変換エラーを明示的に検査する処理は parser にありません。したがって、範囲外値や不正文字列の結果を CLI が検証・拒否すると断定できません。C ライブラリの `strtoull` の変換規則に従います。
- 同じオプションを複数回指定したときは、走査中に同じ変数へ順に代入されるため、最後の指定値が残ります。

## 実行時の動作

`strata-plan` は `--embd` の値を `costs.embd_bytes` に設定します。pool の計算では `free_vram - dense_bytes - embd_bytes` を使い、値が控除後の pool に反映されます。控除対象の合計が `free_vram` 以上なら中間 pool は 0 となり、`vram_pool_bytes()` の既定値が使われます。`--pool` は `free_vram` 自体を上書きし、`--vram` と `--pool` の両方がある場合は引数列で後に処理された方が残ります。

その後 `make_plan` は `dense_bytes + embd_bytes + mtp_bytes + workspace_bytes + state_bytes` を固定費に含め、KV と合わせて pool に収まるか判定します。出力の `expert arena (DRAM)` は `dense_bytes + embd_bytes` として表示されます。従って、埋め込みサイズは利用可能な expert cache 枠を減らし、固定費が pool を超えると計画を失敗させます。

## 適用条件と副作用

このオプションは CMake の `strata-plan` 実行ファイルが対象とする、GPU に依存せず計算できるメモリ計画に適用されます。CLI は指定値をファイルや環境変数から自動取得せず、モデルの実テンソルサイズとの整合性も検査しません。実行時の GPU・ファイル・ネットワークへの副作用は parser と planner の経路にはありません。

unsigned 値の加算・減算について追加のオーバーフロー検査はありません。極端な値を指定した場合の正しいメモリ計画は保証されません。

## 出力とエラー

成功時は計画を標準出力に出して終了コード 0 です。固定費と KV が pool を超える場合、`strata-plan: ... reduce --max-context` を標準エラーに出して終了コード 1 で終了します。cache slot が 0 の場合も `strata-plan: no room for even one expert cache slot ...` を標準エラーに出して終了コード 1 です。未知の引数は `unknown argument: ...` を標準エラーに出し、終了コード 2 です。

## 根拠

- `src/plan/plan_main.cpp:13-18` — context、VRAM、`Costs` の初期化。
- `src/plan/plan_main.cpp:20-25` — 値必須処理と `strtoull` による変換。
- `src/plan/plan_main.cpp:31-34` — `--dense` と `--embd` の parser 登録および格納先。
- `src/plan/plan_main.cpp:37-53` — 他の pool/state 引数、help、未知引数の処理。
- `src/plan/plan_main.cpp:56-67` — state 既定値、VRAM pool 控除・fallback、計画実行と成功出力。
- `src/plan/plan_main.cpp:69-72` — 計画失敗時の標準エラーと終了コード。
- `include/strata/plan/plan.hpp:61-69` — 各 byte cost の既定値と `embd_bytes` の意味。
- `include/strata/plan/plan.hpp:129-151` — 固定費、pool の適合判定、cache slot 数と失敗条件。
- `include/strata/plan/plan.hpp:154-165` — 計画出力。DRAM arena 表示は `dense_bytes + embd_bytes` に基づく。
- `CMakeLists.txt:323-331` — GPU 非依存の interface library と `strata-plan` target。
