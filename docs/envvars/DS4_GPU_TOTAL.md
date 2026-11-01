# `DS4_GPU_TOTAL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の DeepSeek V4.1 runtime が deferred command buffer の GPU 実行時間を累積し、終了時の診断出力に追加します。計算経路や dispatch の動作を変える設定ではありません。コード上の読み取りは `metal/src/mtl_rt.mm` の `add_busy_handler()` にある一箇所です。

## 値と判定

値の parse はなく、`std::getenv("DS4_GPU_TOTAL") != nullptr` で設定の有無だけを判定します。空文字や `0` を含め、環境変数が存在すれば有効です。未設定なら無効です（`metal/src/mtl_rt.mm:756-760`）。

| 環境の状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | 無効 | busy time の完了 callback を登録しない |
| 空文字、`0`、その他の文字列 | 有効 | 対象 command buffer の GPU 時間を累積する |

CLI 引数や別の環境変数による上書き・優先順位はありません。値の不正による警告や fallback もありません。

## 有効になる条件

- `metal/CMakeLists.txt` では `STRATA_DS4_RUNTIME=1` を付けた `metal/src/mtl_rt.mm` の object を `strata_ds4` に組み込みます。通常の Metal runtime と他 target はこの runtime 定義を使いません（`metal/CMakeLists.txt:151-165`）。
- 集計対象は `Context::split_runs()` または `Context::flush_runs()` が commit する deferred command buffer です。両経路で `add_busy_handler()` が呼ばれます（`metal/src/mtl_rt.mm:796-810,855-883`）。`Context::run()` / `run_graph()` / `run_graph_seg()` の同期 command buffer にはこの handler が付かないため、この集計には入りません（同 `:902-999,1002-1035`）。
- `add_busy_handler()` 内の `static const bool` は初回呼び出しで初期化され、そのプロセス内では cache されます。したがって、初回の対象 commit より後に環境を変更しても判定は変わりません（同 `:757-760`）。
- 終了時レポートは `flush_runs()` が呼ばれたとき `std::atexit(ds4_report_counts)` に登録されます（同 `:869-870`）。この関数自体が呼ばれない実行では、同関数によるレポート登録もありません。

## 実行時の詳細

有効時、各対象 command buffer の completion handler は `GPUEndTime - GPUStartTime` を計算し、差が正の場合だけマイクロ秒へ換算して `g_gpu_busy_us` に加算します。合計はプロセス内の累積値です（`metal/src/mtl_rt.mm:755-760`）。

終了時の `ds4_report_counts()` は合計が 0 より大きい場合に stderr へ `mtl: GPU busy (every command buffer) %.1f ms` を出力します。0 の場合はこの行を出しません。同時に、別の集計値である `mtl: %.1f ms GPU, ...` および host wait / encoding 時間も出力します（`metal/src/mtl_rt.mm:767-774`）。この追加計測を有効にするための warning、失敗、終了コード変更は実装にありません。

deferred command buffer の失敗は既存経路で `mtl: deferred command buffer failed: ...` と stderr に出ます（`metal/src/mtl_rt.mm:844-853,884-894`）。`DS4_GPU_TOTAL` 固有の失敗処理はなく、handler は完了後の時間差が正のときだけ加算します。

`docs/DEEPSEEK_MAC.md:97-98` も `DS4_GPU_TOTAL=1` を既定で無効の診断項目として列挙しています。実装上は `1` である必要はなく、設定有無の判定です。

## 根拠

- 全参照の確認: 候補名のコード参照は `metal/src/mtl_rt.mm:756,758-759` のみ。`docs/DEEPSEEK_MAC.md:98` は説明上の記載です。
- 読み取り・cache・累積: `metal/src/mtl_rt.mm:755-760`。
- 対象 command buffer の commit 経路: `metal/src/mtl_rt.mm:796-810,855-883`。
- 終了時の stderr 出力とレポート登録: `metal/src/mtl_rt.mm:767-774,869-870`。
- runtime macro と target の適用範囲: `metal/CMakeLists.txt:151-165`。
