# `FNX_PF_DMA_BARRIER`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリ・GPU driver の環境変数動作は対象外。

## 役割

`strata-split` の prompt ring で、DMA による host→device コピーを投入した後、同じ CUDA/HIP stream に event の record と wait を挿入します。これによりコピー後に続く ring の加算 kernel より前に、そのイベント依存を stream に置きます。コードコメントでは、copy engine と compute queue の順序が runtime によって常に保証されるわけではない経路への対処として説明されています。

この変数は通常の Strata エンジン全般の設定ではありません。対象コードは `STRATA_BUILD_SPLIT` で別途ビルドする、2〜4 GPU の strata-split 実行ファイルにあります。split 機能自体は既定でビルドされず、Linux CUDA または Linux HIP の構成が対象です。

## 値と判定

`src/split/src/prefill.cu` は `env_int("FNX_PF_DMA_BARRIER", 0)` を評価し、結果が 0 以外ならイベントを作成します。整数全体を厳密に読む helper です。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 既定値 `0`。イベントを作成しない |
| `0` | イベントを作成しない |
| `1`、`-1`、`+2` など、範囲内の整数で 0 以外 | イベントを作成する。正負や大きさによる追加の制限はない |
| 空文字、空白、数字以外を含む値、符号だけ、`1x`、`long long` の範囲外 | 整数として拒否し、`FNX_PF_DMA_BARRIER: '<値>' is not a whole number` の `std::runtime_error` を投げる |

先頭・末尾の空白、末尾の文字は許容されず、値全体を base 10 の整数として parse します。CLI 引数による上書きはこの読み取り箇所にはありません。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` で strata-split がビルドされ、その実行ファイルが選ばれること。split は CUDA または HIP の Linux ビルドに限られます。
- prompt の ring が通常の host-memory ring 経路を使うこと。RCCL が有効な場合、`pf_ring()` は RCCL all-reduce 経路から戻るため、この ring の barrier は通りません。
- さらに、`FNX_PF_DMA` によって ring の host→device コピーが有効であること。HIP では `FNX_PF_DMA` の既定値が 0 なので、barrier を設定しても既定状態では使われません。HIP で DMA を使うには `FNX_PF_DMA` に 0 以外の整数を設定します。CUDA では既定値が 1 です。`FNX_PF_DMA=0` の場合、ring 加算 kernel は host 側 slot を直接読み、barrier lambda は呼ばれません。

この変数は DMA 自体を有効化しません。DMA の有無は別変数 `FNX_PF_DMA` で決まり、`FNX_PF_DMA_BARRIER` はそのコピー後の依存を追加するだけです。prompt ring 以外のコピーや attention 用の転送には適用されません。

## 実行時の詳細

環境変数は `Engine` 構築中の `prefill_alloc()` で card ごとの `PfRing` を初期化するときに読みます。`env_int` 自体は cache しませんが、各 `Engine` の ring 設定と `fence_ev` はこの初期化時に作られ、通常の prompt 処理ごとには読み直しません。イベントは timing 無効で作成され、所有リストへ登録されて解放時に破棄されます。

ring の `ADD` 操作では、`r.dma` が有効で対象行が空でない場合、`cudaMemcpyAsync(..., cudaMemcpyDefault, s)` で host slot から device slot へコピーし、直後に `fence_ev` があれば同じ stream `s` で `cudaEventRecord` と `cudaStreamWaitEvent` を行います。その後に `add(...)` が加算 kernel を投入します。イベントが作られていない場合、または DMA が無効な場合には、この event 操作を行いません。

不正値は helper の `runtime_error` になります。CUDA/HIP event 作成・記録・wait の失敗も `ckc` が `prefill: event: ...` または `prefill: dma fence: ...` の例外にします。どの最上位ログや終了コードになるかは起動側の例外処理に依存します。確認できた `fnx_run` では例外文字列を stderr に `fnx_run: ...` と出して終了コード 1 を返します。

## 根拠

- 候補一覧の掲載: `docs/envvars/000_envvers.md:560`（候補一覧であるため、実装根拠には使用していません）。Strata 内の全参照検索では、実際の読み取りは以下の `env_int` 呼び出し一箇所で、その他はコメントの記述でした。
- 実読み取り、event 作成、card ごとの ring 初期化: `src/split/src/prefill.cu:866-905`。
- `env_int` の未設定既定値、整数全体 parse、無効値の例外: `src/split/src/env.hpp:15-22,33-40`。
- DMA の HIP/CUDA 既定値と `FNX_PF_DMA` 条件: `src/split/src/prefill.cu:891-903`。
- コピー後の barrier と `ADD` kernel の順序、DMA が無効な場合の host slot 読み取り: `src/split/src/pf_common.cuh:194-227`。
- event/API 失敗を例外にする処理と event の解放登録: `src/split/src/pf_common.cuh:27-29`, `src/split/src/owned.hpp:32-35`。
- strata-split のビルド条件・HIP macro: `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,20-27,92-116`。split の概要と build 手順: `docs/SPLIT_ENGINE.md:1-5,79-82`。
- `fnx_run` の例外ログと終了コード: `src/split/tools/fnx_run.cpp:1364-1373`。
