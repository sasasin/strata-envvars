# `FNX_PF_DMA_BARRIER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

split engine の prefill 用 copy-engine ring で、ホストからデバイスへの非同期 DMA コピーの直後にイベントを同じストリームへ記録し、そのイベントを待つ処理を有効にする。後続のカーネルがコピー完了前に始まらないようストリーム上に順序を置くための設定である。変数を有効にしても DMA 自体を有効化するわけではなく、データ転送方式を選ぶ `FNX_PF_DMA` が別途有効で、実行経路が ring である必要がある（`engine/src/split/src/prefill.cu:1209-1223`、`engine/src/split/src/pf_common.cuh:283-289`）。

読み取りとイベント作成は `Engine` の構築中、各カードの `PfRing` 設定時に行う。値が非ゼロならそのカードでデバイスを選び、タイミング計測なしのイベントを作成して所有リストへ登録する（`engine/src/split/src/prefill.cu:1169-1181,1217-1221`）。CUDA/HIP のどちらでもこの判定は backend 条件で囲まれていない。コメントにある用途の説明は HIP としているが、読み取り・イベント作成コード自体は両方の split backend に共通である（`engine/src/split/src/pf_common.cuh:283-289`、`engine/src/split/CMakeLists.txt:76-92,120-140`）。

## 値と判定

共通 helper `env_int()` が `getenv` で取得し、符号付き十進整数全体として `strtoll` で解析する。未設定時の既定値は `0`。値が整数として解析でき、かつ `0` 以外なら有効となる。`+` / `-` は許可されるが、前後の空白、末尾の文字、空文字、整数範囲外は解析エラーになる（`engine/src/split/src/env.hpp:15-21,33-40`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| split engine の CUDA/HIP 共通判定 | `0`（無効） | `1`, `-1`, `2`（整数として非ゼロ） | `0`, 空文字, `true`, `0anything`, ` 1`, `1 `, 整数範囲外 |

無効な文字列に対する fallback はなく、`FNX_PF_DMA_BARRIER: '<値>' is not a whole number` の例外になる。整数としての上下限チェックや clamp はなく、`long long` に収まる非ゼロ値は同じ有効判定になる（`engine/src/split/src/env.hpp:15-21,33-40`）。

## 有効になる条件

- `FNX_PF_DMA` が非ゼロで、copy-engine ring の DMA 受信が選択されること。`FNX_PF_DMA` 未設定時は HIP では `0`、CUDA では `1`。値が `0` の場合はリング入力をホストメモリからカーネルが読むため、バリアの記録・待機は呼ばれない（`engine/src/split/src/prefill.cu:1209-1216`、`engine/src/split/src/pf_common.cuh:325-336,350-369`）。
- `FNX_PF_RING_SM` が非ゼロでないこと。非ゼロなら `ring_sum()` を使い、copy-engine ring の `pf_ring_run()` には進まない（`engine/src/split/src/prefill.cu:967-975,1693-1699,1762-1769`）。
- HIP では RCCL の all-reduce 経路に入らないこと。`FNX_PF_RCCL` が未設定なら実装定数の既定で有効、設定値が文字列 `0` 以外なら要求されるが、peer push が有効で RCCL のロードと self-test に成功した場合に限り選択される。選択後は ring を実行せず戻る（`engine/src/split/src/hip/rccl_dl.hpp:22,76-90`、`engine/src/split/src/engine.cu:129-142`、`engine/src/split/src/prefill.cu:723-754`）。
- HIP の小チャンク all-to-all が選ばれないこと。peer push 経路で `FNX_PF_A2A_ROWS`（既定 `256`）が正数なら `a2a_rows` が設定され、`C <= a2a_rows && !own_out` の場合に all-to-all とローカル和を実行して戻る（`engine/src/split/src/prefill.cu:994-1010,744-754`）。

`FNX_PF_GATHER` は ring の計画を `direct` / 通常 ring から選ぶが、バリアの値判定を上書きしない（`engine/src/split/src/prefill.cu:1201-1207,1217-1223`）。CLI 引数による上書きはこの読み取り箇所にはない。なお、条件を満たさなくても非ゼロ値なら Engine 構築時のイベント作成までは行われるが、イベントを記録・待機する箇所には到達しない。

## 実行時の詳細

環境値は `Engine` 構築中にカードごとの `PfRing` 設定で読み取られ、非ゼロならカードごとに `cudaEventCreateWithFlags(..., cudaEventDisableTiming)` を呼ぶ。関数内 `static` などのキャッシュではなく、各カード設定時の読み取り結果を `fence_ev` に保持するため、初期化後にプロセス環境を変更しても既存イベントの有無は変わらない（`engine/src/split/src/prefill.cu:1169-1181,1217-1221`）。

実際に ring を実行すると、ホスト側受信バッファからデバイス側バッファへの `cudaMemcpyAsync` の直後に `dma_fence()` が呼ばれる。対象は ADD、GADD（`own_out` を含む）、および OUT の受信コピーである。`dma_fence()` はイベントを同じストリーム `s` に記録し、同じストリームでイベント待ちを登録する。CPU 側の同期待ちや timeout は実装していない（`engine/src/split/src/pf_common.cuh:285-289,302-308,325-336,350-369,383-397`）。

## ログと測定値

この変数を有効にしたことを示す専用ログはない。整数解析に失敗すると、例外メッセージは `FNX_PF_DMA_BARRIER: '<値>' is not a whole number`。`fnx_run` では stderr に `fnx_run: <例外>` を出して終了コード 1、`sfnx` の Engine 初期化失敗では stdout に `ERR <例外>`、stderr に `sfnx: failed: <例外>` を出して終了コード 1 となる（`engine/src/split/src/env.hpp:33-40`、`engine/src/split/tools/fnx_run.cpp:1364-1373`、`engine/src/split/tools/sfnx.cpp:1094-1103,1125-1135`）。対象変数について Strata の資料に条件付き測定値は見つからなかった。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数全体の解析、未設定時の既定値、無効値の例外。
- `engine/src/split/src/prefill.cu:1169-1181,1201-1223` — ring の選択、DMA backend 既定値、環境値の読み取りとイベント作成。
- `engine/src/split/src/pf_common.cuh:283-289,302-308,325-369,383-397` — バリア処理と適用される DMA コピー。
- `engine/src/split/src/prefill.cu:723-755,967-975,1693-1699,1762-1769` — RCCL、小チャンク all-to-all、GPU スレッドリングの迂回経路。
- `engine/src/split/CMakeLists.txt:76-92,120-140` — 共通 prefill ソースを CUDA/HIP split engine としてビルドする構成。
