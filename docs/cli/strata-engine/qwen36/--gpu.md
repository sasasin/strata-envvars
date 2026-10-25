# `--gpu`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 モデル選択時）または `strata-q36` |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU ID のリスト文字列。通常の `strata` の help は `nvidia-smi` / PCI 順の ID をカンマ区切りで指定すると説明する |

## 役割

Qwen3.6 用エンジンを起動する `strata` 経路で、ランタイムに見せる GPU を指定します。値を Strata が GPU ID の配列へ変換するのではなく、CUDA または HIP のデバイス可視環境変数へそのまま設定します（`src/program/generate.cpp:2370-2389`）。

## 使い方

`strata` が Qwen3.6 の GGUF を選択する呼び出しでは、たとえば次のように指定できます。

```sh
strata --model /models/qwen36.gguf --gpu 0 --tokens 1,2,3
```

Qwen3.6 の専用実行ファイル `strata-q36` も引数として `--gpu` と値を受け取りますが、そこで値は読み捨てられ、デバイス可視環境変数は設定されません（`src/qwen35/q36_engine.cu:3742-3754`）。GPU 選択が必要な場合は、呼び出し前に適切な環境変数を設定するか、上記の `strata` 経路を使ってください。

## 値と既定値

- 値を1つ取ります。`strata` の共通エンジン help は GPU ID をカンマ区切りで指定すると案内しています（`src/program/generate.cpp:813-815`）。
- `strata` の Qwen3.6 経路で省略した場合、このオプションによる環境変数の変更はありません。既存の `CUDA_VISIBLE_DEVICES` / `HIP_VISIBLE_DEVICES` やランタイムの既定動作が使われます。
- `strata` は値の構文・範囲を検査しません。カンマ区切りの文字列を環境変数に渡すところまでが確認できた Strata 側の処理です。無効な ID の扱いは CUDA/HIP ランタイム側に委ねられ、このソース調査からは特定できません。
- `strata` に複数回指定した場合、起動時の環境設定に使われるのは最初の `--gpu` とその値です。通常の parser ループは各 `--gpu` の値を消費して処理を続けます（`src/program/generate.cpp:2373-2391,2416-2424`）。
- `strata-q36` では値を消費するだけで、値の検査もデバイス選択への適用もありません（`src/qwen35/q36_engine.cu:3742-3754`）。

## 実行時の動作

`strata` は通常の GPU 初期化より前に引数を走査します。指定値を、CUDA ビルドでは `CUDA_VISIBLE_DEVICES`、HIP ビルドでは `HIP_VISIBLE_DEVICES` に設定し、同時に `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定します。すでに対象の可視環境変数が空でなく、指定値とも異なる場合は stderr に上書き警告を出します。これは起動した `strata` プロセス内の環境変更です（`src/program/generate.cpp:2370-2391`）。

その後 `--model` / `--native` の GGUF family を調べ、Qwen3.6（`qwen35moe`）なら `strata::qwen35::run()` へ引数全体を渡します（`src/program/generate.cpp:2393-2408`）。Qwen3.6 parser は `--gpu` を認識して値を消費します（`src/qwen35/q36_engine.cu:3742-3754`）。

一方、独立実行ファイル `strata-q36` の `main()` は直接 `strata::qwen35::run()` を呼びます（`src/qwen35/q36_main.cpp:1-5`）。専用 parser にも `--gpu` の受理分岐はありますが、設定変更はありません。そのままモデル読み込みへ進み、デバイス確保などを行うため、専用実行ファイルでの `--gpu` 指定はデバイス選択に作用しません（`src/qwen35/q36_engine.cu:3753,3809-3815,953-956`）。

## 適用条件と副作用

- `--gpu` による環境変数設定は、`src/program/generate.cpp` の共通 engine 入口を通る場合に適用されます。Qwen3.6 では、モデル family 判定後に専用 parser へ移る前に設定されます（`src/program/generate.cpp:2370-2406`）。
- CUDA ビルドは `CUDA_VISIBLE_DEVICES`、HIP ビルドは `HIP_VISIBLE_DEVICES` を対象にします。HIP では CUDA 可視環境変数ではなく HIP 側の変数を使うとソースコメントに記載されています（`src/program/generate.cpp:2377-2389`）。
- 既存値を上書きする場合、値が空でなく指定値と異なると警告を stderr に出します。同値または空値なら、この警告条件には入りません（`src/program/generate.cpp:2381-2383`）。
- 明示的な複数 GPU のサポートや、Qwen3.6 で複数 GPU を使った場合の挙動は、このオプションの実装からは確認できません。ここでは GPU ID を複数指定する利用例を示しません。
- `strata-q36` 直接起動では、`--gpu` は引数として受理されますが、GPU の可視性を変えません（`src/qwen35/q36_engine.cu:3753`）。

## 出力とエラー

- `strata` の共通 parser で値が欠けていれば stderr に `--gpu needs a value` を出して終了コード 2 になります（`src/program/generate.cpp:2418-2424`）。Qwen3.6 parser に直接渡った場合も、`strata-q36: --gpu needs a value` を stderr に出して終了コード 2 です（`src/qwen35/q36_engine.cu:3743-3746`）。
- `strata` が既存の可視環境変数を異なる値で上書きすると、`warning: --gpu ... overrides ...` を stderr に出します（`src/program/generate.cpp:2381-2383`）。
- GPU ID の不正値に対する Strata 独自の validation、エラー文、終了コードは確認できません。値は環境変数へ渡されるだけなので、その後の扱いはランタイム側です。

## 根拠

- `src/program/generate.cpp:813-815` — 共通 engine help における値の説明。
- `src/program/generate.cpp:2370-2391` — 初期化前の引数走査、環境変数選択・上書き、警告、最初の指定のみ適用する処理。
- `src/program/generate.cpp:2393-2408` — Qwen3.6 family の判定と専用 engine への引数転送。
- `src/program/generate.cpp:2416-2424` — 共通 parser の値欠落エラーと `--gpu` の値消費。
- `src/qwen35/q36_main.cpp:1-5` — `strata-q36` の入口。
- `src/qwen35/q36_engine.cu:3742-3754` — Qwen3.6 parser の既定値と `--gpu` の読み捨て。
- `src/qwen35/q36_engine.cu:3809-3815,953-956` — 専用 parser 後のモデル読み込みと CUDA メモリ確保。
