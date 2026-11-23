# `strata-hy4-metal --top-k`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner、トップレベル） |
| オプション | `--top-k` |
| 別名 | なし |
| 値 | 整数。parser は `atoi` で読み取る。実サンプリングでは有効 K を 1〜64 に制限する |

## 役割

オフライン生成のサンプリングで、確率分布を作る前に候補トークンを logit 上位 K 個に絞ります。既定の温度は 0（greedy）なので、`--top-k` 単独では確率サンプリングに切り替わらず、結果に作用しません。確率サンプリングには通常 `--temp` で正の温度も指定します。

## 使い方

```sh
# prompt.ids の token ID 列から生成し、温度付きサンプリングの候補を上位 40 個にする
strata-hy4-metal --model SQ64.strata --tokens prompt.ids --gen 64 --temp 0.7 --top-k 40
```

## 値と既定値

- 省略時は `SampleOpts::top_k` の既定値 64 です。CLI は `atoi` の結果をそのまま設定し、範囲検査や専用エラーは行いません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502-1506,1567-1570`、`engine/src/hy4flash/metal/hy4_metal_spec.h:15-24`）。
- 実サンプリングで使う K は `min(max(1, top_k), 64)` です。したがって 0 以下は 1、64 超は 64 として扱われます（`engine/src/hy4flash/metal/hy4_metal_serve.h:175-178`、`engine/src/hy4flash/metal/hy4_metal_spec.h:49-60,105-120`）。語彙数または speculator の候補数が 64 未満なら、候補数もそれ以下になります。
- 非数値文字列は `atoi` により 0 として扱われ、サンプリング経路では K=1 相当になります。整数でない形式や範囲外値を拒否する parser validation はありません（同 `hy4_metal_main.cpp:1569`、同 `hy4_metal_serve.h:175-178`）。

## 実行時の動作

CLI 値は `cli_samp.top_k` に格納されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1567-1570`）。オフライン生成では、温度が 0 以下で penalty もない場合 `cli_prob` が false となり、greedy の argmax 経路を使います。このため既定状態では `--top-k` は無視されます（`engine/src/hy4flash/metal/hy4_metal_spec.h:15-24`、同 `hy4_metal_main.cpp:1818-1827,1835-1843`）。温度を正にすると確率分布を構築し、`--top-k` が候補選択に使われます。logit の上位 K を選んだ後、温度 softmax、`--min-p`、`--top-p` の順で絞り込みます（`engine/src/hy4flash/metal/hy4_metal_serve.h:175-204`、`engine/src/hy4flash/metal/hy4_metal_spec.h:49-95`）。DFly2 speculative decode が有効な場合も、確率経路では `cli_samp` が `Spec::run` に渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1764,1911-1914,1929-1938`）。

`--serve` では起動時の `cli_samp` は `ServeOpts` に渡されず、各 `GEN` 要求の `top_k=N` が要求ごとの値になります。サーバープロトコル側はその値を 1〜64 に clamp します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1656,1674`、`engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,91-94,121-132`）。従って `--serve --top-k N` は要求の sampling 値を設定しません。

## 適用条件と副作用

効果があるのは生成時に確率サンプリングが行われる場合です。prefill のみ、`--gen` を伴わない実行、または greedy 経路ではサンプリング候補を変更しません。オプション自体はファイルやネットワークを操作せず、生成に使う候補数を変えます。Metal runner の parser は値引数の存在確認を行わず `argv[++i]` を読むため、値を省略した呼び出しの挙動は安全に定義されていません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1569`）。

## 出力とエラー

数値の範囲外や数値として解釈できない値に対する専用エラー・警告はありません。値はサンプリング処理で clamp されます。`--top-k` 自体による stdout/stderr 出力はありません。値引数の欠落は parser で検証されず、通常の入力エラーとして扱われる保証もありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1569`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506,1567-1571` — Metal runner の引数 parser と `cli_samp` の生成。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:15-24,49-95,97-135` — sampling option の既定値、K の clamp、通常／候補分布の処理順。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1818-1844,1911-1914,1929-1938` — greedy／確率サンプリングの分岐と speculative decode への option 転送。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674`、`engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,91-94,121-132,162-204` — `--serve` 起動設定と要求ごとの `top_k` 解釈・サンプリング。
- 索引 [`docs/cli/README.md`](../../README.md) の `strata-hy4-metal` 節（`strata-hy4/metal`）に `--top-k` があり、指定パスと command scope が一致することを確認。
