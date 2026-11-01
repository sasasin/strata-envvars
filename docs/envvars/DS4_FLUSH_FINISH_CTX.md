# `DS4_FLUSH_FINISH_CTX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 dsv41 engine の `finish()` が dispatch を記録した後、量子化を伴う finish のたびに共有 `mtl::Context` の処理を区切ります。値の数値変換結果が `2` なら command buffer を commit して待たず、それ以外なら commit して完了を待つ `flush_runs()` を呼びます。未設定なら何もしません。ソース上では診断用の切替で、専用ログはありません。

この実装は macOS 専用の `metal/` CMake プロジェクトに含まれます。CUDA、HIP、SYCL の各ビルドにはこの読み取り箇所がありません（`metal/CMakeLists.txt:1-18,132-146`）。

## 値と判定

| 環境変数の状態・値 | `f.quant == 0` | `f.quant != 0` |
|---|---|---|
| 未設定 | 何もしない | 何もしない |
| 設定あり、`atoi` の結果が `2` | 何もしない | `split_runs()` |
| 設定あり、`atoi` の結果が `2` 以外 | 何もしない | `flush_runs()` |

値は `std::atoi` で変換し、文字列全体の妥当性は確認しません。したがって空文字や数字で始まらない文字列は通常 `0` となり flush を選びます。先頭空白・符号の後に `2` が続く文字列や、`2` の後ろに文字が続く文字列（例 ` 2x`）も `atoi` が `2` を返すため split を選びます。`02` や `+2` も同様です。`-2` は flush です。範囲 clamp や無効値用の fallback はありません。`atoi` が表現できない範囲の値について、このコードは個別の扱いを定義していません。

根拠: `metal/src/engine/ds4_finish.cpp:176-184`。

## 有効になる条件

- `metal/` の macOS 向けビルドであり、`metal/src/engine/ds4_finish.cpp` が dsv41 engine のソースに含まれていること。
- dsv41 の `finish()` が Metal host 実装に到達し、`n_vec` と `len` が正であること。どちらかが 0 以下なら Metal host 関数は成功扱いで早期 return し、環境変数を読みません。
- `FinishIn::quant` が非ゼロであること。`quant == 0` では環境変数の有無を調べますが、何も実行しません。

共通の dsv41 wrapper は、`STRATA_METAL` ビルド時に packed rows と通常の finish の両方から Metal host `finish()` を試し、成功すると CUDA 互換 launch に fallback せず戻ります（`src/dsv41/ds4_kernels.cu:2196-2218`）。Metal ビルドではこの `.cu` が C++ としてコンパイルされ、Metal host 実装とリンクされます（`metal/CMakeLists.txt:132-146`）。モデルの形式や実行モードごとに別の環境変数で優先される処理は、この読み取り箇所にはありません。

## 実行時の詳細

環境変数は finish dispatch ごとに `std::getenv` で読み直され、結果を static cache しません。プロセス起動後に環境を変更した場合も、以降の呼び出しで反映されます。`g_cx->run({d})` の直後に条件分岐するため、変数が設定されていて `f.quant` が非ゼロなら、その finish の後で context 内の dispatch 群を区切ります。

- `atoi(value) == 2` の `split_runs()` は stream の保留コピーを同期した後、batched dispatches を command buffer として commit しますが完了は待ちません。GPU queue の順序により後続 buffer は先行 buffer の後に進みます（`metal/src/mtl_rt.mm:796-816`）。
- それ以外の値で呼ぶ `flush_runs()` は現在の command buffer を commit し、in-flight buffer の完了を待ちます（`metal/src/mtl_rt.mm:855-899`）。
- 先行する `DS4_FINISH_SPLIT` が設定されている場合、`f.quant` が非ゼロならその変数による `split_runs()` が先に呼ばれます。続く本変数の値が `2` なら追加の split は通常 queue 済み buffer がなく no-op になり、`2` 以外なら `flush_runs()` がその in-flight buffer を待つ経路になります（`metal/src/engine/ds4_finish.cpp:177-183`, `metal/src/mtl_rt.mm:796-816,855-899`）。`DS4_FINISH_SPLIT` 自体は最初の finish 時に static cache されますが、本変数は cache されません。

本変数専用のログ、警告、終了処理はありません。同期 flush が完了しなかった場合、`flush_runs()` 側で `mtl: deferred command buffer failed: ...` を stderr に出します。`DS4_ERRINFO` も設定されていれば追加で失敗 buffer 名を記録します（`metal/src/mtl_rt.mm:892-895`）。split 経路ではこの呼び出し自体は待機も完了状態確認もしません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:136-143,162-184` — Metal host finish の入口、dispatch 後の環境変数判定、quant 条件。
- `src/dsv41/ds4_kernels.cu:2196-2218` — packed / non-packed finish から Metal host を呼び、成功時に戻る呼び出し元。
- `metal/CMakeLists.txt:1-18,132-146` — macOS 限定と Metal dsv41 engine への実装組み込み。
- `metal/src/mtl_rt.h:112-119`, `metal/src/mtl_rt.mm:796-816,855-899` — split は非待機 commit、flush は完了待ち。
