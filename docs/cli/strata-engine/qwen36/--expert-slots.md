# `--expert-slots`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | Qwen3.6 専用 engine parser（`strata-q36`、または Qwen3.6 GGUF を選んだ `strata`） |
| オプション | `--expert-slots N` |
| 別名 | なし |
| 値 | 整数。正数は各層の GPU 上の routed-expert slot 数を指定。0 以下は自動配置扱い |

## 役割

Qwen3.6 の routed expert を各層で何個 GPU VRAM に常駐させるかを指定します。指定数を超える expert は、hybrid 配置時にホストメモリと CPU expert pool を使って処理されます。これは同時に推論する会話 slot 数を指定する `--batch` / `--slots` とは別のオプションです（`src/qwen35/q36_engine.cu:2898-2899, 3740-3781`）。

`strata` は `--model` または `--native` の GGUF family を調べ、`qwen35moe` なら Qwen3.6 専用 `strata::qwen35::run` に切り替えます。独立 executable の `strata-q36` も同じ関数を呼びます（`src/program/generate.cpp:2393-2408`、`src/qwen35/q36_main.cpp:1-4`、`include/strata/qwen35/engine.hpp:1-11`）。

## 使い方

```sh
strata-q36 --model /models/qwen36.gguf --expert-slots 8 --tokens "1,2,3"
```

同じ Qwen3.6 family なら `strata --model ...` にも指定できます。ビルドによって `strata-q36` と family switch が有効になるのは gfx906 以外の対応 GPU build です（`CMakeLists.txt:776-794`）。

## 値と既定値

- 既定値は `0` です。parser は `int expert_slots = 0` と初期化し、引数値を `std::atoi` で整数化します（`src/qwen35/q36_engine.cu:3737-3741, 3778-3781`）。
- `N > 0` の場合、実際の slot 数 `S` は `min(モデルの expert 数, N)` です。したがってモデルの expert 数より大きい値は上限に丸められます（`src/qwen35/q36_engine.cu:2898-2899`）。
- `N <= 0` は自動配置扱いです。正数でない場合は全 expert を VRAM に置けるかを判定し、収まらなければ VRAM slot と CPU pool を使う hybrid 配置を選びます（`src/qwen35/q36_engine.cu:2824-2826, 2848-2866`）。
- parser に明示的な範囲検査はありません。数値でない文字列は `atoi` により `0` となり、自動配置扱いになります。複数回指定した場合はループ中で同じ変数に代入されるため、最後の値が残ります（`src/qwen35/q36_engine.cu:3742-3747, 3780`）。
- 値を省略すると `next()` が `strata-q36: --expert-slots needs a value` を stderr に出し、終了コード `2` で終了します（`src/qwen35/q36_engine.cu:3744-3746`）。

## 実行時の動作

正数を指定すると、自動の「全 expert が VRAM に収まる」経路と MTP 専用 hybrid 分岐を通らず、hybrid 配置処理で明示数を各層の slot 数として使います。各層の最初の `S` 個の expert を最初の GPU slot に配置し、残りの expert blob はホストメモリに保持します（`src/qwen35/q36_engine.cu:2824-2826, 2848-2866, 2898-2903, 2934-2965`）。そのため、正数を expert 数以上に指定しても自動の全 VRAM 配置経路とは異なり、hybrid 初期化経路に入ります。

hybrid 経路は GPU と CPU pool を併用し、CPU pool が利用できる build では、GPU slot にない expert を CPU 側で処理します。prompt chunk の expert 読み出しには必要に応じて staging buffer も使います（`src/qwen35/q36_engine.cu:2881-2895, 2975-3007`）。`STRATA_NATIVE_EXPERTS=OFF` で CPU pool を含まない build では、expert が VRAM に収まらない場合に配置を拒否します（`src/qwen35/q36_engine.cu:2881-2886`、`CMakeLists.txt:785-789`）。

`--expert-vram` が設定する VRAM budget は slot の配置可能性チェックには引き続き使われますが、正の `--expert-slots` が選ぶ slot 数 `S` 自体は `min(n_expert, N)` であり、その budget から自動調整されません。必要量が空き VRAM を超えると初期化に失敗します（`src/qwen35/q36_engine.cu:2811-2813, 2896-2918`）。

## 適用条件と副作用

- Qwen3.6 (`qwen35moe`) の専用 parser に適用されます。`strata` で他 family を指定した場合は通常 engine parser に進むため、この専用 parser の値・挙動を一般 engine の設定としては適用できません（`src/program/generate.cpp:2393-2408`）。
- 明示正数は VRAM 配置の要求数です。VRAM が不足しても指定値を自動的に縮小する処理はなく、hybrid 用 buffer と slot の必要量チェックでエラーになります（`src/qwen35/q36_engine.cu:2904-2918`）。
- hybrid 配置では全対象 expert を pinned host memory に確保しようとし、pin に失敗した場合は通常の `malloc` に fallback します。fallback のホストメモリ確保も失敗すると配置エラーになります（`src/qwen35/q36_engine.cu:2920-2932`）。
- 通常の起動処理では配置成功後に warmup を実行します。`--no-warmup` を併用した場合は省略されます（`src/qwen35/q36_engine.cu:3765-3766, 3863-3889`）。

## 出力とエラー

- hybrid 配置成功時は、GPU 上の slot 数、ホストメモリ量と pinned/pageable の別、CPU 処理と staging に関する要約を stderr に出力します（`src/qwen35/q36_engine.cu:3002-3006`）。正常終了時の hybrid 集計も stderr に出ます（`src/qwen35/q36_engine.cu:3875-3879`）。
- GPU の空き VRAM に slot と hybrid buffer が収まらない場合は `not enough VRAM left for the hybrid experts' buffers and slots ...` を stderr に出し、呼び出し側が終了コード `1` で終了します。指定 slot 数が正数の場合、メッセージには `use fewer --expert-slots` が含まれます（`src/qwen35/q36_engine.cu:2912-2918, 3863-3866`）。
- CPU pool のない build で全 expert が VRAM に収まらない場合は、CPU expert pool がない旨を stderr に出し、配置失敗として終了コード `1` になります（`src/qwen35/q36_engine.cu:2881-2886, 3863-3866`）。

## 調査範囲

ソース checkout の parser、family switch、配置処理、CMake の build 条件を確認しました。同一 revision の既存 CLI help や Release 配布物は確認していません。したがって、個別の配布物にこの option が含まれるかはここでは断定しません。
