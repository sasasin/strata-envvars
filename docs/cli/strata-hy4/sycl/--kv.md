# `--kv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL） |
| オプション | `--kv` |
| 別名 | なし |
| 値 | 1 個の文字列。受理される値は `fp16` のみ |

## 役割

SYCL runner が受け付ける KV cache 形式を `fp16` に限定するオプションです。現行実装では指定値を保存せず、`fp16` 以外を拒否するチェックだけを行います。オプションを省略しても KV cache は FP16 で作られるため、`--kv fp16` は形式を切り替えず、明示的に指定しても実行時の設定は変わりません（parser: `engine/src/hy4flash/sycl/sy_main.cpp:144-151`、cache の型とサイズ: `engine/src/hy4flash/sycl/sy_graph.h:538-550`、`engine/src/hy4flash/sycl/sy_mla.cpp:1652`）。

## 使い方

```sh
# SYCL runner の単発実行で受理される値を明示する
strata-hy4-sycl --model model.strata --tokens ids.txt --kv fp16

# server モードでも同じ parser が値を検査する
strata-hy4-sycl --serve --native model.strata --kv fp16
```

## 値と既定値

- `--kv` の直後から次の argv を 1 個読み取り、文字列が厳密に `fp16` と一致するときだけ続行します。大文字小文字の違い、空文字、`q8`、`auto` などは受理されません（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`, `144-151`）。
- 値を省略した場合の選択値を格納する変数はなく、FP16 が標準の cache 実装です。cache は `half*` として確保され、バイト数も `sizeof(half)` を使って算出されます（`engine/src/hy4flash/sycl/sy_graph.h:538-550`、`engine/src/hy4flash/sycl/sy_mla.cpp:1652`）。
- 複数回指定すると、各指定を順に検査します。すべて `fp16` なら通過し、いずれかが異なる値ならその時点で失敗します（`engine/src/hy4flash/sycl/sy_main.cpp:105-115`, `144-151`）。
- 値の形式以外の数値範囲検証はありません。値なしの場合、共通の引数取得処理が `ERR --kv needs a value` を stdout に出し、flush して終了コード 2 で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。

## 実行時の動作

parser は `--serve` の有無による実行経路分岐より前に全引数を走査します。そのため、単発実行と server モードのどちらでも同じ `fp16` 限定チェックが適用されます（`engine/src/hy4flash/sycl/sy_main.cpp:105-115`, `215-248`）。

受理時にはローカル変数 `kv` を比較した後、値を runner や `ServeOpts` に渡しません。従って `--kv fp16` は cache の形式・容量・配置を変更しません。cache の保存先配置は別の `kv_host_above` 閾値と context 長などで決まり、`--kv` との連動はありません（閾値の parser と引き渡し: `engine/src/hy4flash/sycl/sy_main.cpp:164`, `234`, `293`; 配置判定と確保: `engine/src/hy4flash/sycl/sy_graph.h:541-550`）。

## 適用条件と副作用

この記述は `strata-hy4-sycl` の parser に限ります。`strata-hy4` CUDA/HIP や `strata-hy4-metal` は別 parser で、同名オプションの受理値・動作は異なり得ます（索引の scope: `docs/cli/README.md:1452-1478`）。

受理された `--kv fp16` 自体に追加のファイル、ネットワーク、GPU、server 状態変更はありません。実際の KV cache 確保は通常のモデル実行初期化に伴って行われます（`engine/src/hy4flash/sycl/sy_graph.h:535-553`）。

## 出力とエラー

`fp16` 以外を渡すと `ERR --kv <値>: only fp16` を stdout に出し、flush 後に終了コード 2 を返します。単発実行・server モードとも同じ parser 内で拒否されます（`engine/src/hy4flash/sycl/sy_main.cpp:144-150`）。値を省略した場合のエラーは前節のとおりです。

## 根拠

- 索引上のコマンド階層と SYCL parser: `docs/cli/README.md:1452-1478`。
- parser の引数取得、値チェック、エラー出力: `engine/src/hy4flash/sycl/sy_main.cpp:105-115`, `144-151`。
- server / 単発実行へ分岐する位置: `engine/src/hy4flash/sycl/sy_main.cpp:215-248`, `250-294`。
- KV cache の FP16 型確保と配置条件: `engine/src/hy4flash/sycl/sy_graph.h:535-553`。
- cache byte 数に `sizeof(half)` を用いる実装: `engine/src/hy4flash/sycl/sy_mla.cpp:1652`。

`--help` の実行や build・GPU 実行は行っていません。説明は同一 checkout の parser と実装箇所に基づきます。
