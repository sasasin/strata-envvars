# `--gpu`（Qwen3.6 engine）

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 family 経路（`strata-q36` の parser にも同名引数あり） |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | 必須の `LIST`。help ではカンマ区切りの nvidia-smi/PCI index と説明される |

## 役割

通常の `strata` に Qwen3.6 のモデルを指定した実行では、GPU 初期化に先立って可視 GPU の一覧をプロセス環境に設定します。CUDA build では `CUDA_VISIBLE_DEVICES`、HIP build では `HIP_VISIBLE_DEVICES` に値を設定し、同時に `CUDA_DEVICE_ORDER=PCI_BUS_ID` とします。専用 `strata-q36` 実行ファイルにも `--gpu` の parser 分岐はありますが、値を読み飛ばすだけで環境を設定しません。

## 使い方

通常の `strata` から Qwen3.6 モデルを実行する例です。`--native` のモデルファイルから family が判定され、Qwen3.6 の専用 parser に引き渡されます。

```sh
strata --native /models/qwen36.gguf --gpu 0,1 --tokens 1,2,3 --n 16
```

専用 `strata-q36` で実行する場合、`--gpu` 値は device 選択には適用されません。GPU の制限が必要なら、同プロセスを起動する環境側で可視 device を設定してください。

## 値と既定値

- `--gpu` の直後の引数を文字列のまま可視 device 環境変数へ設定します。engine 側のこの処理では、数値・区切り・index 範囲の検証や正規化はしません（`engine/src/program/generate.cpp:3784-3802`）。help の値説明は `engine/src/program/generate.cpp:1215-1217` にあります。
- 値を省略すると専用 parser は `strata-q36: --gpu needs a value` を標準エラーへ出し、終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5350-5352`）。
- `--gpu` を指定しない場合、このオプションによる環境変更はありません。利用できる GPU は起動時環境と CUDA/HIP runtime の可視性に委ねられます。CLI ソースでは未指定時の device 数を独自に設定していません。
- 複数回指定した場合、通常の `strata` の事前走査は最初に見つかった `--gpu` の値だけを環境へ適用して終了します。Qwen3.6 parser は以降の引数も値とともに読み進めますが、後続指定は選択を更新しません（`engine/src/program/generate.cpp:3784-3802`、`engine/src/qwen35/q36_engine.cu:5348-5360`）。

## 実行時の動作

通常の `strata` は、`--native` または `--model` の値から GGUF family を調べて Qwen3.6 (`qwen35moe`) と判定した場合、Qwen3.6 parser に渡します（`engine/src/program/generate.cpp:3804-3818`）。その family 判定より前に `--gpu` を走査し、最初の指定値で可視 device 変数を上書きします。CUDA build は `CUDA_VISIBLE_DEVICES`、`STRATA_USE_HIP` または `STRATA_HIP_GFX906` build は `HIP_VISIBLE_DEVICES` を対象にします。Windows では `_putenv_s`、それ以外では上書きを許可した `setenv` を使います。どちらの build でも `CUDA_DEVICE_ORDER` を `PCI_BUS_ID` に設定します（`engine/src/program/generate.cpp:3781-3802`）。

このため、通常の `strata` 経路では、対象環境変数が未設定または空なら警告せず CLI 値で設定します。空でない既存値と CLI 値が異なる場合は、既存値を示す警告を標準エラーに出して CLI 値で置き換えます。同じ値なら警告は出ません（`engine/src/program/generate.cpp:3792-3801`）。

一方、`strata-q36` の入口は直接 `strata::qwen35::run` を呼びます（`engine/src/qwen35/q36_main.cpp:1`）。この parser は `--gpu` の後続値を `next()` で取得して捨てるだけで、環境変数には反映しません（`engine/src/qwen35/q36_engine.cu:5348-5360`）。従って専用実行ファイルにこの引数を渡しても、GPU 選択効果はありません。

## 適用条件と副作用

- 通常 `strata` の GPU 環境設定は、`strata` の `generate.cpp` にある起動経路でのみ確認できます。HIP build の識別は `STRATA_USE_HIP` / `STRATA_HIP_GFX906` の compile-time 条件です（`engine/src/program/generate.cpp:3788-3801`）。
- プロセス自身の環境を書き換えるため、後続の Qwen3.6 engine 初期化で runtime が参照する可視 device 環境に影響します。環境設定以降に runtime が値をどう解釈するかや、無効な index が runtime でどう扱われるかは、この Strata 側の処理だけからは確定できません。
- 専用 `strata-q36` は値を受理して消費しますが、この引数では環境を書き換えません。直接起動時の GPU 選択をこの CLI option の効果として期待しないでください。

## 出力とエラー

通常 `strata` で既存の可視 device 環境変数が空でなく、CLI 値と異なる場合、標準エラーに `warning: --gpu <LIST> overrides <ENV>=<previous> from the environment` を出します（`engine/src/program/generate.cpp:3792-3794`）。専用 parser で値を省略した場合は前述のエラーを出して終了コード 2 です（`engine/src/qwen35/q36_engine.cu:5350-5352`）。このオプション独自の範囲外 index に対する Strata 側 validation / error 経路は確認できませんでした。

## 根拠

- `engine/src/program/generate.cpp:1215-1217` — `--gpu LIST` の help 表示と説明。
- `engine/src/program/generate.cpp:3781-3802` — 起動時の値走査、CUDA/HIP の対象環境変数、既存値警告、`CUDA_DEVICE_ORDER` と環境変数の設定。
- `engine/src/program/generate.cpp:3804-3818` — モデル family を確認し、Qwen3.6 を専用 parser に引き渡す経路。
- `engine/src/qwen35/q36_main.cpp:1` — 専用 `strata-q36` の入口。
- `engine/src/qwen35/q36_engine.cu:5348-5360` — 専用 parser の必須値処理と `--gpu` 値の読み捨て。
