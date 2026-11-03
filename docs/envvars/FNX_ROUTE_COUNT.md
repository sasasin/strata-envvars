# `FNX_ROUTE_COUNT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`sFNX` split engine の expert 選択回数を GPU 上で集計する診断・測定用スイッチです。モデルの routing 結果や生成処理を変更せず、各 layer で選ばれた expert の tally を追加で記録します。通常の Strata 実行全般の環境変数ではなく、split engine を使う `strata-split`（CUDA/HIP）と `split_fnx_run`（CUDA）に実装されています（`src/split/CMakeLists.txt:64-80,95-120,153-165`）。

集計配列は `unsigned` の `[decode | prompt][NL][NEXP]` 形式です。各 expert の要素に top-k の選択回数を加算します。結果の保存先は別環境変数 `FNX_ROUTE_FILE` で指定します（`src/split/src/engine.hpp:124-125`, `src/split/src/engine_impl.hpp:144`, `src/split/src/kernels.hpp:260-261`, `src/split/src/kernels.cu:1786-1789`）。

## 値と判定

`fnx::env_flag("FNX_ROUTE_COUNT")` は `env_int(name, 0) != 0` です。未設定なら既定値 0 で無効です。設定されている場合は、空白なしの符号付き base-10 整数として文字列全体を parse し、`long long` の範囲内である必要があります。0 は無効、0 以外（負数を含む）は有効です。`1`, `true`, 空文字、前後空白、数字の後ろに文字がある値、範囲外整数は整数として受け付けられず、`<NAME>: '<value>' is not a whole number` 形式の例外になります。小数・真偽文字列の解釈や値の clamp はありません（`src/split/src/env.hpp:15-22,33-40,51-52`）。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| `0`, `+0`, `-0` | OFF |
| 0 以外の整数（例: `1`, `-2`） | ON |
| 空文字、非整数、整数の前後に空白や文字、`long long` 範囲外 | parse エラー |

## 有効になる条件

- split engine の `strata-split` または `split_fnx_run` が実行されること。CMake では `strata-split` を Linux CUDA/HIP 用に構成し、`split_fnx_run` は CUDA target として定義しています（`src/split/CMakeLists.txt:20-30,64-80,95-120,153-165`）。
- `sfnx` では `FNX_ROUTE_COUNT` が ON の場合、`FNX_ROUTE_FILE` が設定されている必要があります。ファイル名が空文字でも「設定あり」のチェックは通りますが、後のファイル書き込みは成功しません。条件不足または値の parse エラーはモデル読込前に検出されます（`src/split/tools/sfnx.cpp:1007-1012,1040-1048`）。
- `fnx_run` は `FNX_ROUTE_FILE` が設定されている場合に tally 出力を試みますが、counter を有効化するための同じ起動前チェックはありません。従って `FNX_ROUTE_FILE` だけを設定し `FNX_ROUTE_COUNT` を未設定または 0 にすると、空の tally として終了時にエラーになります（`src/split/tools/fnx_run.cpp:1145-1152`）。
- 別変数 `FNX_EXPERT_PROFILE` は、モデルの expert 配置に使うプロファイルの選択です。`FNX_ROUTE_COUNT` が自動で profile を設定したり、CLI 引数で上書きされたりする処理は確認できません（`src/split/src/model.hpp:250-261`, `src/split/src/model.cpp:1491-1498`）。

## 実行時の詳細

`sfnx` は引数解析後、モデルロード前に環境変数を検査します。検査時に tally が有効なら `FNX_ROUTE_FILE` が未設定の場合は `FNX_ROUTE_COUNT needs FNX_ROUTE_FILE` を stderr に出し、終了コード 2 で終了します。無効値の parse 例外も `sfnx: ...` として stderr に出し、終了コード 2 になります（`src/split/tools/sfnx.cpp:1007-1012,1040-1048`）。engine の GPU buffer 割り当て時にも、card 0 で同じ flag を読み、`2 * NL * NEXP` 個のゼロ初期化済み tally buffer を確保します。環境値を `static` に cache する実装ではなく、この buffer 初期化時に評価します（`src/split/src/engine.cu:193-196`）。

decode は各 layer の routing 後に top-k index を集計配列へ加算し、prompt の prefill も別領域へ同様に加算します。集計関数は各 index に対して `atomicAdd(&cnt[topi[i]], 1u)` を行います。カウンターは 32-bit unsigned で、飽和・overflow 検査はありません（`src/split/src/engine.cu:905-914`, `src/split/src/prefill.cu:1276-1281`, `src/split/src/kernels.cu:1786-1789`）。

`sfnx` は応答完了時に tally を host 側へコピーし、`FNX_ROUTE_FILE.tmp` に全配列を書いてから指定先へ rename します。したがって同じファイルは各応答完了ごとに最新 tally で置き換えられます。書き込みまたは rename に失敗すると stderr に `sfnx: FNX_ROUTE_FILE: cannot write ...: route counting stopped` を出し、その後の tally 保存を止めますが、engine の serving は継続します（`src/split/tools/sfnx.cpp:531-551,554-570,846-855`; host へのコピーは `src/split/src/engine.cu:663-669`）。

`fnx_run` はその実行終了時に `FNX_ROUTE_FILE` が設定されている場合、配列を読み出して指定先へ直接 `wb` で書きます。tally が空、ファイルを開けない、または書き込みに失敗すると `FNX_ROUTE_FILE <path>: no tallies (FNX_ROUTE_COUNT=1?) or not written` を stderr に出し、終了コード 1 になります（`src/split/tools/fnx_run.cpp:1145-1152`; route tally 取得は `src/split/src/engine.cu:663-669`）。

## 根拠

- 厳密な整数変換、未設定時の既定値、flag 判定: `src/split/src/env.hpp:15-22,33-40,51-52`
- counter buffer の割当と初期化: `src/split/src/engine.cu:193-196`; buffer 定義: `src/split/src/engine_impl.hpp:144`
- decode / prompt の tally 更新と kernel: `src/split/src/engine.cu:905-914`, `src/split/src/prefill.cu:1276-1281`, `src/split/src/kernels.cu:1786-1789`
- sfnx の出力先検査、起動時エラー、応答ごとの保存と継続動作: `src/split/tools/sfnx.cpp:1007-1012,1040-1048,531-551,554-570,846-855`
- fnx_run の終了時出力とエラー: `src/split/tools/fnx_run.cpp:1145-1152`
- split executable の build 経路: `src/split/CMakeLists.txt:64-80,153-165`
