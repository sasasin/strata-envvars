# `STRATA_METAL_STEPPROF_OUT`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal engine の step profiler が集計した barrier group ごとの結果を、指定したファイルへ TSV 形式で出力します。この変数は profiler を起動せず、出力先だけを指定します。測定の起動には別の `STRATA_METAL_STEPPROF` が必要です。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | ファイルを開かず、TSV を出力しない。stderr の測定ログは通常どおり出る。 |
| 空文字 | 設定済みとして `fopen("", "w")` を試みる。通常のファイル名として開けず `nullptr` になるが、Strata は専用の警告を出さない。 |
| パス文字列 | 文字列を加工せず `fopen(path, "w")` に渡す。開けた場合は同名ファイルを truncate して書き込む。 |
| 開けないパス | `fopen` が `nullptr` を返し、その回のファイル出力は行わない。専用の警告・エラー処理はない。 |

空白除去、環境変数内のパス展開、文字列 parse、既定の出力パス、fallback はありません。`getenv` は存在確認と `fopen` の引数取得で呼ばれ、結果を `static` 変数には保存しません。読み取りは profiler が実行される時点です。

## 有効になる条件

- `metal/CMakeLists.txt` の Metal engine は macOS 以外では構成を拒否します。この変数の読み取り箇所も Metal engine の `metal/src/engine/window.cpp` にあります。
- engine の build には `METAL_CPP_DIR` が有効で `STRATA_METAL_ENGINE` が ON であることも必要です。`METAL_CPP_DIR` が未設定なら CMake は device runtime と engine を build せず、`STRATA_METAL_ENGINE` が OFF なら engine 構成をそこで終了します。
- キャッシュ済みの `Window::run` 経路で、`STRATA_METAL_STEPPROF` の `atoi` 結果が今回の `Tn` と一致し、`head` が true であることが必要です。`STRATA_METAL_STEPPROF` と `STRATA_METAL_STEPPROF_AT` は block 内の `static const int` として初回評価結果を保持します。前者が未設定または `atoi` が 0 なら profiler は起動しません。
- 同じ `Tn` の head cache hit 数が `STRATA_METAL_STEPPROF_AT` に達し、かつ streaming (`stream_`) でない場合に `stepprof()` が呼ばれます。`_AT` の既定値は 20 で、こちらも `atoi` を使います。
- この条件を満たした後、`STRATA_METAL_STEPPROF_OUT` が未設定でなければ出力ファイルを試みます。空文字や不正パスであっても profiler の stderr 集計自体は止めません。

## 実行時の詳細

`stepprof()` は decode window の dispatch を barrier group ごとの prefix として GPU で再実行し、group ごとの時間・weight bytes などを集計します。実行は `STRATA_METAL_STEPPROF_REPS` に応じて反復し、既定は 5 回です。出力先を指定した場合、group ごとに次の 6 列をタブ区切りで書きます: group index、dispatch 数、part 名、時間 ms、bytes、先頭 dispatch の pipeline 名（対応名がなければ `?`）。

`strata metal stepprof: ...` の進捗・集計は stderr に出ます。出力先ファイルを開けなかった場合も stderr にその失敗を知らせるログはありません。ファイルへの `fprintf` の戻り値も確認されません。測定中の Metal command buffer が失敗した場合は runtime が stderr に `mtl: command buffer failed: ...` を出してプロセスを終了コード 5 で終了しますが、これは出力先変数の検査ではなく、測定実行中の失敗経路です。

## 根拠

- 候補名の直接参照は `metal/src/engine/window.cpp:474,1915`。コメントに出力用途が記され、実際の読み取り・`fopen` は `1915` 行だけ。
- profiler の呼び出し条件、cache-hit/head 判定、および trigger 側の static cache は `metal/src/engine/window.cpp:1406-1409,1462-1475`。`STRATA_METAL_STEPPROF_AT` の既定値・parse は `1468-1471`。
- group ごとの TSV 列と `fclose` は `metal/src/engine/window.cpp:1912-1936`。stderr の集計は `1939-1953`。`STRATA_METAL_STEPPROF_REPS` の既定 5 と `atoi` は `1878-1879`。
- Metal engine の macOS 条件、`METAL_CPP_DIR` / `STRATA_METAL_ENGINE` の build 条件と build target は `metal/CMakeLists.txt:1-18,50-80,110-130`。
- GPU command buffer failure のログと終了コード 5 は `metal/src/mtl_rt.mm:995-1019`。
