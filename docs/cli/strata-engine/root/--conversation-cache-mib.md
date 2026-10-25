# `--conversation-cache-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--conversation-cache-mib N` |
| 別名 | なし |
| 値 | MiB 単位の非負整数。最大 `INT64_MAX / (1024 * 1024)` |

## 役割

`--serve` で複数リクエストを受け付ける間、会話の実行状態をホスト RAM に退避して、後続リクエストで共通の prompt prefix を再利用するためのメモリ予算を指定します。これは `--prompt-cache N` が保持する prompt checkpoint とは別の、会話間キャッシュの総 byte budget です。会話ごとに必要な状態を保存し、次のリクエストで一致する prefix があれば復元します（`src/program/generate.cpp:9470-9509`, `src/program/generate.cpp:12683-12694`, `src/program/generate.cpp:12900-12920`）。

## 使い方

```sh
strata --native MODEL.gguf --serve --conversation-cache-mib 4096
```

`--serve` が有効なときに会話を最大 4096 MiB の予算で保持します。エンジンはリクエストを標準入力から受け取ります（`src/program/generate.cpp:2637`, `src/program/generate.cpp:3168`）。

## 値と既定値

- 指定値は10進の非負整数で、値全体が整数として読み取れる必要があります。負数、小数、末尾に余分な文字がある値、上限超過は拒否されます。エラーは標準エラーに `--conversation-cache-mib needs a nonnegative integer within range` と出し、終了コード `2` になります（`src/program/generate.cpp:2641-2655`）。
- 値を省略した場合の内部既定値は `-1`（未指定）です。`--serve` かつ `--prompt-cache > 0` かつ `--conversation-cache-slots > 0` なら、モデル読み込み後の利用可能 RAM と `--conversation-cache-min-free-mib` を基に自動設定します（`src/program/generate.cpp:729-731`, `src/program/generate.cpp:9373-9393`）。
- 自動値は、空き RAM から指定 RAM floor を引いた量の40%を256 MiB単位で切り下げ、最大8192 MiBです。計算結果が1024 MiB未満、利用可能 RAM が不明、または floor 以下なら `0`（無効）になります（`include/strata/core/conversation_memory.hpp:67-78`）。空き RAM は Linux では `MemAvailable` と見える cgroup 制限等を考慮し、Windows では空き物理 RAM と commit limit の小さい方を基に取得します。取得できない OS では不明値になります（`src/core/conversation_memory.cpp:258-298`）。
- 明示した値は `0` を含め自動設定で変更されません。`0` は会話 cache を無効にします（`src/program/generate.cpp:9373-9393`, `include/strata/core/conversation_cache.hpp:210-217`）。

## 実行時の動作

cache は `--serve` のリクエスト処理で生成され、設定値を byte に換算して `ConversationCache` に渡します。予算または slot 数が `0` なら cache は無効です（`src/program/generate.cpp:8348-8355`, `src/program/generate.cpp:9391-9393`, `include/strata/core/conversation_cache.hpp:210-217`）。

会話を切り替えるとき、現行会話の checkpoint と実行状態を snapshot として保存します。snapshot が予算を超える場合は保存をスキップし、slot 数または byte 予算が不足する場合は古い会話を退避して空きを作ります。利用可能 RAM が `--conversation-cache-min-free-mib` の floor を保てない場合も保存を見送り、必要なら古い会話を順に evict します（`src/program/generate.cpp:9470-9509`, `src/program/generate.cpp:9553-9599`, `include/strata/core/conversation_cache.hpp:313-349`）。次の入力に一致する状態があれば復元します（`src/program/generate.cpp:12683-12694`, `src/program/generate.cpp:12900-12920`）。

## 適用条件と副作用

