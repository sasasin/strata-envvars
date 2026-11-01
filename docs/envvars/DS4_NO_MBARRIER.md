# `DS4_NO_MBARRIER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata_ds4` の Metal runtime が、遅延 command buffer に単一 dispatch を追加する経路で、連続する dispatch の間に発行する buffer memory barrier を省略します。これは通常経路を変える開発・診断向けのフックです。`DS4_NO_MBARRIER` 自体によるログや警告はありません。

## 値と判定

値の内容は parse せず、`std::getenv("DS4_NO_MBARRIER") != nullptr` で設定の有無だけを判定します。

| 環境変数の状態 | `no_mb` | 対象 dispatch 後の処理 |
|---|---:|---|
| 未設定 | `false` | `memoryBarrierWithScope:MTLBarrierScopeBuffers` を発行 |
| 空文字を含む、何らかの値が設定済み | `true` | barrier を省略 |

したがって `0`、`false`、空文字も設定済みなら有効です。数値変換、値域検査、無効値時の fallback はありません。CLI 引数や別の環境変数との優先順位も実装されていません。

## 有効になる条件

- macOS の Metal runtime のうち、CMake で `STRATA_DS4_RUNTIME=1` を付けて `strata_ds4` に組み込まれる実装が対象です。通常の `strata`（Qwen engine）や他の target はこの macro を付けない、と CMake に記されています。
- `Context::run()` が `STRATA_DS4_RUNTIME` で有効な分岐に入り、`ds.size() == 1 && reps == 1 && !barrier_between` を満たす必要があります。
- `run()` の別経路、`run_graph()`、`run_graph_seg()` には `DS4_NO_MBARRIER` の判定がありません。これらの経路で別途指定された barrier の扱いはこの変数で切り替わりません。
- モデル状態や CLI オプションによる追加条件は、この読み取り箇所にはありません。

## 実行時の詳細

対象分岐では dispatch を `impl_->enc_def` に encode した後、既定で `MTLBarrierScopeBuffers` の memory barrier を追加し、その後必要なら encoder を閉じて新しい encoder を作ります。環境変数が設定されている場合は barrier 呼び出しだけを飛ばします。ソースコメントは、この barrier がないと wrapper ごとに別の `MTLBuffer` を同じメモリに bind するため Metal の hazard tracking が依存を認識できず、後続の reader が古い値を読み、実例として二つ目の matvec の activation quantizer が前の layer の `x` を読んだ、と説明しています。これはソースコメントに記録された観測であり、この調査で再現・測定したものではありません。

判定は関数内の `static const bool` なので、プロセスでこの行に初めて到達した際に一度だけ読み取り、その後は同じ値を使います。したがって、到達後にプロセスの環境を変更しても判定は更新されません。変数専用の結果ログはありません。通常の遅延 command buffer flush では、失敗時に `mtl: deferred command buffer failed: ...` が stderr に出ます。別経路の同期 command buffer は失敗時に `mtl: command buffer failed: ...` を出し `exit(5)` しますが、後者はこの変数の分岐を通る経路ではありません。

## 根拠

- `metal/src/mtl_rt.mm:902-910` — `Context::run()` の runtime 条件と単一 dispatch 分岐。
- `metal/src/mtl_rt.mm:927-946` — dispatch の encode、barrier の省略判定、encoder 更新。barrier 省略時の stale read 事例のコメントは `937-938`。
- `metal/src/mtl_rt.mm:884-895,961-979` — deferred flush と通常同期経路の失敗ログ。
- `metal/CMakeLists.txt:151-169` — `STRATA_DS4_RUNTIME` を付ける object と `strata_ds4` への組み込み、および通常 `strata` などで macro が無効である旨。
- 候補名の全参照検索では実装参照は `metal/src/mtl_rt.mm:939` のみ。共通 env helper や動的な名前による読み取り先はありません。
