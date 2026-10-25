# `--bench-pp`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata-q36`、または Qwen3.6 family に振り分けられた `strata` |
| オプション | `--bench-pp` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換。正の値で指定した token 数を prompt processing 計測に使う |

## 役割

Qwen3.6 engine の prompt processing（PP）速度を計測します。実際の文章を tokenize するのではなく、固定 seed で生成した整数 token 列を処理する engine 内蔵ベンチマークです。対象 parser は Qwen3.6 専用 parser で、`strata-q36` executable または Qwen3.6 family に切り替わった `strata` がこの engine を使います。単独 executable は CMake の `STRATA_HIP_GFX906` 以外の条件下で定義されています（`src/qwen35/q36_engine.cu:3735-3742`、`CMakeLists.txt:776-794`）。

## 使い方

```sh
strata-q36 --model /path/to/qwen36.gguf --bench-pp 512
```

`--model` には使用する GGUF を指定します。`--bench-tg` を併記すると decode throughput も同じ各反復で計測します。

```sh
strata-q36 --model /path/to/qwen36.gguf --bench-pp 512 --bench-tg 128
```

## 値と既定値

- 省略時の内部値は `0` です。値は `std::atoi` で変換され、`--bench-pp` 専用の範囲検証や変換エラー検出はありません。値を省略すると parser が stderr に `needs a value` を出して終了コード `2` で終了します（`src/qwen35/q36_engine.cu:3737-3747,3763`）。
- ベンチマーク経路に入る条件は `bench_pp > 0 || bench_tg > 0` です。`--bench-pp` の正値を指定しない場合、`--bench-tg` だけが正値でも経路に入り、PP 用列は `max(bench_pp, 1)` により1 token になります。正の `--bench-pp` だけを指定した場合、TG token 数は既定値 `0` です（`src/qwen35/q36_engine.cu:3737,3890-3914`）。
- 0、負数、または `atoi` で0になる値だけではベンチマーク経路に入りません。`--tokens` も指定されていなければ、後続の通常生成経路が `strata-q36: --tokens, --serve or --bench-pp is required` を stderr に出し、終了コード `2` を返します（`src/qwen35/q36_engine.cu:3763,3890,3916-3917`）。

## 実行時の動作

1. parser は値を `bench_pp` に格納します。parser 後、モデルの指定確認、モデル読み込み、engine 初期化、expert 配置を行い、既定では warmup も実行してからベンチマーク分岐に進みます（`src/qwen35/q36_engine.cu:3797-3817,3863-3889`）。
2. PP 列の長さは `max(bench_pp, 1)` です。`std::mt19937` を seed `1234` で初期化し、各要素を `rng() % 200000` で埋めます。利用者の prompt や tokenizer は使いません（`src/qwen35/q36_engine.cu:3890-3898`）。
3. 反復ごとに `E.reset()` してから PP 全体を `E.process` で処理し、CUDA stream を同期して PP 時間を測ります。続いて greedy token を得て、`--bench-tg` 回まで1 token ずつ処理して TG 時間を測ります。この一連を3回実行します（`src/qwen35/q36_engine.cu:3895-3914`）。
4. `--chunk` / `--prefill` は PP の処理 chunk に、`--max-context` / `--ctx` は engine context に影響します。これらを指定しない場合の初期値はそれぞれ `0`（自動決定）と `32768` です。chunk と context の一般 validation はありますが、`--bench-pp` の値を context と照合する個別検証は確認できません（`src/qwen35/q36_engine.cu:3737,3756-3757,3807-3808,3817-3863`）。

## 適用条件と副作用

- `--serve` が同時に指定されている場合は、warmup 後に serve を返す分岐がベンチマーク分岐より先にあるため、ベンチマークは実行されません（`src/qwen35/q36_engine.cu:3888-3891`）。
- `--no-warmup` を指定すると warmup は省略されますが、ベンチマーク自体は省略されません。既定の warmup は prompt chunk・decode step（MTP が有効なら speculative step も）を実行して engine を reset し、stderr に経過時間を出します（`src/qwen35/q36_engine.cu:3766,2757-2777,3888-3891`）。
- `--tokens` が同時指定されても、ベンチマーク分岐が通常の token prompt 解析より前に実行されるため、その値はこの経路では使われません（`src/qwen35/q36_engine.cu:3890-3917`）。
- ベンチマークはモデル読み込みと GPU engine の初期化・計算を伴います。実行環境の実速度を出力しますが、合成 token 列による計測であり、実 prompt の性能を直接表すものではありません（`src/qwen35/q36_engine.cu:3810-3867,3890-3914`）。
- `--bench-pp` が `--max-context` を超える場合の境界処理・安全性は、確認した parser と `E.process` の経路からは確定できません。確認できた `process` は渡された列を chunk ごとに処理しますが、この値と context の照合は行いません（`src/qwen35/q36_engine.cu:2433-2491,3890-3899`）。その範囲外の値を使わず、context 内の長さにしてください。

## 出力とエラー

- 標準出力に各反復の `bench <反復番号>: pp<token数> <tok/s>, tg<token数> <tok/s>` を1行ずつ出し、flush します。PP の既定長はこの出力でも1、TG 速度は TG 数が0以下なら `0.0` です。正常終了時は終了コード `0` です（`src/qwen35/q36_engine.cu:3909-3914`）。
- 値の欠落、model 未指定、無効な `--chunk` / `--max-context` は stderr にエラーを出します。parser の不足値と model/context の事前条件は終了コード `2`、model load や expert 配置失敗は `1` です（`src/qwen35/q36_engine.cu:3745-3746,3797,3807-3815,3863-3866`）。
- CUDA 呼び出しが失敗すると `CK` macro が失敗した式・CUDA error を stderr に出し、終了コード `1` で終了します（`src/qwen35/q36_engine.cu:67-74`）。
- hybrid expert 配置が有効な場合、engine の破棄時に hybrid expert 処理の集計が stderr に出ることがあります（`src/qwen35/q36_engine.cu:3868-3881`）。

## 根拠

- parser、既定値、分岐・出力: `src/qwen35/q36_engine.cu:3735-3797,3890-3917`
- モデル・engine 初期化と context/chunk 設定: `src/qwen35/q36_engine.cu:3807-3889`
- synthetic PP 列、反復、PP/TG 計測: `src/qwen35/q36_engine.cu:3890-3914`
- `E.process` の prompt chunk 処理: `src/qwen35/q36_engine.cu:2433-2491`
- warmup と reset: `src/qwen35/q36_engine.cu:1512-1524,2752-2777`
- CUDA failure 出力: `src/qwen35/q36_engine.cu:67-74`
- executable / family integration build declaration: `CMakeLists.txt:776-794`

同一 revision の `--help` と Release 配布物はこの調査では確認していません。上記は checkout 内の parser・実行箇所と CMake 定義に基づく記述です。
