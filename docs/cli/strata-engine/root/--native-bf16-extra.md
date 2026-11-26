# `--native-bf16-extra`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、トップレベル） |
| オプション | `--native-bf16-extra` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると有効 |

## 役割

実験的な BF16 projection 経路を、PLE の value 投影と shared expert の scalar gate で選びます。通常の CUDA/HIP engine と SYCL engine の双方に parser と実装があります。通常の起動では既定で無効です。一方、`--native` の native preset 処理はこのフラグを含む native 機能群を有効にするため、明示しなくても有効になります。Qwen3.5 family は起動前に別 parser へ振り分けられ、このオプションはその parser では受理されません（serve 経路では未知のオプションとして無視される場合があります）。

## 使い方

```sh
# 通常の engine 経路で PLE value / shared expert gate の BF16 projection を有効にする
strata --native-bf16-extra --model model.gguf --tokens 1,2,3
```

`--model` / `--tokens` は engine の通常起動に必要な入力例です。実際のモデル・入力に置き換えてください。`--native` を使う場合、このオプションの指定は不要です。

## 値と既定値

- 値は不要です。parser は引数文字列と一致したとき `native_bf16_extra` を `true` にします。省略時は `false` です（CUDA/HIP: `engine/src/program/generate.cpp:781,3915`、SYCL: `engine/sycl/src/program/generate.cpp:465,1954`）。
- 同じスイッチを複数回指定しても、同じ真偽値を再設定するだけです。無効化する `--no-native-bf16-extra` はありません。
- このフラグ自身に値の範囲や追加 validation はありません。値を続けて渡すと、その値は別引数として解析されます。通常 parser で未知引数になった場合は stderr に `unknown argument` と usage を出して終了コード 2 になります（`engine/src/program/generate.cpp:4268-4274`）。

## 実行時の動作

parser で保持した値は初期化時に `ple_set_native_bf16` と `shared_expert_set_native_bf16` に渡されます（CUDA/HIP: `engine/src/program/generate.cpp:6114-6117`、SYCL: `engine/sycl/src/program/generate.cpp:3229-3232`）。

- PLE では value weight が `BF16` 形式で、事前計算済み `pre_value` がないとき、フラグ有効時は FP32 embedding を入力とする `bf16_gemv_fp32_mmvf` を使います。無効時は embedding を BF16 に変換してから BF16 GEMV を行います。PLE の key、norm、その他の nonlinear 処理をこのフラグが切り替えるわけではありません（`engine/src/kernels/cuda/ple.cu:327-335`、SYCL: `engine/sycl/src/kernels/cuda/ple.dp.cpp:479-490`）。
- shared expert では native BF16 有効時に、scalar gate の計算へ FP32 入力の BF16 GEMV と sigmoid/scale 経路を使います。複数 token の場合は `STRATA_DEC_BATCH` が未設定または非ゼロならまとめて計算でき、そうでなければ token ごとの native BF16 経路に分かれます（CUDA/HIP: `engine/src/kernels/cuda/shared_expert.cu:263-280`、SYCL: `engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:379-406`）。この環境変数は batching の選択に関わり、フラグ自体の既定値は変えません。
- `--native` preset の処理では `native_bf16` と `native_bf16_extra` をともに有効化します（CUDA/HIP: `engine/src/program/generate.cpp:5155-5164`、SYCL: `engine/sycl/src/program/generate.cpp:2587-2596`）。
- セッション設定の fingerprint にも `native_bf16_extra` が含まれるため、有効・無効は異なる設定として扱われます（CUDA/HIP: `engine/src/program/generate.cpp:14016-14020`、SYCL: `engine/sycl/src/program/generate.cpp:8195-8199`）。

## 適用条件と副作用

- これは通常の `strata-engine` root parser に対するスイッチです。`engine/src/program/generate.cpp:3804-3818` では Qwen3.5 family を `strata::qwen35::run` に振り分けます。その parser の受理オプション一覧に本フラグはなく、通常経路では usage とともに終了コード 2、`--serve` 経路では未知の `--...` 引数を警告して読み飛ばします（`engine/src/qwen35/q36_engine.cu:5339-5355,5405-5418`）。
- PLE が無効、または shared expert 経路が使われない実行では、該当する切替箇所は実行されません。ソース上、このフラグ単体に追加のモデル形式検証や明示的な警告はありません。
- CUDA/HIP と SYCL のソースで同じ役割の setter・切替が確認できます。ここでは実行環境での数値差、対応 GPU 範囲、性能上の効果は測定していません。

## 出力とエラー

このフラグ専用の成功メッセージや validation error は確認できません。通常 parser が未知引数を処理する場合は `unknown argument: ...` と usage を stderr に出し、終了コード 2 になります（`engine/src/program/generate.cpp:4268-4274`）。各 native kernel の実行時エラーは呼び出し先の通常のエラー経路に従います。

## 根拠

- `engine/src/program/generate.cpp:780-781,1244-1248,3913-3916` — CUDA/HIP engine の既定値、help 表示、引数 parser。
- `engine/src/program/generate.cpp:5155-5164,6114-6117,14016-14020` — native preset による有効化、kernel setter への反映、session fingerprint への記録。
- `engine/src/kernels/cuda/ple.cu:327-335` — CUDA/HIP PLE value projection の分岐。
- `engine/src/kernels/cuda/shared_expert.cu:263-280` — CUDA/HIP shared expert scalar gate と batching 条件。
- `engine/sycl/src/program/generate.cpp:464-465,834-836,1952-1955,2587-2596,3229-3232,8195-8199` — SYCL 側の対応する既定値、help、parser、preset、setter、fingerprint。
- `engine/sycl/src/kernels/cuda/ple.dp.cpp:479-490`、`engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:379-406` — SYCL 側の PLE / shared expert 切替。
- `engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_engine.cu:5339-5355,5405-5418` — Qwen3.5 family の別 parser と未知オプション処理。
