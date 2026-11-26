# `strata` / `strata-q36`（Qwen3.6）`--max-context`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 モデル選択時）または `strata-q36` |
| オプション | `--max-context` |
| 別名 | `--ctx` |
| 値 | `atoi` で整数に変換する値。256 以上 |

## 役割

Qwen3.6 エンジンが確保・管理する会話 context のセル数を指定します。attention の K/V cache と recurrent state はセッションごとにこの値を使って初期化されます。serve 時には prompt と生成上限の合計がこの値を超える要求を受け付けません。

## 使い方

```sh
# Qwen3.6 のエンジンを serve モードで起動し、context を 65536 セルにする
strata-q36 --model model.gguf --max-context 65536 --serve

# `strata` から Qwen3.6 を選ぶ場合も同じ parser に渡される
strata --model model.gguf --ctx 65536 --serve
```

## 値と既定値

- 省略時は `32768`。`--max-context` と `--ctx` は同じ `ctx` 変数を設定し、複数回指定した場合は parser の走査順で後から指定した値が残ります。
- 引数は `std::atoi` で変換されます。厳密な数値書式の検証はありません。値が欠けると `strata-q36: --max-context needs a value` を stderr に出して終了コード 2、変換結果が 256 未満なら `strata-q36: bad --chunk / --max-context` を stderr に出して終了コード 2 になります。
- parser に context の上限 clamp はありません。格納先は `int` です。範囲外の数値文字列に対する `atoi` の結果はソースで規定・検証されていません。

## 実行時の動作

parser で得た値は `E.init(m, ctx, chunk, batch, vision)` に渡され、`Engine::ctx` に保持されます。各 session の K/V cache の大きさは context と `--kv` の幅に応じて決まり、GDN 層の recurrent state も session ごとに確保されます（`engine/src/qwen35/q36_engine.cu:1962-1968, 2140-2148`、K/V 割当は同 `1888-1896`）。serve の起動時には `READY <context> stop` を stdout に出します（同 `5281-5285`）。

`--batch`（別名 `--slots`）で複数 session を使う場合、context に比例する session memory が slot 数分必要です。エンジンは必要量と空き VRAM を表示し、session cache の概算が空き VRAMを 1 GiB の余裕込みで超えると stderr に不足を示して終了コード 1 で終了します（同 `2142-2159`）。単一 session では model の配置や hybrid buffer 等も含む fit 判定を行い、実行不能で適合値を算出できた場合は短い context の提案を出して終了します。判定が context 自体を自動変更することはありません（同 `2161-2180`、`engine/include/strata/qwen35/context_fit.hpp:50-75`）。

## 適用条件と副作用

- 索引がこの文書に割り当てる scope は、Qwen3.6 選択時の `strata` と standalone `strata-q36` の専用 parser です。parser は `--max-context` と `--ctx` の両方を受理します（`engine/src/qwen35/q36_engine.cu:5339-5363`）。
- 大きい値は K/V cache 等の必要メモリを増やし、初期化時の VRAM 不足や割当失敗につながることがあります。K/V cache の幅は `--kv`、session 数は `--batch` と相互作用します（同 `2142-2159`）。
- serve protocol では `prompt tokens + max_new` が context を超える要求に対し、プロセスを終了せず `ERR prompt (...) + max_new (...) exceeds the context (...)` を stdout に返します（同 `5068-5081`）。
- ソース上、モデルの学習済み context 長をこのオプション値と比較して拒否・自動補正する処理は確認できませんでした。実用上の上限は VRAM・モデル・他の設定に依存します。

## 出力とエラー

- context が 256 未満: stderr に `bad --chunk / --max-context`、終了コード 2（`engine/src/qwen35/q36_engine.cu:5456-5458`）。
- 複数 slot の概算が VRAM 条件を満たさない: stderr に slot 数・context・概算と調整案を表示し、`std::exit(1)`（同 `2151-2159`）。
- 単一 session の fit 判定で拒否される場合: stderr に必要量・空き量・算出した適合 context を表示します（同 `2161-2180`、`engine/include/strata/qwen35/context_fit.hpp:68-75`）。
- serve 中の要求が context を超える場合: stdout に `ERR ... exceeds the context ...` を返して要求を終了します（同 `5078-5081`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5363` — Qwen3.6 parser、既定値、`--max-context` / `--ctx` の受理。
- `engine/src/qwen35/q36_engine.cu:5456-5458` — context の最低値検査。
- `engine/src/qwen35/q36_engine.cu:1962-1968, 2140-2159` — Engine 初期化、session ごとの K/V・state 容量、複数 slot の VRAM 判定。
- `engine/src/qwen35/q36_engine.cu:2161-2180` と `engine/include/strata/qwen35/context_fit.hpp:50-75` — 単一 session の fit 判定と不足時メッセージ。
- `engine/src/qwen35/q36_engine.cu:5068-5081, 5281-5285` — serve 要求の context 上限と起動時 `READY` 出力。
