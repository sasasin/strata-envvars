# `FNX_BATCH_STATS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata 同梱の split FNX エンジンで、batch verify の window と graph capture の集計を stderr に出します。`sfnx` の batch decoder 経路では、窓の間にかかった時間と `window()` 内の verify / draft の時間も別に集計します。いずれも観測用で、値により推論・生成の選択を変える処理はありません。

## 値と判定

両方の読み取り箇所は `fnx::env_flag("FNX_BATCH_STATS")` を使います。共通 helper は未設定時に既定値 `0` を返し、設定時は `strtoll` で符号付き base-10 整数として文字列全体を parse します。先頭の `+` / `-` は許可されますが、空文字、空白、数字以外の末尾、整数範囲外は有効な整数にならず、`FNX_BATCH_STATS: '<値>' is not a whole number` の例外になります。parse 後は 0 が OFF、0 以外（負数を含む）が ON です。値の clamp はありません。

各読み取り箇所は `static const bool` に結果を保存するため、それぞれ最初に評価された後は同じプロセス内で再読込しません。CLI 引数や別の設定値による上書きはありません。

## 有効になる条件

- `src/split` の FNX エンジンがビルドされ実行される必要があります。このコンポーネントは opt-in で、CMake の `STRATA_BUILD_SPLIT=ON` を必要とし、ソースは Linux CUDA または Linux HIP の split ビルドに含まれます（`src/split/CMakeLists.txt:1-7,64-79`）。
- エンジン側の集計は `Engine::verify_rows()` が実行されたときに評価されます（`src/split/src/engine_common.cu:1049-1058,1199-1201`）。`BatchDecoder::window()` はこの関数を呼びます（`src/split/src/batch.cpp:120-139`）。同じ関数は graph warm-up からも呼ばれるため、統計ブロックは warm-up の verify window も数えます（`src/split/src/engine_common.cu:328-383`）。
- `sfnx` 固有の窓周期集計は `dec` が存在する batch decode に限られます。`dec` は `--batch` の slot 数が 1 より大きく、`FNX_BATCH_DRAFTS` が `off` でないときに作成されます（`src/split/tools/sfnx.cpp:435-445`）。その後、dec があり decode 対象 row がある場合に `window()` を実行し、`FNX_BATCH_STATS` を評価します（同: `572-607,646-679`）。

## 実行時の詳細

`Engine::verify_rows()` 側は呼び出しごとに時刻、window 数、row 数、capture 時間、直前 window からの間隔を集計します。400 ms 以上の間隔は idle として row 数別の間隔集計から除外します。200 window ごとに、window/capture の平均、row 数の平均、起動後平均、capture の累積値、verify window の host/GPU 平均、row 数別の値を stderr に出し、window 数・row 数・row 数別間隔のカウンタを区切りごとに戻します（`src/split/src/engine_common.cu:1202-1252`）。capture 統計には同じ関数内の既存 capture 計測値を使います。

`sfnx` 側は `window()` の前後、直前の `window()` 終了から次の開始まで、`last_verify_ms`、`last_draft_ms` を累積し、100 window ごとに平均時間を stderr に出してその区間の累積値を戻します。窓間隔も 400 ms 以上なら idle として加算しません（`src/split/tools/sfnx.cpp:654-679`）。

無効値による例外は呼び出し元まで伝わります。`sfnx` の実行中なら `ERR ...` を stdout に送り、`sfnx: failed: ...` を stderr に出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1084-1093`）。`split_fnx_run` では `fnx_run: ...` を stderr に出し終了コード 1 です（`src/split/tools/fnx_run.cpp:1364-1373`）。

## 根拠

- `src/split/src/env.hpp:15-21,33-52` — 整数全体の parse、未設定時の既定値、0 以外を真とする flag helper。
- `src/split/src/engine_common.cu:1049-1058,1199-1252` — batch verify 経路の読み取り、初回結果の cache、集計項目と 200 window ごとの stderr 出力。
- `src/split/src/batch.cpp:120-139` — batch decoder から `verify_rows()` への呼び出し。
- `src/split/tools/sfnx.cpp:435-445,572-607,654-679` — sfnx batch decoder の成立条件、周期集計と 100 window ごとの出力。
- `src/split/tools/sfnx.cpp:1030-1035,1084-1093`、`src/split/tools/fnx_run.cpp:1364-1373` — 例外時の観測可能な結果。
- `src/split/CMakeLists.txt:1-7,64-79` — split の build 条件と CUDA/HIP ソース構成。
