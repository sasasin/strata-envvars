# `STRATA_IO_THREADS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

n-gram（PLE）テーブルの非バッファ読み込み用 `DirectFile` の、読み出し（issue）スレッドプールのサイズを決めます。`DirectFile::submit()` は要求をキューに入れるだけで、実際の read はプール内のスレッドが行います。この変数はそのプールの thread 数だけを変え、読み込む内容・順序・返されるバイト列には影響しません。

- Windows: `FILE_FLAG_NO_BUFFERING | FILE_FLAG_OVERLAPPED` の `ReadFile` を I/O completion port へ投げるスレッド数（overlapped submit の並行数）。
- Linux（POSIX 実装）: 各スレッドが blocking `pread`（`O_DIRECT`）を一つずつ実行するため、スレッド数そのままが read queue の depth になる。
- SYCL port の Linux 既定値は 64（上流の 16 より深い）。

読み取り箇所は `DirectFile::open()` 内のみで、`PleReader::open()` → `DirectFile::open()` の経路で呼ばれます。`static` cache はなく、open のたびに環境を再読み込みします。

## 値と判定

実装は `std::getenv("STRATA_IO_THREADS")` の結果を `std::atoi` で整数化し、`std::clamp(n, 1, 64)` します。文字列全体の文法検査、大文字小文字、空白、接尾文字の検査はありません。

| 状態 | 判定結果 |
|---|---|
| unset | platform/build 既定値（下表）を `clamp(1, 64)` |
| 空文字 | `getenv` は nullptr ではない → `atoi("")` = 0 → clamp により **1** |
| 非数値文字列（`abc`, `off`, `true` など） | `atoi` = 0 → **1** |
| 0・負値 | clamp 下限 → **1** |
| 正の数値 1..64 | その値 |
| 65 以上 | clamp 上限 → **64** |
| 先頭が数字でその後ろに文字（`32x`, `16abc`） | `atoi` が先頭の数値だけを読むため、その数値（64 超は clamp） |

既定値（unset 時）:

| ビルド | 既定 |
|---|---|
| Windows（CUDA/HIP/SYCL port 両実装） | 4 |
| Linux POSIX（CUDA/HIP 本体実装） | 16 |
| Linux POSIX（SYCL port） | 64 |

根拠: `src/platform/direct_file.cpp:61-67`、`sycl/src/platform/direct_file.cpp:61-67`、呼び出し側 `src/platform/direct_file.cpp:187`（Windows 4）・`:314`（Linux 16）、`sycl/src/platform/direct_file.cpp:187`（Windows 4）・`:317`（Linux 64）。テストの注釈も「範囲外値は 1..64 に clamp」と同じことを示している（`tests/platform/direct_file_async.cpp:25`、テスト専用）。

## 有効になる条件

- `--ple-gguf` が指定され、PLE テーブルが `PleIo::Direct` モードで開かれるときだけ効く。`--ple-io mmap` / `--ple-io ram` では `DirectFile` を開かないため、この変数は読まれない（`src/kernels/ngram.cpp:314-329`）。
- `--ple-io` の既定は `direct`（`src/program/generate.cpp:387`）。ただし起動時に短い cold probe で read 速度を測り、15,000 rows/s 未満なら mmap へ自動 fallback する。この場合 `ple_table.close()` 後に `PleIo::Mmap` で再 open するので、fallback 後はプールが存在しない。`--ple-io direct` を明示した場合は fallback せず警告だけ（`src/program/generate.cpp:3174-3198`）。
- `--ple-sync-submit`（`io_thread = false`）でも `DirectFile` のプールは作られる。このフラグは PleReader 側の submit/reap ワーカーの有無を変えるだけで、`DirectFile::submit()` は常にキューに入れるだけなので issue スレッドは常にプール側である（`src/ngram/ple_reader.cpp:95-98,364-370`、`src/platform/direct_file.cpp:206-217,331-340`）。
- Linux 本体実装では、プールスレッドは起動時に `strata::aux_cpus::pin_current_thread()` を呼ぶ。`STRATA_AUX_CPUS` が OFF のときこれは no-op。SYCL port のプールスレッドは pin しない（`src/platform/direct_file.cpp:188,315`、`sycl/src/platform/direct_file.cpp:188,318`）。
- 実際の同時 in-flight read 数は、Linux ではこのスレッド数で上限が決まる（各スレッドが blocking pread を 1 本）。`--ple-inflight`（既定 256、1..1024）は submit できる要求数の上限で、スレッド数とは別。Windows は overlapped なので in-flight 数はスレッド数で縛られない（`src/platform/direct_file.cpp:105-125,277-290`、`src/program/generate.cpp:390,3154`）。

## 実行時の詳細

- 読み取り時期は `DirectFile::open()` の時点。ファイルと completion port（または fd）を開いた直後に `io_threads(dflt)` を呼び、その数だけ `std::thread` を生成する。生成に失敗してもエラーログはない。
- `close()` / 再 `open()` でプールは破棄・再生成される。`PleTable::open()` は engine 起動時に一度呼ばれる（`src/program/generate.cpp:3145,3168`）。同じプロセス内で open 後に環境を変えても、次の open まで反映されない。
- スレッド数そのものを出力するログは Strata 側にない。`PleTable::io_report()`（`STRATA_IO_STATS` 関連）は rows、cache hit、SSD reads、read p50/p99、blocked/submit 時間を出すだけで、プールサイズは表示しない（`src/kernels/ngram.cpp:554-569`）。効果は read 遅延・prompt 時間として間接的に観測できる。
- Windows の completion port は `CreateIoCompletionPort(..., 1)` で作られ、`wait()` が唯一の completion 経路である。プールスレッドは issue だけし、reap しない（`src/platform/direct_file.cpp:179-188`）。

## 資料の測定値

`docs/INTEL.md:290` は、SYCL port の Linux 既定を 16 → 64 にした変更について、2,184-token prompt の PLE row 読みが 466 ms → 330 ms になったと記載する（128・256 は変化なし、ドライブは約 85k IOPS で頭打ち）。同じ数値は port 内のコメントにも「B70 box, 2026-09-30」として残っている（`sycl/src/platform/direct_file.cpp:314-316`）。これは記載された測定環境での値で、他機種の性能を保証しない。

`docs/AMD_HIP_PERFORMANCE.md:21` は HIP の測定 arm の実行環境として `export STRATA_IO_THREADS=32` を挙げている。この値単独の性能差は資料に示されていない。

## 根拠

- `src/platform/direct_file.cpp:61-67` — `getenv` + `atoi` + `clamp(1, 64)` の判定。
- `src/platform/direct_file.cpp:187-188`（Windows 既定 4）、`:314-315`（Linux 既定 16）、`:262-290`（Linux はスレッド数＝queue depth、blocking pread）。
- `sycl/src/platform/direct_file.cpp:63-67`、`:187-188`、`:314-318`（Linux 既定 64、pin なし）。
- `include/strata/platform/direct_file.hpp:1-10` — 概要コメント（既定 4/16。SYCL port の 64 はこのコメントと食い違い、port 側のソースが現行挙動）。
- `src/ngram/ple_reader.cpp:336-341`、`src/kernels/ngram.cpp:314-329` — open 経路と Direct モード限定。
- `src/program/generate.cpp:387,390,3151-3156,3174-3198` — `--ple-io` 既定、probe による mmap fallback。
- `CMakeLists.txt:379-380`、`sycl/CMakeLists.txt:88-107,214` — 本体ビルドは `src/platform/direct_file.cpp`、SYCL ビルドは `sycl/` 内の同名ファイルを優先して使う。
