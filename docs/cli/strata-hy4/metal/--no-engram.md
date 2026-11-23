# `--no-engram`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--no-engram` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

外部 Engram shard を開かず、推論時の Engram lookup と Engram layer の計算を無効にする。オフライン実行と `--serve` に適用される。Metal runner では `--engram` の指定があっても、このフラグが有効なら shard のパスを空にして初期化へ渡す。

## 使い方

```sh
# Engram shard を開かず、トークン列を推論する
strata-hy4-metal --model model.strata --tokens ids.txt --no-engram

# Metal server を Engram なしで起動する
strata-hy4-metal --model model.strata --serve --no-engram
```

## 値と既定値

値は不要で、指定すると真偽値 `no_engram` が `true` になる。既定値は `false`。同じフラグを重ねて指定しても有効状態は変わらない。`--engram <path>` と併記した場合も、引数の順序にかかわらず `--no-engram` が優先される。parser はフラグ固有の値検証を行わない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1491,1504-1519`）。

## 実行時の動作

parser はこのフラグを `no_engram` に記録する。server モードでは `ServeOpts` に値を渡し、server 起動側で `no_engram` が真なら空の shard パスで runner を初期化する。server の spill fingerprint にも空パスを使う。オフライン実行でも同様に空パスを `Runner::init` へ渡す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1647,1762-1765`; `engine/src/hy4flash/metal/hy4_metal_serve.h:240-242,273-276`）。

空パスの場合、`Runner::init` は外部 shard の `eio.open` を呼ばず、`engram_ready` を設定しない。その後の chunk 処理は `mo >= 0 && engram_ready` の条件を満たさないため Engram の準備・prefetch・layer 計算を行わない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:681-686,1297-1320`）。ただし runner 初期化では、外部 shard の有無にかかわらずモデル manifest から Engram metadata を読み込み、Engram layer 用のモデルテンソルと補助 buffer を準備する。このため、フラグはモデル内 metadata の読み込み自体を省略するものではない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:681-705`）。

## 適用条件と副作用

Metal runner 専用のフラグで、CUDA/HIP や SYCL runner の挙動をこの文書の対象には含めない。外部 Engram shard を開かないため、その shard のページ読み込みも発生しない。オフライン実行の終了時には Engram 統計行が出力されるコードがあるが、この設定では Engram 処理を通らない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1982-1984`）。

## 出力とエラー

`--no-engram` 自体に専用の出力やエラー経路はない。runner 初期化が失敗した場合、オフライン実行は `init: <理由>` を stderr に出して終了コード 1 を返す。server 実行は protocol 出力に `ERR init: <理由>` を出して終了コード 1 を返す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1762-1765`; `engine/src/hy4flash/metal/hy4_metal_serve.h:240-243`）。Engram metadata はフラグの有無にかかわらず読み込まれるため、その読み込み失敗はこのフラグでも回避されない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:681-682`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1519` — `no_engram` の既定値と parser 登録。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1647` — server モードへの値の引き渡し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1762-1765` — オフライン runner 初期化時の shard パス選択と失敗処理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:681-705` — shard open の条件、metadata 読み込み、Engram 用テンソル準備。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1297-1320` — Engram の chunk 準備と計算を行う条件。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:240-243,273-276` — server 初期化と spill fingerprint における適用。
