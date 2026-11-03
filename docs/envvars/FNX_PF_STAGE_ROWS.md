# `FNX_PF_STAGE_ROWS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

全カード分割 engine `strata-split-N` の prompt prefill で、RAM 上にある expert を専用 staging buffer へコピーしてから読むか、RAM 上の位置から chunk ごとに読むかを選ぶ token 数の閾値です。通常の `strata` engine の prefill 設定ではありません。`strata-split-N` は `STRATA_BUILD_SPLIT` が既定 OFF の別 target で、Linux CUDA または HIP ビルド向けです（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:20-30,64-80`）。

## 値と判定

値は共通 helper `fnx::env_int` で、10 進の整数として文字列全体を厳密に parse します。未設定なら既定値 `2048` です。空文字、数字以外、末尾に余分な文字がある値、`long long` の範囲外は整数 parse エラーになります。符号 `+` / `-` は許されますが、読み取り後の有効範囲は `0..INT32_MAX` です。

| 入力 | 結果 |
|---|---|
| 未設定 | `2048` token |
| `0` または正の整数 `0..INT32_MAX` | 受理。prompt の token 数が閾値以上なら staging を試みる |
| 空文字、`abc`、`2048x` など | `FNX_PF_STAGE_ROWS: '<値>' is not a whole number` の例外 |
| 負の整数 | `FNX_PF_STAGE_ROWS: want tokens >= 0, got <値>` の例外 |
| `INT32_MAX` より大きく `LLONG_MAX` 以下の整数 | 同じ `want tokens >= 0` 範囲エラー |
| `LLONG_MAX` を超える整数 | `is not a whole number` の parse エラー |

比較は `tokens.size() >= stage_rows` です。値は初期化時に `int` に保存され、CLI 引数による上書き経路はありません（`src/split/src/env.hpp:15-21,33-40`, `src/split/src/prefill.cu:394,832-836,989-990`）。

## 有効になる条件

- `strata-split-N` がビルドされ実行されていること。split target は任意ビルドで既定 OFF です。CMake は Windows / Apple を除き、CUDA または HIP の場合にだけ split source を取り込みます（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:20-30`）。sFNX の入口は `--serve` を必須とし、engine はそのサーバープロセス内で構築されます（`src/split/tools/sfnx.cpp:72-104,1055-1060`）。
- カードに ExpertCache の slot があること（`w.ec.n_slots != 0`）。この場合に限って `prefill_alloc()` が環境変数を読み、閾値を保存します。slot がないカードではこの名前を読みません（`src/split/src/prefill.cu:832-836`）。
- 閾値以上の prompt で、さらに `stage[0]` が確保されていること。stage buffer の確保量は `FNX_PF_STAGE_MIB` で制限され、既定 384 MiB、0 なら確保量 0 です。buffer がない場合、閾値を満たしても staging には入りません（`src/split/src/prefill.cu:914-940,989-990`）。

## 実行時の詳細

値は Engine 構築中に `prefill_alloc()` が ExpertCache のあるカードごとに読みます。リクエストごとの再読込や static cache はありません。プロセス起動後の環境変更で既に作られた Engine の閾値は変わりません（`src/split/src/engine.cu:31,275`, `src/split/src/prefill.cu:625,832-836`）。

prompt が閾値未満、または stage buffer が無い場合は、RAM の expert を in-place で chunk ごとに読みます。条件を満たす場合は各 expert の参照表を作り、slot 内の expert は device pool を指し、RAM 上の expert は staging buffer に収まるものをコピーします。収まりきらない expert は引き続き RAM 上を直接参照します。layer ごとのコピーは専用 copy stream に積まれます（`src/split/src/prefill.cu:1088-1138`）。したがって、この変数は全 expert を VRAM に常駐させる設定ではなく、staging 経路へ入る prompt 長の下限です。

この変数だけを示すログはありません。`FNX_PF_TIMING` が有効なとき、prefill の timing 行に staging 経路で RAM からコピーした MiB 数と in-place 読み込み MiB 数が追記されます（`src/split/src/prefill.cu:1353-1363`）。

不正値は Engine 初期化中に例外となります。sFNX は初期化失敗を stdout の `ERR <理由>` と stderr の `sfnx: failed: <理由>` に出し、終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1055-1062`）。

## 根拠

- 候補名の全参照を Strata checkout 全体で検索した結果、実際の環境読み取りは `src/split/src/prefill.cu:833` のみです。ほかにある名前の一致はコメントで、別の動的 helper 呼び出しはありません。
- 整数の全体 parse と未設定時 default: `src/split/src/env.hpp:15-21,33-40`。
- ExpertCache 条件と range check: `src/split/src/prefill.cu:832-836`。
- staging buffer の容量条件: `src/split/src/prefill.cu:914-940`。
- prompt 長の比較、expert の配置・コピー: `src/split/src/prefill.cu:982-990,1088-1138`。
- timing 観測と startup error: `src/split/src/prefill.cu:1353-1363`, `src/split/tools/sfnx.cpp:1030-1035,1055-1062`。
