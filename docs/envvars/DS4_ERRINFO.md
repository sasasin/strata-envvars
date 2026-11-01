# `DS4_ERRINFO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の DS4 実行ファイルで、失敗した遅延 command buffer の診断情報を追加します。command buffer 作成時に encoder execution status の記録を要求し、実行中の dispatch 名を蓄積します。失敗時には最近の dispatch 名、command buffer の user info、または buffer 内の dispatch 名を stderr に出します。環境変数が未設定でも失敗自体の基本ログは出ます。

## 値と判定

値は parse されず、`std::getenv("DS4_ERRINFO") != nullptr` と同じ設定有無の判定です。

| 状態 | 動作 |
|---|---|
| 未設定 | 追加診断を無効化。command buffer は `commandBufferWithUnretainedReferences` で作成され、dispatch 名を蓄積しない。 |
| 設定あり（空文字を含む） | 追加診断を有効化。値が `0`、`false`、その他の文字列でも同じ。 |

CLI 引数や他の環境変数による優先順位・上書きは、この変数の読み取り箇所にはありません。値は static cache されず、command buffer の作成時、dispatch ごと、および失敗ログ時にその都度読み直されます。従ってプロセス中に環境が変更された場合、作成時の設定と dispatch 名の蓄積・失敗時の追加ログが一致しないことがあります。

## 有効になる条件

- macOS の Metal backend で、`STRATA_DS4_RUNTIME` を付けてビルドされる `strata_ds4` が対象です。CMake は `metal/src/mtl_rt.mm` を通常の `mtl_rt` ライブラリにも含めますが、そのターゲットにはこの macro を付けず、別の `ds4_rt_mm` object target に付けて `strata_ds4` にリンクします。
- DS4 runtime の `Context::run()` が単一 dispatch・`reps == 1`・`barrier_between == false` の遅延 dispatch 経路に入ると、command buffer 作成と dispatch 名の記録に使われます。
- 失敗時の追加ログは `Context::wait_mark()` または `Context::flush_runs()` の待機後に status が Completed 以外の場合だけです。正常完了時にはこの変数による失敗診断は出ません。

## 実行時の詳細

遅延 dispatch 経路で command buffer が必要になると、変数が設定されている場合は `MTLCommandBufferDescriptor` を作り、`retainedReferences = NO` と `MTLCommandBufferErrorOptionEncoderExecutionStatus` を設定して buffer を作成します。dispatch ごとに、変数がその時点で設定されていれば kernel 名を `def_names` に追記します。flush 時にはこの名前列を `inflight_names` に移します。

待機後に command buffer が Completed でない場合、変数の値に関係なく `mtl: deferred command buffer failed: <localizedDescription>` を stderr に出します。さらに `wait_mark()` では設定時に `mtl: recent: ...` と `mtl: info: ...` を出し、`flush_runs()` では設定時に `mtl: failed cb held: ...` と蓄積した kernel 名を出します。このコードはログを出すだけで、ここでは終了処理や fallback を行いません。

## 根拠

- `metal/CMakeLists.txt:151-169` — DS4 runtime 用 object target に `STRATA_DS4_RUNTIME=1` を付け、`strata_ds4` にリンクする構成。通常の `mtl_rt` target は `metal/CMakeLists.txt:33-39`。
- `metal/src/mtl_rt.mm:902-919` — DS4 runtime guard と、遅延 dispatch 経路での設定有無判定・command buffer 作成方法。
- `metal/src/mtl_rt.mm:927-933` — dispatch 実行と kernel 名の蓄積。
- `metal/src/mtl_rt.mm:844-852` — `wait_mark()` の待機後の基本エラー出力と、設定時の recent / user info 出力。
- `metal/src/mtl_rt.mm:871-895` — flush、蓄積名の移動、待機後の基本エラー出力と、設定時の held kernel 名出力。
