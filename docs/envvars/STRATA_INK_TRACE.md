# `STRATA_INK_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 版 Inkling-2 のハイブリッドエンジンで、ルーターが選んだ expert ID をバイナリファイルへ記録する診断用のパス指定です。ルーティングや expert の配置・計算方法を切り替える値ではありません。読み取りと記録処理は `engine/src/inkling2/cuda/ink_hybrid.cuh` の `InkHybridEngine` にあります。同ファイルの CUDA doorbell kernel は M=1 の記録を書き、バッチ経路はホスト側で記録を追加します（`engine/src/inkling2/cuda/ink_hybrid.cuh:1147-1162,1165-1175,1411-1418,2541-2550`）。

この経路は CUDA Inkling backend に限られます。CUDA runner は host expert があるときに `hybrid.start_workers()` を呼び、その中で `trace_open()` を実行します。host expert がなければこの読み取り地点には到達しません（`engine/src/inkling2/cuda/ink_runner.cuh:497-503,1374-1381,1588-1595`; `engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1816`）。

## 値と判定

`std::getenv` で値を取得し、文字列の空／非空だけを判定します。数値・真偽値としての parse、前後空白の除去、大文字小文字変換、値域検査はありません。非空の値全体をファイルパスとして `std::fopen(path, "wb")` に渡すため、既存ファイルがあれば内容を切り詰めて書き込みを開始します（`engine/src/inkling2/cuda/ink_hybrid.cuh:1420-1429`）。

| 条件（build など） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA Inkling hybrid の worker pool 起動時 | 無効 | 空でないパス。例: `trace.bin`、`0`、`true` | 空文字列 |
| 上記以外（別 backend、または hybrid worker pool を起動しない経路） | この実装での読み取りなし | 該当なし | 該当なし |

`0` や `false` も空でなければファイル名として使われます。空白だけの値も trim されず、その文字列のパスです。CLI 引数や別環境変数による上書き・優先順位はこの読み取り処理にはありません。

## 有効になる条件

- CUDA Inkling-2 backend が使われ、モデル初期化で host expert が存在して `hybrid.start_workers()` に進む必要があります。CUDA runner の通常経路と layer-split 経路のどちらも host expert 数を条件にしています（`engine/src/inkling2/cuda/ink_runner.cuh:497-503,1374-1381,1588-1595`）。
- 空でない値のパスを `fopen(..., "wb")` で開ける必要があります。開けなければ警告を stderr に出し、`trace_fp` が null のままなので記録は無効です（`engine/src/inkling2/cuda/ink_hybrid.cuh:1421-1424`）。
- 値が有効でも上記条件を満たさない backend／経路では、この CUDA 実装による記録は行われません。

## 実行時の詳細

読み取りは `start_workers()` から `trace_open()` が呼ばれる際の一度だけです。`trace_fp` がすでに開いている場合は再読込しません。その後にプロセス環境を変更しても反映されません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1418-1423,1779-1816`）。

ファイルを開くと、CUDA 側に `1 << 20` 件分のリング領域と件数カウンターを確保し、stderr に有効化ログを出します。各記録は `InkTraceRec` の 16 byte 構造体で、layer、kind、row、M、top-k の expert ID、seq を含みます。kind 0 は CUDA kernel が M=1 の選択を記録し、kind 1 はバッチ経路が各 row の選択をホストで記録します（`engine/src/inkling2/cuda/ink_hybrid.cuh:1135-1145,1165-1175,1425-1429,2541-2550`）。

記録は `trace_flush(false)` の呼び出しごとに同期するのではなく、32 回に 1 回 CUDA device を同期してリングからファイルへ追記し、`fflush` します。リング容量を超えた場合は古い記録を失います。backend の `stats()` から `stats_total()` が呼ばれると kind 2 の marker を追加し、強制 flush します。engine 解放時にも強制 flush してファイルを閉じます（`engine/src/inkling2/cuda/ink_hybrid.cuh:1431-1456,1473-1480,2397-2400`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:96-114`）。

## ログと測定値

パスを開けない場合、stderr に `[InkHybrid] STRATA_INK_TRACE: cannot open %s\n` を出して戻ります。成功時は `[InkHybrid] expert trace on: %s (16-byte records)\n` を出します（`engine/src/inkling2/cuda/ink_hybrid.cuh:1423-1429`）。

CUDA バッファ確保・初期化の `INK_CK` が失敗した場合は `strata::core::exit_device_error` に渡されます。ファイルへの `fwrite`／`fflush` の戻り値はこのコードで検査されず、別のファイル書き込み失敗ログもありません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1425-1429,1448-1455`; `engine/src/inkling2/cuda/ink_cuda.cuh:34-42`）。この変数について性能測定値は記載されていません。

## 根拠

- 変数の読み取り、空値判定、ファイル open、ログ: `engine/src/inkling2/cuda/ink_hybrid.cuh:1418-1429`
- 記録構造体と CUDA kernel の kind 0: `engine/src/inkling2/cuda/ink_hybrid.cuh:1135-1145,1147-1175`
- worker pool 起動時期と CUDA runner の host expert 条件: `engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1816`; `engine/src/inkling2/cuda/ink_runner.cuh:497-503,1374-1381,1588-1595`
- flush、ring overrun、STATS marker、終了時 close: `engine/src/inkling2/cuda/ink_hybrid.cuh:1431-1456,1473-1480,2397-2400`; stats 経路: `engine/src/inkling2/cuda/ink_cuda_backend.cu:96-114`
- CUDA エラー処理: `engine/src/inkling2/cuda/ink_cuda.cuh:34-42`
