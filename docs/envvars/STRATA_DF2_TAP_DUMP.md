# `STRATA_DF2_TAP_DUMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_DF2_TAP_DUMP` は DFlash2 の prompt tap をバイナリファイルへ追記する研究・診断用の出力先である。値は有効化フラグではなくファイルパスとして `std::fopen(path, "ab")` に渡される。dump は DFlash2 の context 更新の前に試みられる。値を使った分岐は dump の実行だけで、DFlash2 の選択条件そのものには使われない（`engine/src/program/generate.cpp:241-255,13609,24151-24156`）。

## 値と判定

| ビルド／経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `df2_tap_dump()` が呼ばれる経路 | dump しない | 空文字列でない任意の文字列をファイルパスとして使用。`0` や `false` も文字列どおりのパス | 空文字列。値の形式検証やフラグ・数値変換はない |

`getenv` の結果が null、空文字列、または tap の `rows <= 0` なら何もしない。大文字小文字や空白の解釈、数値の境界判定はなく、空でない値はそのままパスに使う。たとえば `STRATA_DF2_TAP_DUMP=0` は無効化値ではなく、名前が `0` のファイルを開こうとする（`engine/src/program/generate.cpp:244-249`）。

## 有効になる条件

- Strata が DFlash2 を使い、prompt tap を受け取る callback に到達すること。CLI の通常生成では `use_df2` のとき tap を登録し、serve では DFlash2 が正常に準備できた単一 GPU 経路で登録する（`engine/src/program/generate.cpp:8151-8158,24151-24156,13584-13610`）。
- DFlash2 を含む CUDA/HIP build と Metal build が対象になり得る。CUDA/HIP 共通 engine は `STRATA_HAVE_DFLASH2` を定義し、Metal も同じ `generate.cpp` を実行ファイルに使い同 macro を定義する。Metal では `cudaMemcpy` 呼び出しが Metal compatibility wrapper を通る（`engine/cmake/strata_gpu_engine.cmake:6-13`; `engine/metal/CMakeLists.txt:89-93,154-177`; `engine/metal/include/metal_compat/cuda_runtime.h:77-87,157`）。対象名の設定だけでは DFlash2 は選択・起動されず、DFlash2 の選択や起動成功が別途必要。
- serve の multi-GPU layer-split 経路では、各 stage の `on_taps` callback は tap を landing buffer に集約して `df2.context()` を呼ぶが、`df2_tap_dump()` を呼ばない。その経路ではこの変数による dump は発生しない（`engine/src/program/generate.cpp:13550-13573,13607-13613`）。
- 別の環境変数や CLI 値による dump パスの上書き・優先順位はない。

## 実行時の詳細

関数ローカルの `static const char*` が `df2_tap_dump()` の初回呼び出し時に `getenv` を実行し、その後は同じ値を使う。プロセス起動時の一括読み取りではなく、初回 callback より後の環境変更は再読込されない（`engine/src/program/generate.cpp:244-246`）。

各 callback で device 上の `rows * floats_per_row` 個の `float` を host vector に `cudaMemcpy` し、ファイルを append binary (`"ab"`) で開いて、`int64 pos0`、`int64 rows`、続けて `rows * floats_per_row` 個の float32 を書き込んで閉じる。`floats_per_row` は DFlash2 の tap layer 数と `g.n_embd` の積で渡される（`engine/src/program/generate.cpp:247-254,13609,24155`）。同一ファイルが既にある場合は上書きではなく追記になる。

dump 関数内では device-to-host copy が失敗すると何も書かずに戻り、ファイルを開けない場合も黙って終わる。`fwrite` / `fclose` の結果も検査せず、dump 固有のエラーを caller に返さない。その後の DFlash2 context 更新は通常どおり試行される（`engine/src/program/generate.cpp:247-255,13609,24155`）。

## ログと測定値

dump の成功・失敗を示す専用ログはない。ファイルを開けない場合や device copy に失敗した場合も、この関数からは警告・エラーを出さない（`engine/src/program/generate.cpp:247-255`）。

## 根拠

- `engine/src/program/generate.cpp:241-255` — dump 関数、読み取り、値判定、コピー、追記形式。
- `engine/src/program/generate.cpp:13550-13573,13584-13613` — serve の単一 GPU と layer-split での callback の違い。
- `engine/src/program/generate.cpp:8151-8158,24151-24156` — DFlash2 の存在条件と通常生成 callback。
- `engine/cmake/strata_gpu_engine.cmake:6-13`; `engine/metal/CMakeLists.txt:89-93,154-177`; `engine/metal/include/metal_compat/cuda_runtime.h:77-87,157` — CUDA/HIP と Metal の DFlash2 build／copy 経路。
