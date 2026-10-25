# `--n`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | Qwen3.6 専用 engine parser（`strata` の family switch 経由、または `strata-q36`） |
| オプション | `--n` |
| 別名 | なし。`--max-new` も同じ生成数変数を書き換える別の受理名 |
| 値 | 整数として `std::atoi` で変換される引数 |

## 役割

`--tokens` で与えた prompt の後に生成する token 数を設定します。これは Qwen3.6 専用 parser の option です。通常の engine parser と区別して `qwen36/` に置く索引の scope と一致します。`strata` は `--model` または `--native` で指定された GGUF の architecture が `qwen35moe` の場合にこの parser へ引数全体を渡します。独立 executable `strata-q36` も同じ parser を呼びます（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`、`src/qwen35/q36_engine.cu:3735-3743`）。

## 使い方

Qwen3.6 model の token ID を指定して 64 token を生成する例です。

```sh
strata --model /path/to/qwen36.gguf --tokens 1,2,3 --n 64
```

この parser は `--model` と `--native` を同じ model 値として受理し、単独起動の usage は `strata-q36 --model GGUF ... --tokens IDS [--n 64]` を示します（`src/qwen35/q36_engine.cu:3748-3760,3789-3794`）。実行例の token ID と model path は形式を示す仮値です。

## 値と既定値

- `--n` の省略時は `n_gen = 64` です（`src/qwen35/q36_engine.cu:3737`）。
- 値は `std::atoi` で変換され、正数のみといった範囲検証は見当たりません。数値に変換できない値は `atoi` の規則により 0 になります。値を省略すると `next()` が `strata-q36: --n needs a value` を stderr に出して `exit(2)` します（`src/qwen35/q36_engine.cu:3744-3746,3758-3760`）。
- `--max-new` も `n_gen` に代入します。両方を複数回指定したときは parse 順に同じ変数が更新されるため最後の指定が残ります（`src/qwen35/q36_engine.cu:3750,3758-3760`）。
- `--force IDS` が空でない場合、option の parse 順にかかわらず、後段で `n_gen` は forced ID の個数 + 1 に設定されます（`src/qwen35/q36_engine.cu:3760,3916-3918`）。

## 実行時の動作

prompt は `--tokens` の ID 列から作られ、prompt 自体の処理後に `n_gen` 回の greedy token 生成を行います。生成 ID は stdout の `gen:` 行に出て、prompt と生成の時間・token 数は stderr に出ます（`src/qwen35/q36_engine.cu:3916-3917,3931-3933,3960-3978`）。

`--mtp N` で MTP が有効な model かつ `--force` が空、`--dump-full-logits` が未指定の場合は speculative MTP 経路が使われます。その経路でも `n_gen` が上限として参照され、最後に出力 vector をその長さにそろえます。それ以外は通常の逐次 greedy loop で `n_gen` 回まで生成します（`src/qwen35/q36_engine.cu:3935-3958,3960-3970`）。

`--serve` は `serve(E)` に分岐し、生成上限はプロトコルの各 `GEN <max_new>` request から取得します。benchmark mode は `--bench-pp` / `--bench-tg` の値で実行し、どちらも `n_gen` を使いません。従って parser 上は `--n` が読まれても、これらの mode では `--n` による上限設定にはなりません（`src/qwen35/q36_engine.cu:3782-3788,3888-3915`。serve request の解析と上限判定は同ファイル `:3435-3506,3625-3638`）。

## 適用条件と副作用

- `--n` の生成 loop は `--tokens` mode のみです。`--tokens` が空なら `--serve` または `--bench-pp` も必要として stderr にエラーを出し、終了コード 2 で戻ります（`src/qwen35/q36_engine.cu:3916-3918`）。
- `--n` に正数・context 残量以内という validation は見当たりません。通常生成 loop は `n_gen` 回を回し、途中で追加 token を `Engine::process` に渡しますが、serve request にある prompt + max_new の context 超過拒否と同等のチェックはこの単発 loop にはありません（`src/qwen35/q36_engine.cu:3960-3970` と serve の `:3495-3507`）。context に近い prompt では `--n` を残り context 以内にしてください。具体的な範囲外時の挙動はこの調査では実行確認していません。
- 0 は通常 loop を 0 回にし、空の `gen:` 行を出す挙動です。負数も通常 loop は 0 回になります。一方、MTP 経路では `gen.resize((size_t)n_gen)` を通るため負数が巨大な `size_t` に変換され、割当例外等を起こす可能性があります。この入力は指定しないでください（`src/qwen35/q36_engine.cu:3940-3951,3960-3974`）。
- `--n` 自体はファイルや環境変数を変更しません。`--dump-full-logits` 等を併用する場合のファイル出力は別 option の副作用です。

## 出力とエラー

値欠落は stderr に診断して `exit(2)`、未知 option は usage を stderr に出し終了コード 2 です。model が未指定の場合も stderr に `--model is required` を出して 2 を返します（`src/qwen35/q36_engine.cu:3744-3746,3789-3798`）。成功時の token ID 列は stdout、計時行は stderr です（`src/qwen35/q36_engine.cu:3951-3957,3971-3978`）。

## 根拠

- `src/program/generate.cpp:2393-2407` — GGUF architecture を見て Qwen3.6 family を専用 parser へ振り分ける箇所。
- `src/qwen35/q36_engine.cu:3735-3798` — Qwen3.6 parser、既定値、`--n` / `--max-new`、値欠落・未知 option・model validation。
- `src/qwen35/q36_engine.cu:3888-3918` — serve/benchmark/token mode の分岐と `--force` による上書き。
- `src/qwen35/q36_engine.cu:3935-3978` — MTP と通常生成の loop、token ID 出力。
- `src/qwen35/q36_engine.cu:3435-3507,3625-3638` — serve protocol の request 別 `max_new`、範囲・context 判定。
- `src/qwen35/q36_main.cpp:1-5` — `strata-q36` が同じ `run()` parser を呼ぶ entry point。

調査は指定 revision のソースに限定しました。既存の同一 revision バイナリで `--help` は実行しておらず、Release 配布物の有無や実行時の context 超過挙動も確認していません。
