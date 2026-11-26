# `STRATA_ADAPT_CALLBACK_WARMUP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux での `strata` 起動時に、CPU expert pool が現在のホストスレッドを pin する前に、空の GPU host callback を登録して同期するかを制御する。既定では有効で、Strata は `cudaLaunchHostFunc(nullptr, ...)` と `cudaStreamSynchronize(nullptr)` を呼び、成功・失敗を stderr に出す。コメントでは、後から作られる callback thread が pin 後の CPU mask を引き継いでホストの spin-wait と競合する状況を避ける意図としている。環境変数は callback の処理内容、expert の選択、生成結果を直接設定するものではない。`engine/src/program/generate.cpp:8985-9000`。

## 値と判定

このコードは `std::getenv` の戻り値を数値・真偽値として parse せず、先頭 1 byte が文字 `0` かだけを比較する。したがって空文字列は設定されていても有効側であり、`0` で始まる文字列だけが無効側になる。空白除去、大文字小文字変換、文字列全体の検査はない。`engine/src/program/generate.cpp:8990`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `__linux__` が定義されたビルド | 有効（warm-up を行う） | 空文字、`1`、`true`、`false`、`off`、` 0` など先頭 byte が `0` 以外の値 | `0`、`0anything`、`01`、`0 `、`0.0`（先頭 byte が `0`） |
| `__linux__` が未定義 | この箇所で読まれず、warm-up を行わない | 該当なし | 該当なし |

「有効」はこの分岐に入るという意味であり、GPU API 呼び出しが成功する保証ではない。Linux の判定は `#if defined(__linux__)` で囲まれ、変数を無視する別の値 parse や CLI 引数による上書きはこの処理にはない。`engine/src/program/generate.cpp:8985-9000`。

## 有効になる条件

- このコードがコンパイルされた `strata` の Linux 実行であること。OS 条件は `__linux__` のみで、当該分岐に GPU backend 用の追加 `#if` はない。ビルド構成として通常の GPU engine は `generate.cpp` を `strata` 実行ファイルに含める（`engine/cmake/strata_gpu_engine.cmake:548-551`）。
- CLI の通常実行または `--serve` など、共通の起動処理がこの位置まで到達すること。`--version` は main の早期 return 経路があるため対象外（`engine/src/program/generate.cpp:3670-3705`）。
- 変数が unset、または値の先頭 byte が `0` 以外であること。
- callback 登録と既定 stream の同期が成功すること。どちらかが失敗した場合は警告を出して続行する。pool の作成自体を取りやめる条件ではない（`engine/src/program/generate.cpp:8991-8998`）。

## 実行時の詳細

共通の `main` 内でモデル・arena の準備後、`ExpertPool` の構築直前に環境値を直接 1 回読み取る。分岐が有効なら空 callback を既定 stream に登録し、同期を試みる。pool はその後 `pin=true` で構築される。この箇所に static cache やリクエストごとの再読取はないため、同一プロセス内で後から環境を変えても、この起動時の分岐には反映されない。serve の各 request でも読み直さない（`engine/src/program/generate.cpp:8975-9005`）。

API 呼び出しが失敗したときは `cudaGetLastError()` も呼ばれるが、その戻り値は使わず警告後も起動を続ける。この変数に結び付いた終了・timeout 経路はない（`engine/src/program/generate.cpp:8991-8998`）。

## ログと測定値

warm-up 成功時の stderr は `strata generate: GPU host-callback thread started before host-core pinning`。どちらかの API 呼び出しが失敗した場合は `strata generate: could not warm up the GPU host-callback thread (continuing)` を出す。変数の値が先頭 `0` のとき、または非 Linux ビルドでは、この箇所からログは出ない（`engine/src/program/generate.cpp:8991-8998`）。

Strata の資料には過去の測定がある。`docs/bench-results/2026-10-11-rtx-5090-callback-affinity/README.md:3-12,44-69` は v0.1.43（記載 source SHA `7695859aa13afb248bdb4d36f9b2e95707db079d`）での RTX 5090 / Ryzen 9 9950X、Fedora Silverblue 上の Ubuntu 26.04 NVIDIA distrobox、NVIDIA 610.57.04 / CUDA 13.3.33、Qwen3.8-Flash-Next GSQ-RCO IQ3_S の比較として、4K の三 prompt で通常 callback 142.82 TPS に対し早期 warm-up 207.75 TPS（各設定 12 requests）、100K の code prompt で 232.96 対 252.19 TPS（各設定 4 requests）を記載する。4 回の起動を normal/warm-up/warm-up/normal の順で行った結果で、現行 HEAD の再測定ではない。報告書は token-array の全一致を主張していない。

`docs/DETAILS.md:1213,1674` にも Linux の既定 ON・`=0` の off switch と 4K 三 prompt の測定要約がある。コード上の値判定は `=0` 全体との比較ではなく先頭 byte 判定である。

## 根拠

- 実読取、Linux guard、API 呼び出し、pool 構築順序、成功・失敗ログ: `engine/src/program/generate.cpp:8985-9005`
- `main` と `--version` 早期終了: `engine/src/program/generate.cpp:3670-3705`
- GPU engine における executable 構成: `engine/cmake/strata_gpu_engine.cmake:548-551`
- 過去の測定条件と制限: `docs/bench-results/2026-10-11-rtx-5090-callback-affinity/README.md:3-12,44-82`; 要約: `docs/DETAILS.md:1213,1674`
