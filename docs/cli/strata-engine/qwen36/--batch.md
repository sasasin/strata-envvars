# `--batch`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 専用 parser、または `strata-q36` |
| オプション | `--batch N` |
| 別名 | `--slots N` |
| 値 | 整数として `atoi` で読み取る session 数 |

## 役割

Qwen3.6 engine が保持する会話 session 数を指定します。`--serve` と併用すると、各 session が独立した recurrent state と KV cache を持ち、複数の要求を同じ decode window で処理できます。Qwen3.6 は通常の `src/program/generate.cpp` engine parser と異なる実装経路なので、この説明は `qwen36/` scope に限ります。`strata` は GGUF architecture が `qwen35moe` の場合、この parser に処理を渡します。 (`src/program/generate.cpp:2394-2406`、`src/qwen35/q36_main.cpp:1-5`)

## 使い方

```sh
strata --model /path/to/qwen36.gguf --serve --batch 4
```

この例では最大4 sessionを作ります。Qwen3.6 の識別条件に合うモデルが必要です。`--batch` の別名を使う場合は `--slots 4` と指定できます。 (`src/qwen35/q36_engine.cu:3748-3777`、`src/qwen35/q36_engine.cu:965-975`)

## 値と既定値

- 省略時は `0`。初期値の session 数1で動き、バッチ slot はありません。 (`src/qwen35/q36_engine.cu:3735-3741`、`src/qwen35/q36_engine.cu:1342`)
- 値は `std::atoi` で読み込み、session 数は `max(1, min(N, 8))` に制限されます。したがって `0`、負数、整数として読めない文字列は1 sessionになり、8を超える値は8 sessionになります。 `--batch` と `--slots` を両方指定した場合は、後に解析された値が残ります。 (`src/qwen35/q36_engine.cu:1208`、`src/qwen35/q36_engine.cu:1342`、`src/qwen35/q36_engine.cu:3740-3742`、`src/qwen35/q36_engine.cu:3776`)
- 値を省略すると parser は `strata-q36: <指定した option> needs a value` を stderr に出して終了コード2で終了します。 (`src/qwen35/q36_engine.cu:3742-3746`)

## 実行時の動作

`--batch N` は session ごとに recurrent state、attention KV cache、MTP block の KV cache（モデルに MTP block がある場合）を持ちます。各 session の状態を GPU に確保し、同時に処理中の slot の行を一つの decode window にまとめます。通常の `GEN`/`GENI` は単一要求の経路です。複数要求を slot に割り当てるには `--serve` を指定し、server protocol の `BGEN` または `BGENI` 要求を使います。 (`src/qwen35/q36_engine.cu:1194-1218`、`src/qwen35/q36_engine.cu:3174-3178`、`src/qwen35/q36_engine.cu:3431-3450`)

`--serve` 時は session 数が2以上なら起動時に `INFO batch_slots=N slot_cache=1` を stdout に出し、その後 `READY` を出します。session の状態は slot 間で独立します。 (`src/qwen35/q36_engine.cu:3678-3681`)

## 適用条件と副作用

- `--serve` なしでも指定数の session を初期化するため VRAM を使いますが、複数要求を同時 decode する BGEN/BGENI protocol は serve 経路でのみ処理されます。通常の `GEN`/`GENI` は単一要求用です。 (`src/qwen35/q36_engine.cu:3863-3864`、`src/qwen35/q36_engine.cu:3174-3178`、`src/qwen35/q36_engine.cu:3431-3450`)
- session 数に応じて GPU メモリ使用量が増えます。engine は複数 session の場合、context 長に基づく session ごとの VRAM 見積もりと空き量を stderr に表示します。必要量と1 GiB の余裕を確保できなければ、VRAM 不足メッセージを出して終了コード1で終了します。 (`src/qwen35/q36_engine.cu:1450-1469`)
- 要求を受け付ける際に指定 slot が範囲外、使用中、または session 数が1の場合は stdout に `ERR BGEN: no such free slot ...` を返します。 (`src/qwen35/q36_engine.cu:3441-3449`)
- `--batch-mtp` は複数 session と `--mtp N`（Nが正数）の両方がある場合に有効です。必要条件を満たさない `--batch-mtp` は stderr に注意を出して無視されます。`STRATA_BATCH_MTP` による有効化もあります。 (`src/qwen35/q36_engine.cu:3882-3887`)

## 出力とエラー

- 値が欠落した場合は stderr と終了コード2です。未知の引数は serve mode では警告してスキップされ、それ以外では usage を表示して終了コード2になります。 (`src/qwen35/q36_engine.cu:3742-3746`、`src/qwen35/q36_engine.cu:3782-3795`)
- session allocation が失敗した場合、VRAM 不足の詳細を stderr に出し終了コード1で終了します。指定数より少ない session に自動縮小する処理は確認できません。 (`src/qwen35/q36_engine.cu:1450-1469`)

## 根拠

- `src/program/generate.cpp:2394-2406` — `qwen35moe` を検出した場合の Qwen3.6 parser への振り分け。
- `src/qwen35/q36_engine.cu:3735-3797` — Qwen3.6 parser、`--batch`/`--slots` の受理、必須値処理、serve mode。
- `src/qwen35/q36_engine.cu:1194-1218`、`src/qwen35/q36_engine.cu:1339-1344` — session の状態と 1〜8 の上限。
- `src/qwen35/q36_engine.cu:1450-1471` — session ごとの VRAM 見積もり・不足時の終了・割り当て。
- `src/qwen35/q36_engine.cu:3174-3178`、`src/qwen35/q36_engine.cu:3431-3450`、`src/qwen35/q36_engine.cu:3678-3681` — serve protocol、slot の選択・エラー、起動時出力。

調査範囲はこの checkout のソースです。同一 revision の既存 `strata-q36` binary や Release artifact は確認していません。
