# `--no-warmup`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 family parser、または `strata-q36` |
| オプション | `--no-warmup` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

Qwen3.6 engine 起動時に通常実行される GPU warmup を省略します。`strata` は `--model` / `--native` で指定された GGUF の family が `qwen35moe` の場合に Qwen3.6 専用実装へ引き渡します。CMake では同じ実装を `strata-q36` executable としても生成します（`src/program/generate.cpp:2393-2407`、`CMakeLists.txt:782-792`、`src/qwen35/q36_main.cpp:1-5`）。

## 使い方

通常の token generation の例です。`IDS` は実際の入力 token ID をカンマ区切りで指定します。

```sh
strata --model ./model.gguf --tokens IDS --no-warmup
```

同じフラグは `--serve` と `--bench-pp` / `--bench-tg` の起動にも適用されます。専用 executable では `strata-q36 --model ./model.gguf ... --no-warmup` と指定します。`--no-warmup` は parser が引数全体を走査する間に受理され、後続の実行モード分岐より前に反映されます（`src/qwen35/q36_engine.cu:3735-3779,3882-3890`）。

## 値と既定値

- 値を取りません。parser はこの引数を見つけると `warm = false` にします（`src/qwen35/q36_engine.cu:3739-3742,3765-3767`）。
- 省略時は `warm = true` のままなので warmup が実行されます（`src/qwen35/q36_engine.cu:3739,3888`）。
- 数値範囲などの validation はありません。複数回指定しても同じ `false` を設定するだけです（`src/qwen35/q36_engine.cu:3742-3795`）。
- `--no-warmup` の次に値らしい引数を置いても、その値をこのフラグが消費することはありません。通常の generation / benchmark 経路では未知引数として usage を stderr に出し終了コード 2 になります。`--serve` 経路では未知の `--...` 引数を警告して無視する別処理があります（`src/qwen35/q36_engine.cu:3782-3795`）。

## 実行時の動作

model load、`Engine::init`、expert placement、初期 `E.reset()` を終えた後、`warm` が真の場合に限り `E.warmup()` を呼びます。したがってこのフラグはモデル読込や engine 初期化、最初の reset を省略しません。warmup 呼び出し後に server、benchmark、または token generation の処理へ進みます（`src/qwen35/q36_engine.cu:3811-3817,3863-3866,3882-3890`）。

省略される warmup は、token ID 198 の filler を使った `tmax` token の prompt、必要な場合は最小 GEMM chunk の追加 prompt、1 token decode を実行し、`--mtp N` の有効な draft 数がある場合は speculative step も実行します。最後に stream を同期し、hybrid routing score とカウンターをクリアして engine state を reset します。通常は stderr に所要時間を含む `strata-q36: warmed up in ...` を出力します（`src/qwen35/q36_engine.cu:2752-2778`）。

warmup 中は `warming` フラグにより hybrid expert rebalance が無効になります。warmup の routing score は最後に消去されるため、この処理が warmup 中の routing を使って expert slot を再配置することはありません（`src/qwen35/q36_engine.cu:2756-2777,2296-2301`）。

## 適用条件と副作用

このフラグは Qwen3.6 専用 parser の動作です。`strata` では GGUF header の model family が `qwen35moe` と判定されたときだけこの parser が使われます（`src/program/generate.cpp:2393-2407`）。通常 engine の別 parser に同じ意味で適用されるとは確認できません。

指定すると起動時の追加 GPU forward 実行、warmup 後の reset、および warmup 完了時間の stderr 表示を飛ばします。一方、engine 初期化時の CUDA/GPU memory setup や model load は引き続き行われます（`src/qwen35/q36_engine.cu:1348-1365,1502-1509,3811-3817,3882-3889`）。実装コメントは warmup を初回 prompt で使う GPU code object、BLAS kernel、decode graph の初回生成を先に行うための処理と説明しています。そのため省略時には初回 request / benchmark の最初の測定にそれらの初回実行コストが含まれる可能性がありますが、この文書では性能差を測定していません（`src/qwen35/q36_engine.cu:2752-2755`）。

## 出力とエラー

このフラグ自体の成功・失敗メッセージはありません。warmup を実施する場合の stderr 完了行は省略されます。model load、GPU 初期化、後続 generation / serve / benchmark の失敗条件はこのフラグによって取り除かれません（`src/qwen35/q36_engine.cu:3811-3817,3882-3890`）。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3795` — parser の既定値、値なしフラグ、未知引数と usage / 終了コード。
- `src/qwen35/q36_engine.cu:2752-2778` — warmup の目的、実行内容、状態 reset、stderr 出力。
- `src/qwen35/q36_engine.cu:2296-2301` — warmup 中の hybrid expert rebalance 抑止。
- `src/qwen35/q36_engine.cu:3811-3817,3863-3866,3882-3890` — model load・初期化・placement の後で warmup を条件実行し、各実行モードへ進む順序。
- `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:782-792` — family dispatch と専用 executable。

調査は指定 revision の checkout 内の parser と呼び出し経路を対象としました。同 revision の CLI `--help` および Release 配布物は照合していません。
