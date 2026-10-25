# `strata-plan --workspace`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan`（ルート） |
| オプション | `--workspace B` |
| 別名 | なし |
| 値 | 10 進整数として読むバイト数（`uint64_t`） |

## 役割

メモリー計画で、モデル実行に必要な workspace の見積もりを固定 VRAM コストへ加えます。指定値は expert cache に回せる容量を減らし、固定コストと KV cache が VRAM pool に収まらない場合は計画を失敗させます。

## 使い方

```sh
strata-plan --workspace 268435456
```

値はバイト単位です。例では 256 MiB（268,435,456 bytes）を計上します。

## 値と既定値

- 値を1つ必要とします。末尾に値がない場合は `--workspace needs a value` を標準エラーへ出し、終了コード 2 で終了します。
- 省略時は `Costs::workspace_bytes` の初期値である 0 bytes です。
- 同じオプションを複数回指定した場合、parser は各指定を順に処理し、最後に読んだ値が残ります。
- 値は `std::strtoull(..., nullptr, 10)` で変換されます。変換終了位置や `errno` を確認する検証はありません。そのため、不正な文字列や範囲超過の扱いは堅牢に拒否される仕様ではなく、C ランタイムの変換結果に依存します。負数、空文字列、数値の後ろに文字が続く値も、CLI 独自の検査で拒否されません。

## 実行時の動作

`--workspace` の値は `costs.workspace_bytes` に格納され、`make_plan` の固定コスト `fixed` にそのまま加算されます。KV cache と固定コストの合計が pool を超えると `DoesNotClose` になり、超えなければ workspace 分だけ expert cache の容量と slot 数が減ります。値は計画計算に使われますが、結果表示には workspace 専用の項目がなく、表示される cache 容量などに反映されます。

`--vram` と `--pool` は plan に渡す pool の決定に関わります。`--pool` は parser 内で `--vram` と同じ変数を書き換えるため、両方を指定した場合は引数列で後に現れた方の値が使われます。`--workspace` 自体は pool を設定せず、決定後の pool 内で固定コストとして差し引かれます。workspace の値が大きく、他の固定コストと KV cache を加えると pool を超える場合、または残り容量で expert cache の slot を1つも作れない場合は計画が失敗します。

## 適用条件と副作用

このオプションは `strata-plan` の計画計算だけに作用します。`strata-plan` は独立した計画 CLI として CMake の `strata-plan` 実行 target に登録され、GPU backend の条件付き target 群より前に定義されています。ここでの指定は実際の推論エンジンへ workspace を割り当てたり、GPU メモリーを確保したりするものではありません。

ファイルやネットワークへのアクセス、副プロセスの起動は、このオプションの処理経路にはありません。

## 出力とエラー

成功時は計画全体を標準出力へ出して終了コード 0 です。workspace 超過を含む固定費と KV cache が pool に収まらない場合は、必要 VRAM と pool のバイト数を含む `strata-plan: ...` を標準エラーへ出し、終了コード 1 で終了します。この経路では `--max-context` を減らすよう案内します。計算結果に expert cache slot が1つも残らない場合も `strata-plan: no room for even one expert cache slot ...` を標準エラーへ出して終了コード 1 です。

値がない場合、または未知の引数の場合は標準エラーへ診断を出し、終了コード 2 です。数値の書式や上限に対する独自エラーは実装されていません。

## 根拠

- `src/plan/plan_main.cpp:18-26,35-43` — 引数走査、値の取得、`--workspace` から `costs.workspace_bytes` への格納。値なしは終了コード 2。`--vram` と `--pool` が同じ変数を更新する。
- `src/plan/plan_main.cpp:64-72` — plan 計算の呼び出し、成功時の標準出力、計画失敗時の標準エラーと終了コード。
- `include/strata/plan/plan.hpp:61-69` — `workspace_bytes` の型と既定値 0。
- `include/strata/plan/plan.hpp:129-151` — workspace を含む固定費、pool 超過判定、expert cache 容量計算、および slot が残らない場合の失敗。
- `include/strata/plan/plan.hpp:154-165` — 計画表示項目。workspace 専用行はなく、cache などの計算結果を表示。
- `CMakeLists.txt:326-331` — 独立した `strata-plan` target の定義。
- [CLI 文書索引](../../README.md) — `strata-plan` と本オプション文書の配置。
