# `strata` / Qwen3.6 `--bench-pp`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6-35B-A3B / `qwen35moe` の場合） |
| オプション | `--bench-pp` |
| 別名 | なし |
| 値 | prompt 用 token 数を表す整数 `N` |

## 役割

Qwen3.6 エンジンで合成 prompt の prefill throughput を測定する。`--bench-pp N` は `N` 個の token を処理する prompt 測定を有効にし、測定結果を3回出力する。必要に応じて [`--bench-tg`](--bench-tg.md) を併用すると、各回の prompt 後に token-by-token の decode も測定する。

## 使い方

```sh
# Qwen3.6 GGUF の prefill を 2048 token で測定
strata --model /models/qwen36.gguf --bench-pp 2048

# 同じ測定で decode throughput も 128 token 分測定
strata --model /models/qwen36.gguf --bench-pp 2048 --bench-tg 128
```

## 値と既定値

このオプションは値を1つ取り、`std::atoi` で `int` に変換する。省略時は内部値 `0` であり、`--bench-pp` 単独による benchmark は有効にならない。prompt 測定を意図する場合は正数を指定する。parser に数値形式・正数範囲の明示 validation はなく、変換結果が0以下ならこの値だけでは benchmark 分岐を有効化しない。非数値文字列は `atoi` により0として扱われる。複数回指定した場合は parser が順番に代入し、最後の値が残る。

## 実行時の動作

値は `bench_pp` に格納され、`bench_pp > 0 || bench_tg > 0` のとき benchmark 経路に入る。prompt の token ID は `std::mt19937` の seed `1234` から生成し、長さは `max(bench_pp, 1)`。したがって、`--bench-pp` が0以下でも `--bench-tg` が正数なら、1 token の prompt prefill の後に decode を測る。各反復の先頭で engine state を reset し、prompt を処理して GPU stream を同期した後、`bench_tg` 回の1-token decode を行う。この一連を3回行う。測定対象は実際のユーザー prompt ではなく、固定 seed で作った合成 token ID 列である。

benchmark 分岐は `--serve` 分岐の後、通常の `--tokens` prompt の検査より前にある。そのため `--serve` と同時に指定した場合は serve が優先され、benchmark は行われない。`--tokens` も受理されるが benchmark 分岐では使われない。`--no-warmup` を指定しない場合、benchmark の3反復より前に通常の warmup が実行される。

## 適用条件と副作用

`strata` の family switch は `--model` または `--native` の GGUF ヘッダーを調べ、family が `qwen35moe` の場合に Qwen3.6 parser へ処理を渡す。この文書の対象はその経路であり、Qwen3.6 専用 parser を直接呼ぶ別 entry point がある場合も同じ `run` 処理を使う。

benchmark 分岐に到達する前にモデルを GPU へロードし、engine を初期化して expert 配置を行う。既定では warmup も実行されるため、測定前に相応のモデル/GPU 初期化処理が発生する。benchmark は3回の推論処理を実行する。`--peer-device` による peer tier が有効な場合は、各反復後に tier 統計も stderr に出力する。`--bench-pp` 自体がファイルを指定・生成する処理は確認できない。

## 出力とエラー

各反復で stdout に `bench <反復番号>: pp<token数> <tok/s>, tg<token数> <tok/s>` の形式を出力し、flush する。`--bench-tg` が0以下の場合、tg throughput は `0.0` と出力される。通常の起動・配置メッセージや条件付き peer tier 統計は stderr 側に出る。

`--bench-pp` の値が欠落すると `strata-q36: --bench-pp needs a value` を stderr に出して終了コード2となる。モデル指定がなければ `--model is required` で終了コード2。モデルの読込・形式検査や expert 配置の失敗は stderr に理由を出し、確認した経路では終了コード1。benchmark 条件が成立せず `--tokens` などの有効な実行モードもない場合は `--tokens, --serve or --bench-pp is required` を出して終了コード2となる。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5370` — Qwen3.6 parser と `--bench-pp` の値取得（`atoi`）。
- `engine/src/qwen35/q36_engine.cu:5412-5420` — 未知引数、値なし、およびモデル未指定のエラー経路。
- `engine/src/qwen35/q36_engine.cu:5456-5465` — モデル読込前の検査と読込失敗時の終了コード。
- `engine/src/qwen35/q36_engine.cu:5522-5525` — engine 初期化・expert 配置と配置失敗時の終了コード。
- `engine/src/qwen35/q36_engine.cu:5555-5562` — warmup の既定実行と serve 分岐。
- `engine/src/qwen35/q36_engine.cu:5563-5596` — benchmark 条件、合成 token 列、3反復、出力、および通常 prompt 経路への分岐。
- `engine/src/program/generate.cpp:3804-3818` — `--model` / `--native` の GGUF family を判定し、Qwen3.6 を専用 parser に振り分ける箇所。
