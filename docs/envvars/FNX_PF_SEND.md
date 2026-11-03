# `FNX_PF_SEND`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Qwen3.8-Flash-Next の split engine が prompt の chunk sum をカード間で ring 交換するとき、送信側 GPU device buffer から次カードの host buffer へのコピー方法を選びます。既定は `cudaMemcpyAsync` で、指定値 `kernel` のときだけ GPU kernel によるコピーを使います。受信コピーや attention の部分結果転送を切り替える設定ではありません。

## 値と判定

初期化時に `std::getenv("FNX_PF_SEND")` の値全体を `std::strcmp(..., "kernel") == 0` で比較します。

| 値 | 判定 | 送信コピー |
|---|---|---|
| 未設定 | 無効 | `cudaMemcpyAsync(..., cudaMemcpyDefault, stream)` |
| 空文字 | 無効 | `cudaMemcpyAsync` |
| 小文字の完全一致 `kernel` | 有効 | `k_pfr_copy` kernel |
| `Kernel`、`KERNEL`、`kernel `、その他の文字列 | 無効 | `cudaMemcpyAsync` |

数値変換、範囲検査、無効値の警告やエラーはありません。CLI 引数や別環境変数による優先順位もありません。`FNX_PF_DMA` は受信・gather 側の DMA を設定し、`FNX_PF_SEND` の判定を上書きしません。

## 有効になる条件

- split engine の Flash-Next prefill が動き、複数カード間の prompt chunk sum が `pf_ring()` の ring 経路を通ること。
- `FNX_PF_RING_SM` が 0（未設定時の既定）で、GPU-thread ring の `ring_sum()` 経路ではないこと。
- HIP では RCCL all-reduce が有効になっていないこと。RCCL 経路は ring kernel を呼ばずに戻るため、この設定を使いません。CUDA ではこの RCCL 分岐自体がありません。

値の読み取りと `send_kernel` の保存は `Engine` の prefill buffer 初期化時に各カードの `PfRing` ごとに行われます。設定を後から変更しても既に保存された値は変わりません。該当する環境変数読み取りの `static` cache はありませんが、この engine の構築後に再評価するコードもありません。CLI からの上書きや子プロセスへの個別転送は確認できません。

## 実行時の詳細

ring plan の `SEND` 操作で `copy()` が呼ばれます。有効時は `nrows > 0` の場合に `k_pfr_copy` を同じ stream に enqueue し、0 行なら何も enqueue しません。無効時は行数にかかわらず `cudaMemcpyAsync` を呼びます。続く ring plan の flag 操作も同じ stream 上に置かれます。kernel は各 `uint4` を送信元から宛先へコピーし、HIP のこの呼び出しでは `sysfence` の既定値 0 のため system fence 分岐には入りません。

この環境変数に固有のログ、警告、終了経路はありません。ring 実行後は `cudaGetLastError()` を `ckc(..., "ring")` に渡して GPU API / kernel launch のエラーを検査します。読み取り文字列が `kernel` 以外でも、その値自体を理由に失敗することはありません。

## 根拠

- `src/split/src/prefill.cu:296-310` は `PfRing::send_kernel` の既定値を `false` とし、`:883-905` で backend 別の ring 設定とともに `FNX_PF_SEND` を完全一致判定して各 ring に保存します。
- `src/split/src/prefill.cu:510-535` は RCCL 経路が all-reduce 後に戻り、そうでなければ `pf_ring_run()` の後に ring エラーを検査することを示します。
- `src/split/src/prefill.cu:738-745,1243-1244,1304-1305` は `FNX_PF_RING_SM` が有効なとき prompt ring sum が `ring_sum()` に進むことを示します。
- `src/split/src/pf_common.cuh:167-192,209-230` は ring の SEND 操作が選択された copy 実装を呼び、`k_pfr_copy` または `cudaMemcpyAsync` を使うことを示します。
- `src/split/src/pf_common.cuh:108-115` は `k_pfr_copy` が `uint4` 単位でコピーし、HIP では `sysfence` 指定時だけ system fence を実行することを示します。

