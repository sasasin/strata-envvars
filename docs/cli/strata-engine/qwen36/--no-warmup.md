# `--no-warmup`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 engine） |
| オプション | `--no-warmup` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Qwen3.6 engine がモデルのロードと expert 配置を終えた後、通常は実リクエスト前に行う明示的な GPU warmup を省略する。serve、benchmark、単発生成の各実行モードに共通して、モードの処理へ入る前の warmup 呼び出しを制御する。

## 使い方

```sh
# Qwen3.6 モデルを serve モードで起動し、明示的 warmup を省く
strata-q36 --model /models/qwen36.gguf --no-warmup --serve

# 同じ Qwen3.6 engine を strata のモデル選択経路から起動する例
strata --model /models/qwen36.gguf --no-warmup --tokens "1 2 3" --n 16
```

`strata` の場合は、`--model` / `--native` が指す GGUF の architecture が `qwen35moe` のとき Qwen3.6 専用 engine に切り替わる。別 architecture はこの専用 parser の対象ではない（`engine/src/program/generate.cpp:3804-3818`）。

## 値と既定値

値を取りません。省略時は `warm` が `true` で、`--no-warmup` を指定すると `false` になる。複数回指定しても同じ boolean を `false` に設定するだけである。値を続けて書く形式は parser にない。未知の引数・余分な位置引数は通常の直接実行では usage を stderr に出して終了コード 2 となる（`engine/src/qwen35/q36_engine.cu:5342-5353,5372,5412-5418`）。

## 実行時の動作

指定しない場合、`E.warmup()` は model load、engine 初期化、expert 配置、`E.reset()` と MTP 設定の後、serve / benchmark / 単発生成への分岐より前に実行される（`engine/src/qwen35/q36_engine.cu:5522-5526,5555-5562`）。warmup は合成 token の prompt chunk を処理し、条件が合えば最小 GEMM chunk、decode 1 step、MTP draft が有効なら speculative step も処理する。その後 stream を同期し、hybrid routing 等の計数をクリアして engine state を reset する。完了時は所要秒数を stderr に出す（`engine/src/qwen35/q36_engine.cu:4022-4053`）。

このフラグを指定すると `if (warm)` の呼び出し全体がスキップされ、warmup 用の処理、reset、および `strata-q36: warmed up ...` の stderr 出力がありません（`engine/src/qwen35/q36_engine.cu:5561`）。この分岐より前に行うモデルロード、engine 初期化、expert 配置は引き続き実行され、失敗すればそれぞれのエラー経路に進む（`engine/src/qwen35/q36_engine.cu:5458-5465,5522-5526`）。

## 適用条件と副作用

- `strata-q36` を直接実行する場合、および `strata` が `qwen35moe` architecture を検出して Qwen3.6 engine に切り替えた場合に適用される（`engine/src/qwen35/q36_main.cpp:1-5`、`engine/src/program/generate.cpp:3804-3818`）。
- warmup は prompt・decode・（有効な場合の）speculative 計算を先行実行するため、その起動時の GPU 計算と時間を省く。一方、engine のコメントは warmup が初回 prompt の初回利用コストを前払いする意図だと説明しているため、省略時にはその初回利用時の処理が残る（`engine/src/qwen35/q36_engine.cu:4022-4025`）。性能差の大きさはこのソース調査では測定していない。
- parser には `--no-warmup` に対する値の validation や別 option との条件分岐はない（`engine/src/qwen35/q36_engine.cu:5348-5418`）。
- ここでスキップするのは `E.warmup()` の呼び出しである。GPU/backend や依存コードに存在する他の初期化・lazy warmup まで無効にする仕様は確認できない。

## 出力とエラー

フラグ自体は出力やエラーを追加しない。省略時の warmup 完了メッセージは `--no-warmup` 指定時には出ない（`engine/src/qwen35/q36_engine.cu:4052-4053,5561`）。不足値の概念はなく、モデル未指定は stderr に `--model is required` を出して終了コード 2、モデル読込失敗は stderr に理由を出して終了コード 1 となる。これらは warmup の有無にかかわらず warmup 判定より前の経路である（`engine/src/qwen35/q36_engine.cu:5420,5458-5465`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5342-5353,5372` — 既定値 `warm = true`、引数走査、および値なしフラグの parser。
- `engine/src/qwen35/q36_engine.cu:5412-5420` — 不明引数時の usage / 終了コードと、モデル必須条件。
- `engine/src/qwen35/q36_engine.cu:4022-4053` — warmup の内容、state・計数の reset、完了出力。
- `engine/src/qwen35/q36_engine.cu:5522-5526,5555-5562` — 初期化後、各実行モードの前に warmup を呼ぶ順序。
- `engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_main.cpp:1-5` — `strata` の architecture による engine 切替と専用 executable の入口。
