# `STRATA_MTP_PRIORITY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP drafter が `--pipeline-windows 2` の forcing graph 用 stream を作るとき、CUDA ビルドで高優先度 stream の作成を試みるかを決める。未設定では試み、atoi の結果が 0 なら通常 stream にする。CUDA/HIP 版の MTP drafter は `cs_` を draft 計算に使うため、対象になるのはこの drafter stream である。`--pipeline-windows 0` や 1 では `force_on_` が立たず、この設定による優先度 stream の作成分岐に入らない。SYCL 版も同名を読むが、どちらの値でも同じ queue 作成呼び出しとなり、実装コメントでは priority 指定を無視するとされている（`engine/src/core/mtp.cpp:613-620,646`; `engine/sycl/src/core/mtp.cpp:552-580`; `engine/include/strata/core/mtp.hpp:198-203`）。

## 値と判定

CUDA/HIP 共通ソースのうち、次の条件付きコンパイルで含まれる経路と、SYCL ソースで判定が異なる。

| ビルド・経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA の通常ビルド（`STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL` が未定義） | 高優先度 stream を試みる | `std::atoi(v) != 0`。例: `1`, `-1`, `1tail`, ` 1` | `std::atoi(v) == 0`。例: 空文字、`0`, `0tail`, `true`, `tail`, `  ` |
| SYCL（`STRATA_USE_HIP` が未定義） | `hi_prio` は true | 同じ `std::atoi(v) != 0` 判定 | 同じ `std::atoi(v) == 0` 判定。ただし queue 作成の実質的な違いはない |
| HIP、gfx906 向け HIP、Metal | この変数を読む当該分岐がコンパイルされない | 該当なし | 該当なし |

判定は設定文字列全体の厳密な数値 parse ではなく `std::atoi` である。先頭の空白と符号の後に読める数字部分を使い、後続文字列は無視する。数字を読めない文字列や空文字は 0 となる。したがって `1tail` は有効、`0tail` は無効、`true` は無効で、大文字小文字の特別扱いはない。`atoi` で表現できない範囲の整数の結果はこの実装から保証できない。各読み取り箇所は関数内 `static const` に値を保持する。根拠: `engine/src/core/mtp.cpp:616-620`; `engine/sycl/src/core/mtp.cpp:555-568`。

## 有効になる条件

- CUDA 側でこの設定が stream 選択に効くのは、通常 CUDA ビルドで、MTP drafter の `load()` に入る前に `set_force_capture(true)` が呼ばれた場合に限る。呼び出し元は `o.pipeline_windows >= 2` のときに設定しており、`--pipeline-windows 1` では設定しない（`engine/src/program/generate.cpp:8258-8264`; `engine/sycl/src/program/generate.cpp:4537-4541`）。
- pipeline windows 自体はサーバーモードの対応する multi-GPU layer-split 経路でのみ有効になる。CUDA 側では `--mtp` と `--spec` 2 以上が必要で、batch slots、peer device、helper cache などの条件で無効化される場合がある。SYCL 側も `--serve`、2 枚の Battlemage GPU の layer split、MTP などが自動有効化条件で、非対応条件では無効化される（`engine/src/program/generate.cpp:6584-6601`; `engine/sycl/src/program/generate.cpp:3590-3633`）。
- CUDA では環境値が非ゼロでも、`cudaDeviceGetStreamPriorityRange` が失敗すれば高優先度 stream 作成を試さず通常 stream に進む。高優先度 stream 作成自体が失敗した場合も通常 stream 作成へ進む（`engine/src/core/mtp.cpp:618-620,646`）。
- SYCL では同じ `force_on_ && hi_prio` 条件を通ると `create_queue(true)` を呼ぶが、偽の場合も後続で同じ `create_queue(true)` を呼ぶ。実装コメントは queue が priority options を無視すると明記しているため、現行ソース上、この環境変数による queue の優先度差はない（`engine/sycl/src/core/mtp.cpp:562-580`）。
- HIP、gfx906 向け HIP、Metal の CUDA 翻訳単位では `STRATA_MTP_PRIORITY` の読み取り自体がコンパイル除外される。HIP の別設定 `STRATA_MTP_HIP_PRIO` は別の分岐であり、この文書の変数の代替として扱わない（`engine/src/core/mtp.cpp:616-645`）。

## 実行時の詳細

読み取りは process 起動時ではなく、`MtpDrafter::load()` 内で stream を準備するときに行う。C++ の関数内 `static const` なので、設定値はその static initialization が初めて評価されたときに一度取得され、同じプロセス内で後から環境を変更しても再読込されない。条件式が `force_on_ && hi_prio` の短絡評価なので、`force_on_` が false の load では static 初期化も実行されず、最初に forcing graph を使う load で評価される（`engine/src/core/mtp.cpp:617-620`; `engine/sycl/src/core/mtp.cpp:556-568`）。

CUDA では環境値が未設定または atoi 非ゼロで、優先度範囲取得が成功すれば `prio_hi` を渡して非同期 stream を作成する。これに失敗した場合や値が 0 なら `cudaStreamCreateWithFlags(..., cudaStreamNonBlocking)` に進む。SYCL では読み取り結果に応じて分岐するものの、どちらも `create_queue(true)` である。CLI の `--pipeline-windows` は環境値との優先順位を持つ設定上書きではなく、forcing graph 経路自体の有効・無効を決める前提条件である（`engine/src/core/mtp.cpp:613-646`; `engine/sycl/src/core/mtp.cpp:552-580`; 呼び出し元は `engine/src/program/generate.cpp:8262-8264` と `engine/sycl/src/program/generate.cpp:4539-4541`）。

## ログと測定値

`STRATA_MTP_PRIORITY` の値や、高優先度 stream を作成できたかどうかを直接表示するログは該当箇所にない。CUDA で通常 stream の作成にも失敗すると `load()` は `err = "mtp: stream"` で失敗する。generate の呼び出し元はそのエラーを `strata generate:` に続けて stderr に出し、終了コード 1 を返す。SYCL でも通常 queue 作成失敗時の内部エラー文字列は `mtp: stream` である（`engine/src/core/mtp.cpp:646`; `engine/src/program/generate.cpp:8264`; `engine/sycl/src/core/mtp.cpp:578-580`; `engine/sycl/src/program/generate.cpp:4541`）。

## 根拠

- CUDA/HIP/Metal 条件付き分岐、値の判定、高優先度 stream と通常 stream の fallback: `engine/src/core/mtp.cpp:613-646`。
- SYCL での判定・同一 queue 作成呼び出し・priority 無視の注記: `engine/sycl/src/core/mtp.cpp:552-580`。
- forcing capture の設定と MTP load: `engine/src/program/generate.cpp:8258-8264`; `engine/sycl/src/program/generate.cpp:4537-4541`。
- pipeline windows の有効条件: `engine/src/program/generate.cpp:6584-6601`; `engine/sycl/src/program/generate.cpp:3590-3633`。
- MTP draft layer と `--mtp` の概要: `docs/DETAILS.md:376-383`。
