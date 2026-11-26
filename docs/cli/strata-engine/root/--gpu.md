# `--gpu`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。usage 表記は `strata generate`） |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU の番号をカンマ区切りで指定する `LIST`。help は `nvidia-smi` / PCI の番号と説明し、省略時は可視 GPU 全てとする。 |

## 役割

エンジンプロセス内で可視 GPU を指定し、CUDA のデバイス順を PCI bus ID 順に設定する。呼び出し元の環境変数を変更するのではなく、エンジン自身の初期化前に `CUDA_VISIBLE_DEVICES`（HIP ビルドでは `HIP_VISIBLE_DEVICES`）を設定する。Qwen3.6 系モデルへ処理を振り分ける場合も、振り分け前に同じ設定を行う。

## 使い方

```sh
# 0 番と 2 番の GPU を選択して生成
strata generate --gpu 0,2 --pack ./pack/full --tokens "1,2,3"
```

## 値と既定値

- 値は `LIST` として1引数で受け取る。help の記述はカンマ区切りの番号である。
- オプションを指定しない場合、このオプションによる可視 GPU の絞り込みは行われず、help 上の既定は「可視な GPU 全て」である。
- `--gpu` の値について、Strata 側に数値・範囲・CSV 形式を検査する処理は確認できなかった。値は文字列のまま可視デバイス環境変数へ設定されるため、受理可能な個々の値や無効値の結果は、このソース範囲からは確定できない。
- 複数回指定した場合、起動前の環境設定ループは最初に見つけた `--gpu` と直後の値で設定し、そこで終了する。後続の指定も引数 parser では値を消費するが、GPU 環境設定には使われない。

## 実行時の動作

`main` は CUDA/HIP を使う処理に入る前に引数列を走査する。`--gpu LIST` があれば、常に `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定し、CUDA ビルドでは `CUDA_VISIBLE_DEVICES=LIST`、HIP ビルド（`STRATA_USE_HIP` または `STRATA_HIP_GFX906`）では `HIP_VISIBLE_DEVICES=LIST` を設定する。Windows では `_putenv_s`、それ以外では `setenv(..., 1)` を使用し、既存値を上書きする。

通常の parser は `--gpu` の次の引数を消費するだけで、別の値変換はしない。Qwen3.6 と判定されたモデルは `strata::qwen35::run` に引数列ごと渡され、同側 parser も `--gpu` の値を消費するだけである。GPU 可視性の設定は振り分け前に済んでいる。

## 適用条件と副作用

- `--gpu` がなければ、このオプションによる環境設定は行われない。
- GPU 可視性環境変数が既に非空で、かつ指定値と異なる場合、stderr に `warning: --gpu ... overrides ...` を出して上書きする。同じ値、または既存値が空の場合はこの警告を出さない。
- `CUDA_DEVICE_ORDER` は `PCI_BUS_ID` で上書きされる。HIP ビルドでもこの設定を行い、GPU の可視性には `HIP_VISIBLE_DEVICES` を使う。
- 環境変数の変更は起動したエンジンプロセス内で行われる。親プロセスの環境を変更する処理はない。
- 無効な番号、重複番号、空の値などを Strata が拒否するか、GPU runtime がどう解釈するかは確認できていない。

## 出力とエラー

- 既存の可視 GPU 環境変数と指定値が異なる場合、stderr に上書き警告を出す。
- 値を付けず `--gpu` だけを指定すると、引数処理の `next` が stderr に `--gpu needs a value` と出し、終了コード `2` で終了する。
- 値の形式・範囲に対する Strata 独自のエラーメッセージや終了コードは確認できなかった。

## 根拠

- `engine/src/program/generate.cpp:1210-1217` — `strata generate` の usage、`LIST` の説明、既定の可視 GPU、設定する環境変数。
- `engine/src/program/generate.cpp:3781-3801` — 初期化前に行う走査、最初の指定を選ぶ処理、CUDA/HIP ごとの環境変数、競合警告、Windows/POSIX の設定処理。
- `engine/src/program/generate.cpp:3844-3850` — parser の `next` による値必須処理と、通常 parser が `--gpu` 値を消費するだけであること。
- `engine/src/program/generate.cpp:3805-3817` — `--native` / `--model` のモデル判定と Qwen3.6 parser への振り分け。
- `engine/src/qwen35/q36_engine.cu:5345-5360` — Qwen3.6 parser も `--gpu` の値を消費し、可視性設定は親側で済ませること。
