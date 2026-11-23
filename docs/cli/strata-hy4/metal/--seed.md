# `strata-hy4-metal --seed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--seed` |
| 別名 | なし |
| 値 | 10進整数。`uint64_t` に変換される |

## 役割

確率サンプリングを行うオフライン生成または Metal server の各リクエストに乱数 seed を与える。オフラインでは DFly2 speculative 生成など、サンプリング経路で使われる。greedy 生成では seed はトークン選択を変えない。

## 使い方

```sh
# DFly2 が利用可能なモデルで、温度サンプリングを行うオフライン生成
./strata-hy4-metal --model SQ64.strata --tokens ids.txt --gen 64 --draft dfly2 --temp 0.7 --seed 1234
```

サーバーモードでは起動引数の `--seed` ではなく、標準入力の各要求に `seed=<整数>` を指定する。

```text
GEN 64 temperature=0.7 seed=1234 1,2,3
```

## 値と既定値

値は必須で、parser は `strtoull(値, nullptr, 10)` の結果を `uint64_t` に格納する。parser に明示的な範囲・書式検査はなく、不正文字列の拒否や範囲外値の扱いを定める独自 validation もない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1571`）。既定値は `0`（`engine/src/hy4flash/metal/hy4_metal_spec.h:15-24`）。

## 実行時の動作

- オフラインの sampler は `--temp`、`--top-p`、`--top-k`、`--min-p` などとともに `SampleOpts` に保存される。既定温度 `0` は greedy を意味し、`--seed` 単独ではサンプリングを有効にしない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1567-1571`; `engine/src/hy4flash/metal/hy4_metal_spec.h:15-24`）。
- DFly2 が使える生成条件では、温度が正または penalty が有効な場合に seed を sampler の乱数 generator に渡す。非ゼロ seed の確率的 speculative 経路では適応状態を初期化し、時間計測に依存しない再現性を意図した分岐を使う（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762,1818-1827,1934-1938`; `engine/src/hy4flash/metal/hy4_metal_spec.h:716-732`）。
- オフライン生成で seed が `0` の場合、乱数 generator には固定値 `0x57A7A123456789AB` が使われる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1820,1911-1912,1935-1936`）。
- DFly2 speculative 生成が無効になった場合（drafter がない、chunk が 16 未満、`--all-logits`、画像入力など）、通常の `--gen` 分岐は argmax を使い、sampler の seed は参照しない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1760-1762,1944-1966`）。
- `--serve` の場合、起動時の `cli_samp` は `ServeOpts` に含まれず、各 `GEN` 行の `seed=` が要求の sampler に設定される。要求 seed が `0` または省略時は `std::random_device` から generator を初期化する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1656`; `engine/src/hy4flash/metal/hy4_metal_serve.h:91-97,121-145,467-468`）。

## 適用条件と副作用

オプション自体は Metal runner の引数 parser にあります。サンプリングの結果に作用するのは確率的生成経路のみです。seed が非ゼロでも greedy 経路や、speculative が使えず通常 argmax となる経路の出力は seed によって変わりません（`engine/src/hy4flash/metal/hy4_metal_spec.h:22-24,716-724`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1818-1827,1944-1966`）。

サーバーは要求ごとに乱数 generator を初期化するため、セッションをまたいだ状態の共有はこのコードでは確認できません（`engine/src/hy4flash/metal/hy4_metal_serve.h:467-468`）。

## 出力とエラー

`--seed` 専用の validation error や警告出力は確認できません。オフラインの speculative 実行で生成処理が `error` を返す場合は `spec: <内容>` を stderr に出して終了コード `1` になりますが、seed の値に起因する専用経路ではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1934-1938`）。サーバーの `GEN` 行に含まれる `seed=` は `strtoull` で読み込まれ、エラー応答を返す明示的な seed validation はありません（`engine/src/hy4flash/metal/hy4_metal_serve.h:121-145`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1504,1567-1571` — CLI parser と sampler の初期値。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:15-24,29-66,154-165` — sampler の既定値、greedy 判定、分布からの抽選。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762,1818-1844,1898-1944` — speculative 適用条件、seed 使用、および通常生成への分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1944-1976` — speculative が使われない通常 `--gen` の argmax と出力。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:91-97,100-145,467-468,505-536` — server 要求単位の seed 解析・乱数 generator・サンプリング。

