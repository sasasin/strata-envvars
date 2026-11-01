# `GDN_BENCH_SPLIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前は通常の Strata 実行ファイルの設定ではなく、HIP 用 GDN prompt stage の手動測定ツール `hip_gdn_stage_bench` が読むベンチマーク専用環境変数です。通常の測定経路では、全長を一度に処理した出力・state hash と、奇数位置で二回に分けて処理した hash を比較する処理を省略できます。HIP が有効な構成でビルドされるツールですが、CMake の `add_test` には登録されていません。

## 値と判定

`main()` の開始時に `getenv()` と `atoi()` で判定し、結果を `do_split` に保持します。文字列全体の検証やエラー報告はありません。

| 値 | 通常測定経路での動作 |
|---|---|
| 未設定 | split-call の処理を行う（既定） |
| `0` に変換される設定値 | split-call の処理を省略 |
| それ以外の整数に変換される設定値 | split-call の処理を行う |

変換は C の `atoi` によるため、たとえば空文字や数値で始まらない文字列は `0` となり split-call を省略します。`1suffix` は `1` として扱われ、`-1` は 0 以外なので split-call を行います。先頭の空白や符号なども `atoi` の変換規則に従います。無効文字列への警告、既定値への別 fallback、値の clamp はありません。

## 有効になる条件

- CMake の `STRATA_ENABLE_HIP` が有効なときに `hip_gdn_stage_bench` ターゲットが定義されます。通常の Strata アプリや CUDA 専用の設定として使われる読み取り箇所は確認できません。
- `GDN_BENCH_CHECK` が設定されている場合、ベンチは比較チェック経路に入り、そこで split-call の比較を無条件に実行して早期 return します。この経路では `do_split` は参照されないため、`GDN_BENCH_SPLIT` でチェック内の split-call を止めることはできません。
- ツールの CLI 引数は測定する系列長を指定します。`GDN_BENCH_SPLIT` と CLI 引数、または別の Strata 環境変数との優先順位・上書き関係はありません。

## 実行時の詳細

環境変数はプロセスの `main()` 内で一度評価され、`do_split` に保存されます。通常測定では、まず全長を処理して出力・state hash を計算します。`do_split` が真なら奇数位置で系列を二分して再処理し、二つの hash が一致するかを `split_same` として出力します。偽なら二分処理を省き、初期値の `same=true` がそのまま `split_same=1` として出力されます。したがって、この出力値は split 比較を実施しなかった場合も一致を表す値になります。

この環境変数による警告やエラー経路はありません。ツールは通常経路の各系列について `STAGE ... split_same=...` 行を stdout に出します。`GDN_BENCH_CHECK` 経路ではチェック結果を `CHECK ...` 行に出し、環境変数による skip はありません。CUDA API の失敗は共通の `ck()` から stderr にエラー文字列を出して終了コード 2 で終了しますが、これはこの環境変数固有の失敗処理ではありません。

## 根拠

- `tests/hip/gdn_stage_bench.cpp:8-10,51-57` — ツールの説明、既定系列長、環境変数の読み取りと `atoi` 判定。
- `tests/hip/gdn_stage_bench.cpp:103-104,140-154` — `GDN_BENCH_CHECK` 経路が `do_split` を使わず比較して早期 return する。
- `tests/hip/gdn_stage_bench.cpp:174-190` — 通常経路の hash 計算、split-call の省略条件、`split_same` の出力。
- `tests/hip/gdn_stage_bench.cpp:25-26` — CUDA API エラー時の stderr 出力と終了コード。
- `CMakeLists.txt:1016-1018,1079-1082` — HIP 有効時のターゲット定義と、手動測定用で `add_test` にしない旨。
