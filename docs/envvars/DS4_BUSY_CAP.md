# `DS4_BUSY_CAP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の DeepSeek V4.1 エンジンで、CPU lane が CPU 側 expert を処理している間に別の Metal command queue で動かす busy-spin kernel の反復上限を指定します。値が大きいほど kernel が自分で終了するまでの反復上限が増えますが、CPU lane の完了時には共有 flag により kernel が途中で抜けられます。

この設定は `strata_ds4` の Metal 経路に限られます。通常の `strata` ターゲットには `STRATA_DS4_RUNTIME` を付けず、DS4 用に別コピーをコンパイルする構成です。

## 値と判定

`ds4_busy_begin()` が呼ばれ、busy kernel の初期化が成功し、すでに実行中でない場合に環境変数を読みます。未設定なら `20000`、設定されていれば `std::atoi()` の結果を `uint32_t` に変換します。文字列全体の検証や範囲チェックはありません。

| 環境変数の値 | `cap` の扱い |
|---|---|
| 未設定 | `20000` |
| 空文字 | `atoi("")` が `0` となり、`0` |
| 10進整数として読める文字列 | `atoi` が先頭の整数部分を読み、`uint32_t` に変換。例: `123tail` は `123` |
| 数字部分がない文字列 | `atoi` が `0` を返すため `0` |
| 負の整数 | `atoi` の `int` 結果を `uint32_t` に変換するため、負数は符号なし値になる |
| `int` で表せない範囲 | `atoi` の範囲外動作に依存し、Strata 側に検出・fallback はない |

先頭空白と符号は `atoi` の整数変換規則に従い、数値の後ろにある非数字は検査されません。`cap == 0` の場合も command buffer は dispatch されますが、kernel の `for (i = 0; i < cap; ++i)` 本体は実行されません。

## 有効になる条件

- macOS の Metal 用 `strata_ds4` であること。busy 関数の定義は `STRATA_DS4_RUNTIME` 範囲内で、CMake はこの macro を `ds4_rt_mm` に付け、それを `strata_ds4` にリンクします。
- DS4 モデル処理中に CPU lane 対象の expert があり、その区間で `ds4_busy_begin()` が呼ばれること。Metal 条件下で `ds4_metal_kick()` の後に呼ばれ、CPU expert 処理後に `ds4_busy_end()` が呼ばれます。
- `DS4_BUSY=0` が初回 `ds4_busy_begin()` 呼び出し時に成立していないこと。この変数は関数内の `static const bool` で一度だけ判定され、完全一致の文字列 `"0"` なら busy kernel の開始を抑止します。空文字や `00` は抑止しません。
- `DS4_BUSY_ALL` が設定されていれば `forward()` の開始・終了でも begin/end が呼ばれますが、ここでも `DS4_BUSY=0` の判定が優先して開始を止めます。

## 実行時の詳細

busy kernel は `MTLCreateSystemDefaultDevice()` で device を得て、MSL source の library と `busy_spin` pipeline を作成します。pipeline ができると queue と shared flag buffer を作成して `g_busy.ok` を立てますが、queue と buffer の戻り値は個別に検査されません。その後、2つ目の queue へ command buffer を commit します。`cap` は static cache ではなく、この開始ごとに読み取られます。したがって、プロセス実行中の環境変更も、その後の `ds4_busy_begin()` に反映され得ます。ただし `DS4_BUSY` 自体の on/off 判定は初回呼び出し後に変わりません。

kernel は各反復で整数・浮動小数点演算を行い、共有 flag が非ゼロになるとループを抜けます。`ds4_busy_end()` は busy 状態で有効な command buffer があれば flag を `1` にして `running` を解除します。次の開始時は前回 command buffer の完了を待ってから flag を `0` に戻します。`DS4_BUSY_W` は dispatch width（threadgroup 数）を変える別設定で、`DS4_BUSY_CAP` の値判定には関与しません。

この経路に `DS4_BUSY_CAP` 固有のログや値のエラー報告はありません。device/library/pipeline の初期化が成立せず pipeline が得られない場合、`g_busy.ok` が立たず開始関数は戻ります。queue と buffer の作成失敗は個別に確認されず、その先の Metal API 呼び出しに進みます。値が0の場合や無効な数値文字列の場合もエラーを出さず、反復数0の kernel dispatch になります。kernel が `cap` に達して自然終了するまでの時間、GPU のクロックや性能への効果はソースから保証できません。

## 根拠

- `metal/src/mtl_rt.mm:220-222,235-237`: busy kernel の役割と `DS4_BUSY=0` の抑止判定。
- `metal/src/mtl_rt.mm:239-264`: Metal device、library、pipeline、queue、flag buffer の初期化。
- `metal/src/mtl_rt.mm:245-254`: `cap` までの演算反復と flag による早期終了。
- `metal/src/mtl_rt.mm:266-282`: 開始条件、前回 command buffer の待機、`DS4_BUSY_CAP` の取得、GPU への引き渡しと commit。
- `metal/src/mtl_rt.mm:285-289`: 終了時に flag を立てて `running` を解除。
- `src/dsv41/ds4_model.cu:9693-9699,10555-10566`: 全 step 用 `DS4_BUSY_ALL` 経路と CPU expert 処理区間の begin/end。
- `metal/CMakeLists.txt:151-169`: `STRATA_DS4_RUNTIME` 付き runtime object と `strata_ds4` target の構成、および Metal model macro。