- `--serve` を付けない通常の単発生成では、この会話間 cache を使用しません。`--serve` であっても `--prompt-cache 0` または `--conversation-cache-slots 0` なら無効になり、予算が正値の場合はその理由を標準エラーへ警告します（`src/program/generate.cpp:2956-2958`, `src/program/generate.cpp:7051-7054`, `include/strata/core/conversation_cache.hpp:210-217`）。`--prompt-cache` の既定値は6、slot数の既定値は4です（`src/program/generate.cpp:725-730`, `src/program/generate.cpp:891-895`）。
- snapshot のコピーはホスト RAM を消費します。物理 RAM の検査で空き不足、RAM 情報不明、予算不足、snapshot 作成不能となった場合、cache 保存をスキップして serving を継続する経路があります。失敗理由は標準エラーに `conversation cache: skip parking ...` 等で出力されます（`src/program/generate.cpp:9540-9563`, `src/program/generate.cpp:9565-9633`）。
- `--memory-limit-mib` または `STRATA_MEMORY_LIMIT_MIB` は RAM guard が見る上限に影響します。両方がある場合は CLI 値が優先されます。指定値・環境変数の値は非負 MiB 整数として検証され、無効な環境変数値はエラー終了します（`src/program/generate.cpp:2924-2937`; 仕様の説明は `include/strata/core/conversation_memory.hpp:10-30`）。
- `--layer-split` を単一 GPU（`--split-device 0`）に構成した場合、明示した正の予算、正の slot 数、正の `--prompt-cache` の組み合わせは非対応として標準エラーへ理由を出し、終了コード `2` になります。`--conversation-cache-mib 0` ならこの条件には該当しません（`src/program/generate.cpp:3003-3008`）。未指定値はこの検査時点では `-1` のため正値判定を通らず、その後の空き RAM による自動設定が有効値になる可能性があります。これは検査と自動設定の順序から分かる動作です（`src/program/generate.cpp:3005-3008`, `src/program/generate.cpp:9373-9393`）。
- `--model` / `--native` の指定モデルが Qwen3.6-35B-A3B（ソース上の family 名 `Qwen35Moe`）と判定されると、通常 parser より前に専用 `qwen35::run` へ引数を渡します。この専用経路を通常 engine parser の本オプションとして確認していません。ここでの説明は通常 engine parser に到達するモデル経路が対象です（`src/program/generate.cpp:2393-2407`）。

## 出力とエラー

- 明示値の形式違反は parser で拒否され、標準エラーに validation message を出して終了コード `2` です。値が欠落した場合も `--conversation-cache-mib needs a value` を標準エラーに出して終了コード `2` です（`src/program/generate.cpp:2418-2421`, `src/program/generate.cpp:2645-2653`）。
- 未指定時の自動設定では、正値なら設定 MiB と slot 数を、0なら RAM 不足による cache 無効を標準エラーに表示します（`src/program/generate.cpp:9376-9389`）。
- cache 保存の試行は `parked` / `skipped`、保存 byte 数、eviction 数等を標準エラーに出します。allocation failure も `allocation failed; skip parking` と記録され、通常 serving を続けます（`src/program/generate.cpp:9591-9632`）。

## 関連オプション

- [`--conversation-cache-slots`](--conversation-cache-slots.md): 保持する会話数の上限。
- [`--conversation-cache-min-free-mib`](--conversation-cache-min-free-mib.md): 保存・復元時に残す RAM floor。自動予算の算出にも使われます。
- [`--prompt-cache`](--prompt-cache.md): `--serve` 内で維持する prompt checkpoint 数。
- [`--memory-limit-mib`](--memory-limit-mib.md): memory guard の上限。

## 根拠

索引の scope は [`docs/cli/README.md:1128-1153`](../../README.md#strata-engine) の `strata-engine` / `strata`（エンジン引数）です。parser、既定値、自動算出、実行時の保存・復元処理を同一 revision の `src/program/generate.cpp` と `include/strata/core/conversation_memory.hpp`、`include/strata/core/conversation_cache.hpp`、`src/core/conversation_memory.cpp` で確認しました。ビルド済み CLI の `--help` や Release artifact はこの調査では参照していません。
