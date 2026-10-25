# `strata-concurrent --experts`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-concurrent` |
| コマンド | `strata-concurrent` |
| オプション | `--experts` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値。ソース上の範囲検証なし |

## 役割

CPU のストリーミング読み取りと GPU の転送・計算を同時に実行するベンチマークで、読み込む expert 相当データの個数を指定します。これは `strata-concurrent` 専用です。同じ `--experts` は別プログラム `strata-overlap` にもありますが、parser と動作が異なるため別スコープです（`src/core/overlap_main.cpp:41-59`）。

## 使い方

```sh
strata-concurrent --file experts.bin --experts 4096
```

`--file` は必須です。`strata-concurrent` は CMake の GPU 有効時に追加される実行ファイルです（`CMakeLists.txt:356-358`）。この調査ではビルドや実行はしていません。

## 値と既定値

- 既定値は `4096`。同じ実行で複数回指定した場合は、parser が順に代入するため最後の値が使われます（`src/core/concurrent_main.cpp:52-69`）。
- 値は `std::atoi` に渡されます。空文字列や数値に変換できない文字列は `0` になり、数値の後ろに非数値文字が続く場合も数値部分までが変換されます。完全な整数形式・正数・上限の検証はありません（`src/core/concurrent_main.cpp:60-69`）。
- `0` では arena の容量が 0 となり、`PinnedArena` は基底領域を確保せずに戻ります。その後 `valid()` が偽となるため `arena allocation failed` を標準エラーに出し、終了コード 1 で終了します（`src/core/concurrent_main.cpp:82-83`; `include/strata/core/pinned.hpp:45-97`; `src/core/pinned.cu:408-412`）。
- 負数も拒否されず、arena サイズ計算時に `uint64_t` へ変換されます。したがって巨大な確保要求になり得ますが、その後の結果は allocator / OS に依存し、ここでは特定できません（`src/core/concurrent_main.cpp:78-83`）。

## 実行時の動作

プログラム内で固定された寸法 `n_in=2560`、`n_out=640` から `role_codes=409600` byte を算出し、`--experts N` に対して `N * 409600` byte の `PinnedArena` を作ります。既定値 4096 では 1,677,721,600 byte（約 1.56 GiB）です（`src/core/concurrent_main.cpp:78-83`）。

入力ファイルから各 expert 相当レコードについて、1,382,400 byte 間隔で seek し、先頭 409,600 byte を arena に読み込みます。全 N 件を読めなければ `short read` を標準エラーに出して終了コード 1 で終了します。ファイル形式・寸法が合っているかを別途検証する処理はこの CLI にはありません（`src/core/concurrent_main.cpp:84-91`）。

CPU 読み取りループは `--experts` 件分の arena 全体を 64 byte stride で反復します。また GPU 側が回す `--gpu-roles` 回の転送では arena の expert 領域を `i % experts` で選ぶため、データの読み込み・CPU 側の測定領域・GPU 側の巡回範囲はこの値に連動します（`src/core/concurrent_main.cpp:112-123,125-147`）。CPU の同時スレッド数は別 option `--cpu-threads` で制御され、既定値は 6 です（`src/core/concurrent_main.cpp:57-59,149-156`）。

## 適用条件と副作用

- `strata-concurrent` が組み込まれる GPU 有効ビルドが必要です（`CMakeLists.txt:356-358`）。
- 起動時に大きさが変わる pinned arena を確保し、指定ファイルを読み、CUDA device buffer と stream を作成してベンチマークを実行します。このオプションは通常の推論設定ではなく、診断・測定用プログラムの workload サイズです（`src/core/concurrent_main.cpp:82-110,149-178`）。
- Arena 確保失敗は `arena allocation failed`、入力を開けない場合は `cannot open <path>` として標準エラーに出力し、終了コード 1 です。ファイルの末尾不足は `short read` となり同じく終了コード 1 です（`src/core/concurrent_main.cpp:82-91`）。
- `--experts` に値がない場合は `<option> needs a value` と標準エラーに出して、その場で終了コード 2 です。未知の引数では usage を標準エラーに出し、終了コード 2 です。`--file` を指定しない場合は `--file is required` で終了コード 2 です（`src/core/concurrent_main.cpp:60-76`）。
- CUDA runtime 呼び出しが失敗した場合は呼び出し名と CUDA error を標準エラーに出し、終了コード 1 で終了します（`src/core/concurrent_main.cpp:33-37`）。
- 正常な測定では arena サイズ・CPU thread 数・GPU role 数を表示し、CPU のみ、GPU のみ、両方を実行した各モードの所要時間と throughput、干渉率を標準出力に表示します（`src/core/concurrent_main.cpp:93-94,149-188`）。

## 根拠

- `src/core/concurrent_main.cpp:52-76` — parser、既定値、値変換、引数不足・未知引数・必須 `--file` の処理。
- `src/core/concurrent_main.cpp:78-94` — 固定寸法、arena サイズ、ファイル読み込みと失敗経路。
- `src/core/concurrent_main.cpp:112-147` — CPU/GPU の処理における `experts` の使用。
- `src/core/concurrent_main.cpp:149-196` — 実行モード、測定出力、CUDA リソースの解放。
- `include/strata/core/pinned.hpp:45-97`、`src/core/pinned.cu:408-412` — arena の有効判定と 0 byte 時の挙動。
- `CMakeLists.txt:356-358` — `strata-concurrent` の GPU 有効ビルドでの登録。
