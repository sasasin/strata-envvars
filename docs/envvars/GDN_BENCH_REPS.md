# `GDN_BENCH_REPS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

HIP 用の手動計測ツール `hip_gdn_stage_bench` が、各 prompt 長でゲート・畳み込みと recurrence/output の計測を何回行うかを指定します。Strata の通常の生成処理が読む環境変数ではありません。この実行ファイルは `STRATA_ENABLE_HIP` の CMake 分岐内で作られ、`add_test` には登録されない手動計測ツールです（`CMakeLists.txt:1016-1018,1079-1082`）。

## 値と判定

`main()` の冒頭で `std::getenv("GDN_BENCH_REPS")` を一度呼び、設定されていれば `std::atoi` で `int` に変換し、`std::max(1, ...)` で最小 1 にします。未設定なら既定値は 7 です（`tests/hip/gdn_stage_bench.cpp:51-56`）。

| 入力 | 計測回数 `reps` |
|---|---:|
| 未設定 | 7 |
| 空文字 | 1（`atoi` が 0 を返し、最小値に clamp） |
| 先頭から整数として読める値 | 変換結果と 1 の大きい方。例: `4` → 4、`0` / `-2` → 1 |
| 数字で始まらない文字列 | 1（変換結果 0） |
| 整数の後ろに文字がある文字列 | 数字部分の変換結果と 1 の大きい方。例: `3x` → 3 |

文字列全体の形式検査や上限 clamp はありません。`atoi` が `int` で表せない値を受け取った場合の結果はコードで定義されていません。CLI 引数は計測対象の prompt 長 `T` を指定するもので、反復回数を上書きする CLI 引数はありません（`tests/hip/gdn_stage_bench.cpp:51-56`）。

## 有効になる条件

- `STRATA_ENABLE_HIP` が有効な CMake 構成で `hip_gdn_stage_bench` をビルドし、その実行ファイルを起動した場合だけ読み取られます。通常の Strata CLI / サーバー経路にこの読み取りはありません（`CMakeLists.txt:1016-1018,1079-1082`）。
- `GDN_BENCH_CHECK` が設定されていると、回数を読み取った後に比較チェックを実行して終了し、計測ループへ進みません。その場合 `GDN_BENCH_REPS` は計測回数に影響しません（`tests/hip/gdn_stage_bench.cpp:55-56,103-104,153-155`）。
- `GDN_BENCH_SPLIT` は分割呼び出し hash の有無を変えますが、反復回数を変えません（`tests/hip/gdn_stage_bench.cpp:57,181-188`）。

## 実行時の詳細

値はプロセス起動後、`main()` の最初にローカル変数 `reps` として評価されます。後から環境を変更して再評価する cache や、子プロセスへの転送はありません。各 `T` についてループは `round = -2` から `round < reps` まで実行され、最初の 2 回は timing vector に追加されずウォームアップとして捨てられます。残る `reps` 回の計測値を昇順に並べ、`size()/2` 番目を採用します（偶数回の場合は中央 2 値の平均ではなく、後ろ側の中央値です）。結果は `STAGE` 行として stdout に出力されます（`tests/hip/gdn_stage_bench.cpp:155-173,189-190`）。

この環境変数自体に専用の警告・エラー出力はありません。GPU API 呼び出しに失敗した場合は共通の `ck()` がエラー文字列を stderr に出し、終了コード 2 でプロセスを終了します。これは計測回数の値検査による経路ではありません（`tests/hip/gdn_stage_bench.cpp:25-27`）。

## 根拠

- 唯一の読み取りと既定値・clamp: `tests/hip/gdn_stage_bench.cpp:55-56`。
- 計測ループ、ウォームアップ、中央値: `tests/hip/gdn_stage_bench.cpp:155-173`。
- HIP 専用の手動計測ターゲット: `CMakeLists.txt:1016-1018,1079-1082`。
- 候補一覧: `docs/envvars/000_envvers.md:377`。`rg -n --hidden --glob '!.git/**' 'GDN_BENCH_REPS'` で確認した参照は上記ソースのコメントと `getenv` 呼び出しのみです。
