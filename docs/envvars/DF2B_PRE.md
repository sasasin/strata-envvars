# `DF2B_PRE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の開発・診断用 `dflash2_bench gemm` が GEMM 計測用データを作る前に、指定した種類の GPU メモリ確保と初期化を行います。ベンチ開始時の GPU メモリ使用状況や確保順を変えるためのフックです。通常の Strata エンジンやサーバーの実行経路からは読み取られません。

## 値と判定

値を整数などには変換せず、文字列全体に対して大文字小文字を区別する部分文字列検索をします。6 個の判定は独立しているため、1 つの値で複数の処理を選べます。

| 環境変数の状態・内容 | 動作 |
|---|---|
| 未設定 | 先行確保を行わない |
| 空文字 | 設定自体は検出するが、どのキーワードも含まないため何もしない |
| `rope` を含む | 64 個の `double` を確保し、`df2_rope_inv(10000.0f, ...)` を実行して queue を待つ |
| `head` を含む | `make_head()` でベンチ用の Q8_0 head データを生成・転送する |
| `cb` を含む | `VOCAB * RANK` 個の `uint16_t` を `0x3c00` で埋め、GPU に確保・転送する |
| `ring` を含む | `RING * NKV * HD` 個の float 配列を 10 個生成・転送する |
| `layers` を含む | 5 回、各回で `make_mat(I,N)` 2 個、`make_mat(N,I)` 1 個、`make_mat(4096,N)` 1 個を生成・転送する |
| `host` を含む | `strata::host_malloc_polled` で 128 バイトと 256 バイトを確保する |
| 上記以外の文字列 | 先行確保を行わず、警告や fallback もない |

判定は `find(...) != std::string::npos` なので完全一致ではありません。たとえば `my-head-test` は `head` に一致し、`ROPE` や `HEAD` は一致しません。数字、空白、区切り文字、無効値としての形式検査はありません。複数キーワードを含む値は該当処理をすべて実行します。既定値は先行確保なしです。CLI 引数や別の環境変数による優先・上書きはありません。

## 有効になる条件

- `dflash2_bench` がビルドされていること。CMake の SYCL 側ターゲットとして定義されています。
- 起動時のモード引数が `gemm` であること。引数省略時は `bench` になり、この環境変数を読む関数には入りません。`test`、`attn` など他のモードでも読みません。
- `dflash2_bench` は `sycl::gpu_selector_v` で SYCL GPU queue を作成します。この実行ファイルが動作できる SYCL 環境が必要です。

## 実行時の詳細

`DF2B_PRE` は `run_gemm_bench()` 内で、他の `DF2B_HOSTALLOC`、`DF2B_BIGALLOC_MB`、`DF2B_NALLOC`、`DF2B_NMED` による確保と queue wait の後、通常の GEMM ベンチ用行列を作る前に一度読みます。`static` cache はなく、各 `gemm` 実行で読み直します。プロセス実行中に環境を書き換えた場合の再評価はありません（読み取り箇所がこの関数の一度だけです）。

確保したデバイス側ポインターは呼び出し元に保持されず、ここでは解放もされません。したがって、選んだ先行確保は後続の GEMM 計測中も確保状態のままです。すべての該当処理の後に queue を待ち、その後 `device: ...` を標準出力に出して GEMM の測定表に進みます。ここで新しい測定値や速度効果を出力する処理はありません。

`dev()` を通る GPU allocation が失敗した場合は、標準エラーに `out of device memory (<bytes> bytes)` を出し、終了コード 2 でプロセスを終了します。`DF2B_PRE` の値自体に対する警告やエラー経路はありません。

## 根拠

- 候補名の全参照は `sycl/src/kernels/dflash2_bench.cpp:621` の直接 `std::getenv` のみです。helper 経由または動的な名前の参照はありません。
- 読み取り、各キーワードの判定、処理順、queue wait は `sycl/src/kernels/dflash2_bench.cpp:614-630`。
- GEMM mode への分岐、既定の `bench` mode、GPU queue の作成は `sycl/src/kernels/dflash2_bench.cpp:894-901`。
- `dflash2_bench` ターゲット定義は `sycl/CMakeLists.txt:437-438`。
- デバイス確保失敗時の stderr と終了コードは `sycl/src/kernels/dflash2_bench.cpp:61-63`。各先行確保が生成・転送するデータの実装は同ファイルの `68-83`（行列・float 配列）と `106-117`（head データ）。
