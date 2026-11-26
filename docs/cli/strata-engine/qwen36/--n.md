# `--n`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36` の Qwen3.6 専用 engine parser |
| オプション | `--n` |
| 別名 | なし（`--max-new` も同じ内部変数を設定するが、parser 上の alias ではない） |
| 値 | 整数として `std::atoi` で変換される値 |

## 役割

トークン列を直接入力して生成する Qwen3.6 のローカル実行で、生成するトークン数を指定する。通常の `strata` は `--model` / `--native` で指定した GGUF の architecture が `qwen35moe` と判定された場合にこの parser へ切り替わる。専用実行ファイル `strata-q36` も同じ `run` 関数を呼ぶ（`engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_main.cpp:1-5`）。

## 使い方

```sh
# モデルと入力 token ID 列を指定し、16 token 生成する
strata --model ./qwen36.gguf --tokens 1,2,3 --n 16

# 専用 engine を使う場合も同じ parser と値の扱い
strata-q36 --model ./qwen36.gguf --tokens 1,2,3 --n 16
```

`--tokens` の値はカンマまたは空白区切りの整数 ID 列として解析される。例の `1,2,3` は構文例であり、モデルに適した prompt token 列を指定する必要がある（`engine/src/qwen35/q36_engine.cu:4604-4616`）。

## 値と既定値

- 省略時は `n_gen = 64`。
- `--n` の次の引数を `std::atoi` で整数化して `n_gen` に設定する。parser に明示的な範囲検証はない。数値として解釈できない値は `atoi` の結果として0になり、負数も拒否されない（`engine/src/qwen35/q36_engine.cu:5342-5348,5350-5353,5364-5366`）。
- 値を省略すると `strata-q36: --n needs a value` を stderr に出して終了コード2で終了する（同 `5350-5353`）。
- 同じオプションを複数回指定した場合、parser は順に処理し、最後に設定された整数が残る（同 `5348-5366`）。

## 実行時の動作

通常の `--tokens` 生成では、`n_gen` 回まで greedy token を追加し、最終列を `gen: ...` として stdout に出力する。処理時間と token 数の要約は stderr に出る（`engine/src/qwen35/q36_engine.cu:5639-5657`）。

同じ `n_gen` は `--max-new` でも設定できるため、両方を指定した場合は引数列で後に処理された方が値を決める（同 `5355-5357,5364-5366`）。ただし `--force IDS` の解析結果が空でなければ、`--n` / `--max-new` の値にかかわらず `n_gen` は強制 token 数 + 1 に置き換わる（同 `5595-5598`）。

`--mtp` が有効で、forced token 列も logits dump もない場合は MTP 生成ループを使うが、ループ上限にも `n_gen` が使われる（同 `5614-5629`）。

## 適用条件と副作用

`--n` が生成数に反映されるのは `--tokens` による通常の生成経路だけである。`--serve` は Engine 初期化後に `serve(E)` へ戻り、リクエストごとの `GEN <max_new> ...` が数を与えるため、起動引数の `--n` はサーバー生成数を制御しない。また `--bench-pp` / `--bench-tg` は先にベンチマーク経路へ分岐するため、これらの測定回数・token 数にも `--n` は使われない（`engine/src/qwen35/q36_engine.cu:5561-5564,5595-5597`）。

0 以下の値を parser は拒否しない。通常生成ではループが実行されず、生成列が空のまま `gen:` が出力される。MTP 経路では負の `n_gen` が `size_t` に変換されて `gen.resize` に渡るため、極端に大きなサイズ要求となり得る。負数を指定した場合の安全な生成動作は保証されない（同 `5614-5629,5639-5653`）。

## 出力とエラー

- `--n` に値がない場合は stderr に不足を表示し、終了コード2（`engine/src/qwen35/q36_engine.cu:5350-5353`）。
- `--tokens` などの必須入力がない通常実行では stderr に `--tokens, --serve or --bench-pp is required` を出し、終了コード2（同 `5595-5597`）。
- 成功時、生成 token ID 列は stdout、prompt / generation の時間と速度は stderr に出力される（同 `5650-5657`）。

## 根拠

- `engine/src/program/generate.cpp:3804-3818` — `--model` / `--native` の GGUF architecture を見て Qwen3.6 family を専用 parser に振り分ける箇所。
- `engine/src/qwen35/q36_main.cpp:1-5` — `strata-q36` が Qwen3.6 共通 `run` 関数へ委譲する箇所。
- `engine/src/qwen35/q36_engine.cu:5342-5366` — 既定値、値の取得、`--n` と `--max-new` の parser 定義。
- `engine/src/qwen35/q36_engine.cu:5595-5657` — 入力条件、`--force` による上書き、通常 / MTP 生成数の適用と出力。
- `docs/cli/README.md:1240-1275` — Qwen3.6 parser の索引スコープとこの文書へのリンク。
