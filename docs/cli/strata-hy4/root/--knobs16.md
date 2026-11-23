# `strata-hy4 --knobs16`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--knobs16` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

CUDA/HIP 版 Hy4-Flash エンジンの offline 実行で、prefill 後の処理が使う線形 GEMV と MoE decode カーネルの対象トークン数 `M` の上限設定を 16 にします。既定上限を越える複数トークンの処理で、より大きな GEMV/decode カーネルの範囲を使わせたい場合の調整用です。`M=1` の通常の greedy decode は、確認した既定上限（4 または 16）より小さいため、このフラグだけで通常の1トークン decode の経路が変わるとは限りません。

## 使い方

```sh
# tokens.txt の token ID 列を入力して生成する offline 実行
strata-hy4 --model model.strata --tokens tokens.txt --gen 32 --knobs16
```

モデル名・入力ファイル名は例です。ソース上の offline 起動構文は `--model` と `--tokens` を受け付け、`--gen` は生成数を指定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:401-402,484-488,613-615`）。

## 値と既定値

値を取りません。引数 parser は `--knobs16` を見つけると `knobs16 = true` にし、同じフラグを繰り返しても同じ状態です。フラグを省略した場合は `false` のままです（`engine/src/hy4flash/run/hy4_main.hip.cpp:374-375,434`）。値を要求する分岐はなく、直後に別の引数があれば次の parser 反復で通常どおり解釈されます。

## 実行時の動作

offline の prompt prefill と結果出力の後、decode に入る直前に、フラグが有効なら `skd::lin_gemv_max_m()` と `skd::moe_dec_max_m()` をそれぞれ 16 に設定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:785-792`）。線形レイヤーは `M` が設定上限以下かつ 16 以下なら GEMV 経路を選び、上限を越える場合はビルド条件に応じた GEMM 等の経路へ進みます（`engine/src/hy4flash/run/skhy4.hip.h:47-80`）。MoE 側は `M` が設定値と `HY4_MOE_DEC_MAXM` の両方以下なら decode カーネル群を選びます（`engine/src/hy4flash/run/skmoe.hip.h:1470,1473-1480,1510-1529`）。

## 適用条件と副作用

- 効果は root の CUDA/HIP 実装で確認したものです。Metal と SYCL は索引上で別入口・別 parser として管理されており、この文書の対象ではありません（`docs/cli/000_cli_tools.md:11`、`docs/cli/README.md:1277-1281,1358-1361,1452-1455`）。
- 線形 GEMV の上限既定値は、`!HY4_MMA` または RDNA2 の場合 16、それ以外は 4 です。MoE decode の既定値も同じ条件分岐です（`engine/src/hy4flash/run/skhy4.hip.h:27-32`、`engine/src/hy4flash/run/skmoe.hip.h:1473-1480`）。このフラグは両方を 16 に上書きします。
- ただし CUDA ビルドでは MoE decode カーネルのハード上限 `HY4_MOE_DEC_MAXM` が 8 なので、`--knobs16` を指定しても MoE の `M=9..16` は同カーネル条件を満たしません。非 CUDA ではこの上限は 16 で、実際の分岐はさらに `HY4_MMA` などのビルド条件に依存します（`engine/src/hy4flash/run/skmoe.hip.h:1473-1479,1510-1535`）。
- `--serve` の分岐では `ServeOpts` にこのフラグを渡さず、そのまま `hy4_serve_main` を呼びます。そのため serve 実行での効果は確認できません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611`）。
- `--trace-m` の診断処理はこのフラグの有無にかかわらず両上限を 16 にし、`--parity-m` は比較処理内でまず 4、次に比較モードごとに 4/16 を明示設定します。`--ab` の経路では `--spec-exact` がある場合に 16 を設定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:793-800,821-840,859-862,914-925`）。
- このフラグ専用のファイル・ネットワーク操作や出力はありません。変更するのはプロセス内のカーネル選択上限です。性能向上や数値結果の同一性は本ソースだけからは保証できません。

## 出力とエラー

このフラグの受理・適用時に専用メッセージは出力されません。値の検証もありません。未知の引数は parser が `unknown arg <引数>` を stderr に出し、終了コード 2 で戻ります。また、`--model` がない場合は usage を stderr に出して終了コード 2 ですが、いずれも `--knobs16` 固有のエラーではありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505,613-615`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:374,434` — 既定状態と parser 登録。値なしで真にする。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:785-800` — prefill 後の設定と、trace 経路の独立設定。
- `engine/src/hy4flash/run/skhy4.hip.h:27-32,47-80` — 線形 GEMV 上限の既定値と M によるカーネル経路。
- `engine/src/hy4flash/run/skmoe.hip.h:1470-1480,1510-1535` — MoE 上限・ビルド別上限とカーネル選択。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611` — serve 経路へ当該フラグが転送されないこと。
