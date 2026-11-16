# `STRATA_PF_FEWROWS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

GPU prefill の MoE expert 処理で、FP16 経路を使う native pack の expert のうち、この prompt chunk で routed row が 1〜12 件のものを、重みを FP16 に dequantize せず q8_1 activation と量子化 grouped kernel で計算する研究用スイッチです。対象はその条件に合う expert だけで、行数 0 または 13 以上の expert は従来の FP16 dequantize + GEMM 経路に残ります。MMQ、fused kernel、非 native pack、APR (Hadamard-folded) の expert はこの分岐を通りません（`include/strata/prefill/fewrows.hpp:30-36`, `src/prefill/prefill.cpp:6910-6958`）。

## 値と判定

engine は `fewrows_switch(std::getenv("STRATA_PF_FEWROWS"), dflt)` を使います。`nullptr`（未設定）と空文字列は `dflt` を返し、それ以外は文字列の先頭 byte が `'0'` でなければ有効です。文字列全体の parse、数値検査、trim、大文字小文字の変換はありません（`include/strata/prefill/fewrows.hpp:24-28`）。

| 条件 | unset / 空文字 | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| 通常の既定（`dflt=false`） | off | `1`, `true`, `false`, ` 0`, `x` など、先頭が `0` 以外 | `0`, `00`, `0anything` |
| GP100 自動既定が成立（後述） | on | 上と同じ。`1` 等で明示的に on | `0` 等で明示的に off |

`STRATA_PF_FEWROWS` の空文字は値「設定済み」として on にはならず、未設定と同じ `dflt` です。先頭が `0` かどうかだけを調べるため、`00` や `0anything` は off、` 0` と `false` は on です（`include/strata/prefill/fewrows.hpp:25-28`）。

`dflt` は `gp100_fp16_default(std::getenv("STRATA_PREFILL_MMQ"))` の結果です。通常は false です。CUDA で `STRATA_EXPERIMENTAL_SM60` が定義されたビルドでは、`STRATA_PREFILL_MMQ` が未設定で、可視 CUDA GPU が 1 台以上かつ全台 CC 6.0、`STRATA_MMQ_WS` の weight-stationary mode が off、`STRATA_EXPERT_NIBBLE` の変換が off、`--peer-device` が未指定の場合に true になります。明示的な `STRATA_PREFILL_MMQ` は、値が空でも環境変数が存在すればこの自動既定を止めます（`src/prefill/prefill.cpp:1936-1963`, `include/strata/prefill/gp100_prompt_default.hpp:15-25`, `src/program/generate.cpp:4430-4432`）。

## 有効になる条件

- この判定と実処理は `strata::prefill::Prefill` の GPU prompt MoE walk にあります（`src/prefill/prefill.cpp:6681-6684`）。Metal 側で確認できたのは CUDA kernel が記録する計画の stub コメントだけで、Metal 実装による環境変数の読み取りはありません（`metal/src/engine/stubs_prompt_f16.cpp:2-6`）。
- `STRATA_PF_FEWROWS` が有効であり、その layer が MMQ ではなく FP16 経路 (`!use_mmq`) を使う必要があります（`src/prefill/prefill.cpp:5414`, `src/prefill/prefill.cpp:6910-6913`）。GP100 自動既定の場合はこの条件に合わせ、`mmq_plan()` が FP16 path を選びます（`src/prefill/prefill.cpp:1965-1976`）。
- `lay.native` が true の native pack で、`had_gu || had_d` が false（APR なし）である必要があります。これを満たさない expert は同じ compute lambda の通常経路に進みます（`src/prefill/prefill.cpp:5412-5424`, `src/prefill/prefill.cpp:6911-6913`, `src/prefill/prefill.cpp:6943-6958`）。
- 対象 expert の当該 chunk 内の row 数 `m.cnt[e]` が 1〜12 の範囲である必要があります。上限 12 は `kFewRows` です（`include/strata/prefill/fewrows.hpp:18-19,30-36`, `src/prefill/prefill.cpp:6911-6913`）。
- GP100 の自動 on はさらに CUDA ビルドの `STRATA_EXPERIMENTAL_SM60` が必要です。HIP または macro なしでは `gp100_fp16_default` は false を返します。この制限は自動既定に対するもので、`fewrows_switch` 自体の値規則とは別です（`src/prefill/prefill.cpp:1936-1941`; macro の compile definition は `cmake/strata_gpu_engine.cmake:14-17`）。
- GP100 自動既定は環境変数を明示して上書きできます。`STRATA_PF_FEWROWS=0` は自動 on を無効化し、`STRATA_PF_FEWROWS=1` は switch を on にしますが、MMQ 等の条件により実際の layer が FP16 経路でなければ few-row route は使われません（`include/strata/prefill/gp100_prompt_default.hpp:22-25`, `src/prefill/prefill.cpp:6910-6913`）。

## 実行時の詳細

`fr_env` は expert walk 内の関数局所 `static const bool` です。最初に制御が宣言へ到達した時に `STRATA_PF_FEWROWS` と `STRATA_PREFILL_MMQ` を読み、そのプロセス内で再評価しません。後から環境を変更しても `fr_env` には反映されません。GP100 の device 判定も `gp100_fp16_default` 内の static 値に cache されます（`src/prefill/prefill.cpp:6681-6683`, `src/prefill/prefill.cpp:1941-1962`）。

route を使う layer では、chunk の `m.mixed` を一度 q8_1 row に量子化し、expert ごとの device plan record を書いて `native_expert_grouped` を呼び、結果を `m.Dm` に書きます。必要な buffer は初回または row 容量不足時に確保され、量子化は layer ごとに一度です（`src/prefill/prefill.cpp:6914-6940`）。これらは同じ prompt prefill 内の expert 計算経路を変えます。decode 処理や token 選択を変える実装はこの経路にはありません。

## ログと測定値

この変数が on になったことを単独で知らせる通常ログは、調査した分岐にはありません。buffer 確保が失敗した場合は `err` に `prefill: few-row experts: no memory` を設定し、`run_impl` が false を返します（`src/prefill/prefill.cpp:6914-6923`）。この場所自体では stderr 出力やプロセス終了を行いません。

## 根拠

- `include/strata/prefill/fewrows.hpp:18-36` — row 上限、環境値の判定、route 条件。
- `src/prefill/prefill.cpp:1936-1963`、`include/strata/prefill/gp100_prompt_default.hpp:15-25` — GP100 自動既定条件。
- `src/prefill/prefill.cpp:5412-5424,6681-6684,6910-6958` — 対象経路、全実処理、通常経路への fallback。
- `src/prefill/prefill.cpp:6914-6929` — buffer 確保・量子化と割当失敗時のエラー。
- `src/program/generate.cpp:4430-4432` — `--peer-device` 状態を GP100 判定へ渡す箇所。
