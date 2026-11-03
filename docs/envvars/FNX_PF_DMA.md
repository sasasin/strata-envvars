# `FNX_PF_DMA`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

strata-split の複数 GPU prefill ring で、他カードから届いた page-locked host buffer の値を copy engine で当該 GPU の device buffer に取り込んでから加算するかを選びます。ON では最終 gather 結果も device buffer に置き、後続部分を device へコピーして出力 kernel が読みます。OFF では ring の受信・gather host buffer を kernel が直接読みます。通常の Strata engine 全体の設定ではなく、strata-split 実行ファイル内の Flash-Next prefill 経路の設定です。

## 値と判定

`src/split/src/prefill.cu` は `env_int("FNX_PF_DMA", default)` を呼び、結果が 0 以外なら DMA 経路、0 なら host-buffer 読み取り経路にします。共通 helper は変数全体を符号付き base-10 `long long` として parse します (`src/split/src/env.hpp:15-22,33-40`)。

| 入力 | 判定 |
|---|---|
| 未設定 | HIP は 0、CUDA は 1（後述） |
| `0`、`-0`、`+0` | OFF |
| `1`、`-1`、`+2` など、範囲内の整数で 0 以外 | ON |
| 空文字、空白を含む値、数字以外を含む値、符号だけの値 | `FNX_PF_DMA: '<値>' is not a whole number` の例外 |
| `long long` の範囲を超える値 | 同じく整数として不受理 |

parse は文字列全体を消費する必要があります。小数・接尾辞付き数値は不可です。0/1 への限定や追加の上下限 clamp はありません。空文字は未設定扱いではなく不正値です。

## 有効になる条件

- `FNX_HIP` を定義した HIP build では未設定時 OFF (`src/split/src/prefill.cu:893-895`)。`FNX_HIP` なしの CUDA build では未設定時 ON (`src/split/src/prefill.cu:895-897`)。
- 対象は `strata-split` です。CMake ではこれは既定 OFF の opt-in build で、Linux CUDA または Linux HIP、固定カード数 2–4 向けに作られます。HIP target は `FNX_HIP=1` を定義し、CUDA target は定義しません (`src/split/CMakeLists.txt:1-5,92-116`)。
- 値は `Engine::prefill_alloc()` が作る各カードの `PfRing` に設定されます (`src/split/src/prefill.cu:625-635,866-898`)。ただし、実際の ring 加算は `Engine::prefill()` / `prefill_pass()` を実行したときだけです (`src/split/src/prefill.cu:982-1036`)。`fnx_run` の `mtp` / `logits` 経路では `FNX_PREFILL` が prefill path 選択に関わります (`src/split/tools/fnx_run.cpp:989-1018`)。`FNX_PREFILL=0` で窓単位処理を選んでも、Engine 構築時の `prefill_alloc()` は先に呼ばれるため、この変数の parse 自体は回避しません (`src/split/src/engine.cu:274-275`)。
- `FNX_PF_DMA_CHECK` は別の診断用変数で、DMA copy 後に比較 kernel を追加します。`FNX_PF_DMA_BARRIER` も別変数で、非ゼロなら event を作り、DMA コピー後に同一 stream 内で record/wait します。いずれも `FNX_PF_DMA` の値を上書きしません (`src/split/src/prefill.cu:898-903`; `src/split/src/pf_common.cuh:194-200,219-227,245-259`)。
- HIP のコメントでは、gfx1201 で peer host stores を copy engine が常に最新値として読めない問題が観測され、速さも得られなかったため DMA receive/gather は opt-in とされています。これは実装コメントの説明であり、本調査で再測定した結果ではありません (`src/split/src/prefill.cu:891-896`)。

## 実行時の詳細

値は static cache ではなく、`prefill_alloc()` 中にカードごとに `env_int` で読み、各カードの `PfRing::dma` に保存されます。初期化後の環境変更を再評価するコードはこの経路にありません。CLI option がこの設定を直接指定・上書きする処理も見つかりません。

ring の `ADD` では、DMA ON の場合に受信 host slot から `din` へ `cudaMemcpyAsync` し、その device buffer を加算 kernel に渡します。OFF の場合は受信 host slot を直接加算 kernel に渡します (`src/split/src/pf_common.cuh:216-229`)。`GADD` でも同じく ON なら受信値を device にコピーし、加算結果を各カードの gather buffer に書きます (`src/split/src/pf_common.cuh:241-260`)。最後の `OUT` では ON の場合に未完了部分を `dag` にコピーしてから出力 kernel を実行し、OFF の場合は `ag` を直接出力 kernel の入力にします (`src/split/src/pf_common.cuh:274-289`)。DMA が ON の HIP gather では system fence を有効にし、他カードの host buffer への stores を system-wide に見せる分岐もあります (`src/split/src/pf_common.cuh:117-135,253-259`)。

不正値は `env_int` が例外にし、`fnx_run` の top-level handler は stderr に `fnx_run: <例外文言>` を出して status 1 で終了します (`src/split/src/env.hpp:33-40`; `src/split/tools/fnx_run.cpp:1364-1373`)。有効値の DMA copy/runtime 失敗は `ckc(..., "ring in" / "ring out" / "ring gather")` のエラー経路に入ります。ring の flag 待ちを含む pass が完了しない場合は 120 秒で `prefill: a pass did not finish in 120 s (a ring step's flag never came?)`、比較 kernel が不一致を検出した場合は最終的に `prefill: ring error <値>` になります (`src/split/src/pf_common.cuh:219-236,246-287`; `src/split/src/prefill.cu:1320-1335`)。成功時に `FNX_PF_DMA` 専用の on/off ログは確認できませんでした。

## 根拠

- 候補名は `docs/envvars/000_envvers.md` にありますが、実読み取りは HIP/CUDA 分岐の2箇所です (`src/split/src/prefill.cu:891-898`)。`pf_common.cuh:120,218` はコメント上の参照で、環境変数を読む箇所ではありません。
- 整数 parser と無効値時の例外: `src/split/src/env.hpp:15-22,33-40`。
- build 条件と backend macro: `src/split/CMakeLists.txt:1-5,92-116`。
- ring 内の読み取り先・コピー先と同期: `src/split/src/pf_common.cuh:173-200,216-289`。
- Strata docs を確認しました。`docs/SPLIT_ENGINE.md` は split engine の CUDA/HIP 対応と HIP gfx1201 を扱いますが、`FNX_PF_DMA` の値判定や既定値の追加仕様は見つかりませんでした。値と効果は上記の実装に基づきます。
