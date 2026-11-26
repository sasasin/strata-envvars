# `strata` / `strata-q36` `--bench-tg`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 モデル選択時）または `strata-q36` |
| オプション | `--bench-tg` |
| 別名 | なし |
| 値 | 整数。専用の範囲検証なし |

## 役割

Qwen3.6 エンジンのベンチマーク経路で、prompt 処理後に逐次生成する token 数を指定する。`--bench-pp` と併用すると prompt と token generation の両方を計測し、`--bench-tg` 単独では prompt を 1 token として generation を計測する。ベンチマーク経路はモデル読み込み・配置と既定の warmup の後に動く（`engine/src/qwen35/q36_engine.cu:5342-5347, 5561-5565`）。

## 使い方

```sh
# Qwen3.6 GGUF の token generation を 32 token 分計測
strata --model /models/qwen36.gguf --bench-tg 32

# 同時に prompt 128 token の処理も計測
strata --model /models/qwen36.gguf --bench-pp 128 --bench-tg 32
```

`strata` は `--model` / `--native` の GGUF family が Qwen3.6 (`Qwen35Moe`) の場合に専用 parser へ切り替わる。独立入口 `strata-q36` も同じ `run` 関数を呼ぶ（`engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_main.cpp:1-5`）。

## 値と既定値

- 値は `std::atoi` で整数変換される。省略時は `0`。同じ option を複数指定すると、引数を順に読む parser のため最後の値が残る（`engine/src/qwen35/q36_engine.cu:5342, 5348-5353, 5369-5370`）。
- 引数自体を省略すると `strata-q36: --bench-tg needs a value` を stderr に出して終了コード `2` で終了する。非整数値は `atoi` により `0` となり、専用エラーにはならない。値の形式・範囲を検証する処理は確認できない（同 `:5350-5352, 5369-5370`）。
- ベンチマーク分岐は `bench_pp > 0 || bench_tg > 0` のときだけ実行する。負値・0 はその条件を満たさない。`--bench-tg` 単独で正値を指定した場合、prompt token 数は `max(bench_pp, 1)` により 1 となる（同 `:5563-5567`）。

## 実行時の動作

`--bench-tg N` は `bench_tg` に保存される。`--bench-pp` とどちらかが正なら、固定 seed `1234` の乱数生成器から `max(bench_pp, 1)` 個の token ID（各値は `rng() % 200000`）を作り、3 回計測する。各回で engine state を reset し、まず prompt を処理して同期した後、1 token ずつ `N` 回処理して greedy token を次の入力にする。stdout の各行に prompt と generation の token/s が出る。したがってこの値は入力 prompt の長さではなく、計測する逐次 generation の反復回数である（`engine/src/qwen35/q36_engine.cu:5563-5585`）。

`--no-warmup` を指定しない限りベンチマーク前に `E.warmup()` が呼ばれる。`--serve` も指定した場合は warmup 後に serve が選ばれ、ベンチマーク分岐には到達しない（同 `:5561-5564`）。モデルが必須で、読み込み・engine 初期化・expert 配置はベンチマーク分岐より前に行われる（同 `:5420, 5458-5525`）。

## 適用条件と副作用

- Qwen3.6 専用 parser のオプションである。`strata` では Qwen3.6 family と判定されたモデルに切り替わった場合にこの parser が処理する（`engine/src/program/generate.cpp:3804-3818`）。
- 正の `--bench-tg` はモデル推論を伴う GPU ベンチマークを実行し、モデルの読み込み、engine 初期化、expert 配置、既定の warmup を発生させる。計測の前にモデルや CUDA 関連初期化が失敗すればベンチマークは始まらない（`engine/src/qwen35/q36_engine.cu:5458-5525, 5561-5585`）。
- ベンチ用 prompt は実ユーザーの文章ではなく生成した token ID であり、ベンチ用 token 列の作成に外部ファイル入力は使わない（同 `:5565-5567`）。
- `--bench-tg` 自体にファイル出力処理はない。ベンチ結果は stdout に出力される。peer device が有効な場合は各反復の tier 情報も出力され得る（同 `:5583-5591`）。

## 出力とエラー

- ベンチ経路は `bench 0:` から `bench 2:` までの行を stdout に出し、各行に prompt throughput と generation throughput を含める。`bench_tg <= 0` のとき generation throughput 欄は `0.0` になる（`engine/src/qwen35/q36_engine.cu:5583-5585`）。
- option 値の欠落は終了コード `2`。model 未指定も stderr に `strata-q36: --model is required` を出して `2`。モデル読み込み失敗・例外、または expert 配置失敗は stderr に理由を出し `1`（同 `:5350-5352, 5420, 5460-5465, 5522-5525`）。
- 未知 option など通常 parser で処理できない引数は usage を stderr に出して終了コード `2`（同 `:5405-5417`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5348-5370` — Qwen3.6 引数 parser、`--bench-tg` の整数変換、値欠落時の処理。
- `engine/src/qwen35/q36_engine.cu:5412-5420` — usage とモデル必須条件。
- `engine/src/qwen35/q36_engine.cu:5456-5525` — モデル読み込み、初期化、expert 配置と失敗経路。
- `engine/src/qwen35/q36_engine.cu:5561-5591` — warmup、serve/benchmark の分岐、3 回の計測、stdout 出力。
- `engine/src/program/generate.cpp:3804-3818` — `strata` から Qwen3.6 family 専用 parser への切り替え。
- `engine/src/qwen35/q36_main.cpp:1-5` — `strata-q36` 入口が同じ `run` 実装を呼ぶこと。
