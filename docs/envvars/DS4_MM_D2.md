# `DS4_MM_D2`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DeepSeek engine の down expert GEMM で、`DS4_MM_DROP` により置き換える引数のうち 1 個を 2 個目のダミーバッファに割り当てます。通常の利用設定というより、引数をダミーに差し替える診断用フックです。`DS4_MM_DROP` が有効でないと、この変数を設定しても処理は変わりません。

## 値と判定

`DS4_MM_D2` の文字列全体を比較せず、`std::atoi` の戻り値を引数番号 `k`（0～3）と比較します。環境変数が未設定なら比較は常に不一致です。空文字や数値に変換できない文字列は `atoi` が 0 を返すため、引数 0 が `DS4_MM_DROP` で選択されている場合に限り、2 個目のダミーバッファが使われます。先頭の空白や符号、数字の後ろの文字列は `atoi` の変換規則に従い、たとえば `" 2tail"` は 2、`"3x"` は 3、`"-1"` は -1 となります。したがって `"2"` 以外の値でも、変換結果が対象番号と同じなら作用します。

| `DS4_MM_D2` | 変換結果 | `DS4_MM_DROP` が該当番号を選択した場合 |
|---|---:|---|
| unset | 比較を行わない | 通常のダミーバッファ |
| 空文字 | 0 | 引数 0 に 2 個目のダミーバッファ。それ以外は通常のダミーバッファ |
| 数字で始まる値 | `atoi` による整数 | 結果が選択番号と一致すると 2 個目、それ以外は通常のダミーバッファ |
| 数字に変換できない値 | 0 | 引数 0 に限り 2 個目、それ以外は通常のダミーバッファ |

`DS4_MM_DROP` は文字列中に `'0'`～`'3'` の文字があるかを `strchr` で検査します。複数番号を含められます。`DS4_MM_D2` の変換結果に一致する番号が選択されなければ、2 個目のバッファは選ばれません。`atoi` の整数範囲外入力の結果は、このコードから保証できません。

## 有効になる条件

- Apple Silicon 向け Metal engine の `strata_ds4` に含まれる処理です。Metal の CMake 設定では `ds4_finish.cpp` と `ds4_iq.cu` が engine に入り、`STRATA_METAL` の定義下で IQ expert の処理から Metal host 関数へ進みます。
- `iq_set_dn()` から down 計算として `mm_set(false, ...)` が実行される必要があります。gate/up 計算では `gate_up` が真なので、差し替えブロックを通りません。
- `mm_set` は `n_exp` または `total_rows` が 0 以下なら早期に成功を返し、IQ type・次元などの条件を満たさない場合や Metal pipeline 準備に失敗した場合は別経路へ戻ります。これらの経路では `DS4_MM_D2` の差し替えは行われません。
- down 計算で `DS4_MM_DROP` が未設定なら差し替え処理自体を通りません。`DS4_MM_DROP` が設定されていても、`DS4_MM_NODN` が設定されていると kernel dispatch 前に成功扱いで戻るため、ダミーバッファは dispatch に使われません。

## 実行時の詳細

`mm_set` は各 down dispatch の組み立て時に `DS4_MM_DROP` を確認し、1～3 番目の引数に加え 0 番目も含む引数番号 0～3 を走査します。drop 指定された番号には 64 MiB のダミーバッファを割り当て、該当番号が `atoi(DS4_MM_D2)` と一致すると `dummy2`、一致しないと `dummy` を `d.args[k]` に設定します。これらのバッファは関数内の `static mtl::Buffer` で保持され、各バッファは最初に必要になった際に確保されます。`DS4_MM_D2` 自体は static cache されず、drop 指定引数ごとの判定時に環境から取得されます。

置換対象は down kernel の引数です。Metal kernel では番号 0 が重み、1 が出力、2 が hidden-state 入力、3 が tile 情報です。dispatch が実行された後、down 結果は別の copy kernel で engine 側の出力へコピーされます。ダミーに置換した引数に対応するデータを使う、または書き込む結果になりますが、この設定による計算結果の正しさや特定の失敗・終了動作はソースから保証されていません。

`DS4_MM_D2` 専用のログや警告はありません。`DS4_MM_DBG` が設定されている場合、差し替え後の各 buffer pointer を引数情報として stderr に出力します。その他の dispatch・pipeline エラーの扱いは共通処理に従い、この変数の値に応じた専用エラー分岐は見つかりませんでした。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2476-2484` — Metal IQ GEMM host 実装の入力条件と早期 return。
- `metal/src/engine/ds4_finish.cpp:2575-2596` — down 側の `d.args` の組み立て。
- `metal/src/engine/ds4_finish.cpp:2606-2618` — `DS4_MM_DROP` 条件、ダミーバッファ確保、`DS4_MM_D2` の取得と `atoi` 比較、debug 出力、`DS4_MM_NODN` による dispatch 抑制。
- `metal/src/engine/ds4_finish.cpp:2620-2634` — down dispatch 後に結果を engine の出力へコピー。
- `metal/src/engine/msl/ds4_mm.metal:88-92,99-129` — down kernel の引数番号と各引数の読み書き。
- `src/dsv41/ds4_iq.cu:1585-1609` — `STRATA_METAL` 下の Metal IQ gate/up・down host 関数呼び出し。
- `metal/CMakeLists.txt:132-146,165-170` — Metal DeepSeek engine が `ds4_finish.cpp` と `ds4_iq.cu` を含み、`STRATA_METAL` を定義する設定。
