# `--no-graph`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 family 選択時）または `strata-q36` |
| オプション | `--no-graph` |
| 別名 | なし（`--no-token-graph` も同じ内部フラグを変更するが、parser 上は別のオプション） |
| 値 | 取らないフラグ |

## 役割

Qwen3.6 エンジンが decode 等で CUDA graph を使わないようにします。通常は graph を使う設定で始まり、このフラグを指定すると `Engine::use_graph` が false になります。モデル family による `strata` の振り分けと、単独の `strata-q36` 実行のどちらにも適用されます（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3742`）。

## 使い方

```sh
strata --model /models/qwen3.6.gguf --tokens 1,2,3 --n 8 --no-graph
```

単独 executable を使う場合:

```sh
strata-q36 --model /models/qwen3.6.gguf --tokens 1,2,3 --n 8 --no-graph
```

`--tokens` はこの実行例の入力トークン列です。実際の GGUF ファイルのパスに置き換えてください。

## 値と既定値

値は不要です。parser は `--no-graph` を見つけると内部の `graph` boolean を false にし、初期値は true です。数値・範囲の validation はありません。繰り返し指定しても同じ false を再設定します（`src/qwen35/q36_engine.cu:3737-3742,3765`）。

## 実行時の動作

`Engine` の `use_graph` に parser の値が渡されます。graph 実行 helper は `use_graph` が false のとき、capture / instantiate / graph launch の経路を通らず、同じ処理本体をそのまま呼びます。したがって、このフラグは CUDA graph の利用を切り替えます。GPU 演算全体や CUDA の利用を無効にするものではありません（`src/qwen35/q36_engine.cu:2368-2379,3817-3818`）。

単一トークン decode、batch window、speculative verify など graph helper を通る処理が対象です（`src/qwen35/q36_engine.cu:2451-2454,2504-2507,2541-2544,2734-2738`）。一方、複数トークンの prompt chunk は元から `forward(..., false, false)` で eager 実行されるため、このフラグによる切り替え対象ではありません（`src/qwen35/q36_engine.cu:2463-2478`）。warmup は既定で実行されますが、graph が無効な状態で行われます。warmup 自体を省略するのは別の `--no-warmup` です（`src/qwen35/q36_engine.cu:3882-3889`）。

## 適用条件と副作用

Qwen3.6 の専用 parser に渡されたときだけ有効です。`strata` は `--model` / `--native` の GGUF header から family を判定し、Qwen3.6 family の場合にこの parser へ委譲します（`src/program/generate.cpp:2393-2407`）。

hybrid expert mode では main layers の host 処理が各 layer に入るため、コードが `E.use_graph = false` にします。このため、その経路では `--no-graph` を指定しなくても main layer graph は使われません。MTP block の graph も同箇所で常に無効化されます（`src/qwen35/q36_engine.cu:2888-2893`）。

このフラグ自身によるファイル・ネットワーク操作はありません。graph capture が抑止されるため、graph を生成・保持する経路を使わなくなります。性能への影響の方向や程度は、このソース調査だけでは判断できません。

## 出力とエラー

フラグ受理時の専用メッセージや警告はありません。parser は値を要求しません。未知の引数は通常実行では usage を stderr に出して終了コード 2 になります。たとえば `--no-graph false` の `false` はこのフラグの値ではなく、別の未知引数として扱われます（`src/qwen35/q36_engine.cu:3742-3747,3789-3795`）。

graph helper が使う CUDA Runtime API の失敗は `CK` macro が stderr にエラー内容を出して `exit(1)` します。ただし graph を無効にした場合は helper 内の graph API 呼び出しを通りません。他の CUDA 処理の失敗経路は残ります（`src/qwen35/q36_engine.cu:67-74,2368-2379`）。

## 根拠

- parser、初期値、`--no-graph` の設定: `src/qwen35/q36_engine.cu:3735-3747,3765`
- graph の eager / capture 実行分岐: `src/qwen35/q36_engine.cu:2368-2379`
- graph helper を使う decode、batch、verify 経路: `src/qwen35/q36_engine.cu:2429-2454,2494-2507,2509-2544,2729-2738`
- prompt chunk が eager 実行される箇所: `src/qwen35/q36_engine.cu:2463-2478`
- hybrid mode の graph 制御と warmup: `src/qwen35/q36_engine.cu:2888-2893,3882-3889`
- `strata` から Qwen3.6 parser への family switch: `src/program/generate.cpp:2393-2407`
- 単独 `strata-q36` target の生成条件: `CMakeLists.txt:778-794`
