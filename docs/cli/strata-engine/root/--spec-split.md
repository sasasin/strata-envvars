# `--spec-split`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--spec-split` |
| 別名 | なし。無効化用の別オプションは `--no-spec-split` |
| 値 | 取らない真偽フラグ |

## 役割

投機的検証 window の token 行を2グループに分け、片方の CPU expert 計算ともう片方の GPU 処理を重ねるための opt-in 設定です。Verifier のコメントはこの方式を「exact but slower」と説明しています。既定値は無効で、性能向上を保証するものではありません（`src/program/generate.cpp:709`、`include/strata/core/verify.hpp:336-338`）。

## 使い方

通常 engine parser が扱うモデルファイルを指定して生成する例です。`model.gguf` は実際のモデルファイルに置き換えてください。

```sh
strata --spec-split --native ./model.gguf --tokens 1
```

この例はフラグの構文を示します。実際に分割を使うには、複数 token を含む投機的検証 window が実行される必要があります。Qwen3.5 に振り分けられるモデルにはこの例を適用できません（調査範囲の注記を参照）。

## 値と既定値

- `--spec-split` は値を受け取らず、parser 内の `spec_split` を `true` にします。
- `Options::spec_split` の初期値は `false` です（`src/program/generate.cpp:709`, `2632`）。
- `--no-spec-split` は同じ値を `false` に戻します（`src/program/generate.cpp:2734`）。両方指定したときは parser が引数を左から処理するため、後に現れた方が有効です。
- このフラグ単体に対する値 validation や数値範囲はありません。

## 実行時の動作

通常 parser は `spec_split` を Verifier に渡します。単一 GPU の生成経路では verifier 初期化後に `ver.set_split(o.spec_split)` を呼び、serve 経路では通常 verifier と layer split の stage verifier に設定します（`src/program/generate.cpp:9212-9232`, `16167-16175`）。SYCL 実装にも同じ parser 設定と Verifier への伝播があります（`sycl/src/program/generate.cpp:663`, `1929`, `2011`, `7435-7455`）。

実際にグループ数を2にする条件は `split_ == true`、検証 window の行数 `T >= 2`、かつ batch 記録中でないことのすべてです。それ以外は1グループのままです。分割時は先頭側のグループを `0..ceil(T/2)`、後半を残りの行に割り当てます。GPU 側のグループごとの処理・doorbell を Verifier が扱い、expert dispatch もグループ別の slot を使います（`src/core/verify.cpp:1122`, `1141`, `1148`, `2091-2104`, `2984-3004`, `3238-3253`）。

この分割は `--spec` で作られる複数候補の検証 window に作用します。`T < 2` の window や batch window では指定していても動作上の分割はありません（`src/core/verify.cpp:1122`）。`--no-spec-split` は既定値を明示する用途にも使えます。

## 適用条件と副作用

- 設定自体は GPU/backend を選ばず、CUDA verifier と SYCL verifier の両方に実装があります。ただし実際の window 分割条件は上記の通りです（`src/core/verify.cpp:1122`; `sycl/src/program/generate.cpp:7422-7455`）。
- 2グループ時は各グループが GPU 計画・expert 処理の別領域を使い、Verifier がグループごとに layer を処理します（`src/core/verify.cpp:2091-2142`, `2984-3004`, `3250-3253`）。このため主な影響は検証時の CPU/GPU の実行スケジュールです。
- このオプション自体がファイルを書き換えたり、ネットワーク要求を発生させたりする処理は確認できません。
- `--no-spec-split` と同じく、処理は正確性を維持する意図で実装されていますが、実行性能は環境・モデルに依存します。ソースコメントは「slower」としています（`src/program/generate.cpp:709`, `include/strata/core/verify.hpp:336-338`）。

## 出力とエラー

このフラグ専用の stdout/stderr 出力や値検証エラーはありません。引数列に未知の option があれば共通 parser が `unknown argument: ...` を stderr に出し、usage を表示して status 2 で終了します（`src/program/generate.cpp:2787-2792`）。フラグ自体は引数値を要求しないため、値不足エラーの対象ではありません。

## 根拠と調査範囲

- option の既定値と parser 定義: `src/program/generate.cpp:709`, `2632`, `2734`。
- 設定先と分割条件: `src/program/generate.cpp:9212-9232`, `16167-16175`; `include/strata/core/verify.hpp:336-338`, `614`; `src/core/verify.cpp:1122`, `1141`, `2984-3004`。
- SYCL 側の parser・設定伝播: `sycl/src/program/generate.cpp:663`, `1929`, `2011`, `7435-7455`。
- 一般的な未知引数処理: `src/program/generate.cpp:2787-2792`。

通常 parser は `--model` / `--native` の model family が Qwen3.5 のとき別実装へ引数列を渡します（`src/program/generate.cpp:2397-2407`）。その parser は `--spec-split` を通常実行では未知引数として usage を出し status 2 で終了します。`--serve` を先に指定してからこの option を渡す場合は、値なしの未知 option を警告して無視します（`src/qwen35/q36_engine.cu:3742-3795`）。したがってこの option は通常 engine parser の scope で有効ですが、Qwen3.5 parser では有効な設定ではありません。SYCL parser は通常 engine と同様の option 設定・伝播を実装しています。Release 配布バイナリの実行確認や性能測定は行っていません。
