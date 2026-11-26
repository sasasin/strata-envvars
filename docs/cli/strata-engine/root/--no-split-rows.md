# `strata generate --no-split-rows`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--no-split-rows` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

CPU expert pool が単一トークンの expert 計算を行う際、各 expert の行を pool の複数スレッドに分割する既定の方式を無効にし、`run` による処理へ切り替えます。行分割方式と通常方式の A/B 比較用フラグとして実装されています（`engine/src/program/generate.cpp:999`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-split-rows
```

`--tokens` はこの実行形式で必須の事前 token 化済み入力です（`engine/src/program/generate.cpp:1208-1214`）。

## 値と既定値

値は不要です。parser はフラグを受けると `no_split_rows` を `true` にします。既定値は `false` なので、指定しない場合は行分割が有効です。繰り返し指定しても同じ真偽値を設定するだけで、値の検証や重複指定エラーはありません（`engine/src/program/generate.cpp:999,4034`、SYCL 実装 `engine/sycl/src/program/generate.cpp:647,2029`）。

## 実行時の動作

設定値は `drive.d.split_rows = !o.no_split_rows` として expert dispatch に渡されます（`engine/src/program/generate.cpp:10246`、SYCL 実装 `engine/sycl/src/program/generate.cpp:5783`）。単一トークン dispatch では、真なら `ExpertPool::run_split`、偽なら `ExpertPool::run` を呼びます（`engine/src/core/expert_source.cpp:5389-5391`、SYCL 実装 `engine/sycl/src/core/expert_source.cpp:2536-2538`）。

`run_split` は expert の gate/up 行を pool 全体で処理し、中間値を量子化してから down 行を処理します。ヘッダーは `run` と出力が bitwise 同じと説明しています。expert 数が pool の上限を超える場合、worker が1つの場合、または CPU oracle 用 q8_0 が有効な場合は `run_split` 自身が `run` にフォールバックします（`engine/include/strata/kernels/cpu/pool.hpp:241-245`、`engine/src/kernels/cpu/pool.cpp:1500-1513`）。したがってこれらの条件では、このフラグによる実処理の差はありません。

複数トークンをまとめる dispatch は `run_split_multi`（または native 版）を直接呼び、`split_rows` を参照しません（例: `engine/src/core/expert_source.cpp:5889-5892,5934-5936`、SYCL 実装 `engine/sycl/src/core/expert_source.cpp:2791-2793`）。その経路の行分割動作はこのフラグでは切り替わりません。

## 適用条件と副作用

この設定を参照するのは CUDA/HIP 共通側と SYCL 側の `strata generate` の単一トークン expert dispatch です。CPU expert pool の仕事の割り振りを変えます。モデル出力への影響や速度の差は、確認したソースからは断定できません。ファイル変更などの副作用はこのフラグの処理にはありません。

## 出力とエラー

このフラグ自体の validation、警告、専用出力、専用エラー経路はありません。フラグ以外の未知引数は `unknown argument` を stderr に出して usage を表示し、終了コード 2 で終了します（`engine/src/program/generate.cpp:4268-4273`、SYCL 実装 `engine/sycl/src/program/generate.cpp:2214-2219`）。

## 根拠

- `engine/src/program/generate.cpp:999,4034,10246`: 既定値、parser、dispatch 設定。
- `engine/src/core/expert_source.cpp:5389-5391`: 単一トークン経路の分岐。
- `engine/include/strata/core/expert_source.hpp:587-588`: 行分割が既定で有効な設定。
- `engine/include/strata/kernels/cpu/pool.hpp:241-245`、`engine/src/kernels/cpu/pool.cpp:1500-1513`: `run_split` の処理・フォールバック。
- `engine/src/core/expert_source.cpp:5889-5892,5934-5936`: 複数トークン経路が `split_rows` を参照しない根拠。
- `engine/sycl/src/program/generate.cpp:647,2029,5783`、`engine/sycl/src/core/expert_source.cpp:2536-2538,2791-2793`: SYCL 側の対応箇所。
