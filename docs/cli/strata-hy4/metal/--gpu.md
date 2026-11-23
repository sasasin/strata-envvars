# `strata-hy4-metal --gpu`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | 次の引数を1個消費する文字列。Metal runner では内容を検証・解釈しない |

## 役割

このビルドでは `--gpu` は互換的に受理されるだけで、GPU 選択には使われない。指定しても stderr に未使用の警告を出し、Metal runner はシステム既定の Metal デバイスで続行する。

## 使い方

```sh
# --gpu の値は選択に反映されず、未使用の警告が出る
strata-hy4-metal --model model.strata --gpu 1 --load-only
```

## 値と既定値

`--gpu` の直後の引数を1個消費し、その文字列を警告に表示する。整数変換、範囲検査、空文字や値の形式の検証は行わない。省略時はこの警告経路に入らない。複数回指定した場合は各指定について警告する。値を省略した場合に備えた明示的な引数数チェックは parser にないため、その場合の動作は保証できない。`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1603`。

## 実行時の動作

parser は `--gpu` を `--kv` などと同じ未使用オプション分岐で扱い、値を読み取って `[args] --gpu <値>: not used by the Metal runner` を stderr に出すだけで、GPU 番号を保存しない。以後の Metal コンテキスト生成は引数に依存せず `MTLCreateSystemDefaultDevice()` を呼び出す。このため `--gpu` はデバイス選択を変更しない。`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603,1615-1616`、`engine/metal/src/mtl_rt.mm:139-145`。

## 適用条件と副作用

対象は `strata-hy4-metal`（Metal runner）である。`--gpu` の指定自体は処理を止めず、通常のモデル読み込み・推論または `--load-only` の経路へ進む。Metal デバイスが得られない場合は、オプション値とは無関係に `mtl::Context` が `mtl: no Metal device` を stderr に出して終了コード 2 で終了する。`engine/metal/src/mtl_rt.mm:139-145`。

## 出力とエラー

指定時の stderr 警告は `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603` にある。これだけを理由に終了コードは設定されず、parser は後続処理を続ける。`--model` が最終的に空なら usage を stderr に出し終了コード 2、モデル読み込みに失敗すれば `load: ...` を stderr に出し終了コード 1 となる（同ファイル `1611-1622`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506,1603` — Metal runner の引数解析と `--gpu` の値消費・未使用警告。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1622` — model 必須チェック、デバイス情報の表示、モデル読み込み失敗経路。
- `engine/metal/src/mtl_rt.mm:139-145` — システム既定 Metal デバイスの取得と、デバイスがない場合の終了処理。
- `docs/cli/README.md:1387-1450` — `strata-hy4-metal` のコマンド階層と `--gpu` リンク（索引照合のみ。動作根拠には使用していない）。
