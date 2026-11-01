# `DS4_FINISH_SPLIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal 版 DeepSeek V4.1 engine の finish dispatch 後に、現在まとめられている Metal command buffer を終了・commit するかを切り替えます。commit は待機を伴わず、後続 dispatch は同じ Metal queue 上で順序付けられます。対象は `metal/src/engine/ds4_finish.cpp` の `finish()` 経路だけです。通常の CUDA/HIP/SYCL engine ではこの Metal host 実装は呼ばれません。

## 値と判定

環境変数の値を parse せず、`std::getenv()` が null かどうかだけを見ます。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効 |

したがって `DS4_FINISH_SPLIT=0`、`false`、空文字も有効です。数値変換、範囲検査、無効値時の fallback はありません。CLI 引数や別の設定値による優先順位もありません。

## 有効になる条件

- `strata_ds4` を Metal engine としてビルドした場合に限られます。`metal/CMakeLists.txt` は macOS 以外で構成を中断し、DeepSeek engine 用の `strata_ds4` に `ds4_finish.cpp` と `ds4_kernels.cu` を含めます。
- 呼び出し元では `STRATA_METAL` 定義時だけ `metal_host::finish()` を試します。Metal host 処理が成功して `true` を返した場合に限り、その先の split 判定に到達します。
- `n_vec <= 0` または `len <= 0` なら `finish()` は先に成功 return し、split 判定を行いません。
- 判定が有効でも、実際に `split_runs()` を呼ぶには `f.quant != 0` が必要です。`f.quant == 0` の finish では効果がありません。

## 実行時の詳細

`finish()` は Metal kernel dispatch を `g_cx->run({d})` で追加した後、関数内 static の `split_after` を初期化します。これは最初にこの行まで到達した時点の設定有無をプロセス内で cache し、その後の環境変更は読み直しません。値の読み取り時点より前に設定されている必要があります。

`f.quant` が非ゼロで `split_after` が true なら `g_cx->split_runs()` を呼びます。これは蓄積 dispatch を独立した command buffer として commit しますが完了を待ちません。runtime 実装は必要に応じて stream 間の pending copy を同期してから commit し、同じ queue 上の後続 buffer は順序どおりに実行します。対象コードには、この変数専用のログ、警告、終了コードはありません。

同じ finish の直後には別設定 `DS4_FLUSH_FINISH_CTX` と `DS4_FLUSH_FINISH` の判定もあります。前者は設定があり `f.quant` が非ゼロなら `atoi` 値 `2` で追加の `split_runs()`、それ以外の値で `flush_runs()` を呼びます。後者は `atoi` 値と finish 引数の条件が一致した場合に `ds4_metal_flush()` を呼びます。これらは `DS4_FINISH_SPLIT` の優先順位ではなく、同じ処理後に評価される別の動作です。

## 根拠

- 全リポジトリでの完全一致検索では、環境変数の読み取りは `metal/src/engine/ds4_finish.cpp:181` の 1 箇所です。同ファイル `:177-189` は dispatch 後の split 条件と隣接する flush 設定を示します。
- Metal の finish dispatch と失敗経路は `metal/src/engine/ds4_finish.cpp:136-190`。初期の無処理 return は `:137`、host view / buffer / pipeline の失敗は `:141-166`、dispatch は `:176` です。
- `f.pdst` と `f.quant` を使った Metal host finish 呼び出し、および失敗時の既存 kernel 経路への続行は `src/dsv41/ds4_kernels.cu:2196-2218`。`finish_kernel<true>` が packed row 経路であることもここにあります。
- command buffer を待たずに commit する動作は `metal/src/mtl_rt.h:112-119` と `metal/src/mtl_rt.mm:796-816` にあります。
- Metal 限定のビルド条件、DeepSeek engine のソース構成、`STRATA_METAL` 定義は `metal/CMakeLists.txt:1-18,132-171`。通常の root CMake では Metal build が含まれないことは `CMakeLists.txt:97` にも記載されています。
- stale read 対策として split を戻す意図と、コメントに記された GPU idle の説明は `metal/src/engine/ds4_finish.cpp:177-182` の実装コメントにあります。これはコメントの説明であり、この調査では性能を再測定していません。
