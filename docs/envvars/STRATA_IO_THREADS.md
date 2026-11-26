# `STRATA_IO_THREADS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

PLE（n-gram table）の `--ple-io direct` 経路で、`DirectFile` がファイル読み込みを発行するスレッドプールのスレッド数を指定する。Windows では overlapped read の発行スレッド数、POSIX では blocking `pread` を行うスレッド数になる。CUDA/HIP 共通実装と SYCL 実装の双方に読み取りがある（`engine/src/platform/direct_file.cpp:61-67,193-197,319-333`; `engine/sycl/src/platform/direct_file.cpp:61-67,193-197,317-329`）。

この値は `--ple-inflight` の上限値や PLE の行キャッシュ容量を設定しない。直接読み込みを選ばない場合、たとえば `--ple-io mmap` / `ram` の場合には `DirectFile` が開かれず、この変数は使われない（`engine/src/program/generate.cpp:6269-6276`; `engine/src/kernels/ngram.cpp:449-464`）。

## 値と判定

`std::getenv` で値の有無を見て、設定されていれば `std::atoi` で整数化し、最後に `std::clamp(n, 1, 64)` を適用する。構文検査やエラー報告はない。未設定は呼び出し側の既定値、空文字や数字で始まらない文字列は `atoi` が 0 を返すため 1 スレッドになる。先頭の空白と符号は `atoi` の規則で扱われ、整数部分の後ろに文字があっても読み飛ばされる（例: `" 8x"` は 8、`"3.5"` は 3）。負数と 0 は 1、65 以上は 64 に clamp される。`atoi` が `int` に表せない値を受けた場合の結果はこのコードでは検査されず、値域外入力について安全な規則は定められていない（`engine/src/platform/direct_file.cpp:63-66`; `engine/sycl/src/platform/direct_file.cpp:63-66`）。

| ビルド / OS | unset | 設定時に有効になる値 | 設定時に無効になる値・例 |
|---|---:|---|---|
| CUDA/HIP 系、Windows | 4 | `1`〜`64`（範囲外は 1〜64 に clamp） | 空文字、`abc`、`0`、`-2` は 1。`65` は 64 |
| CUDA/HIP 系、POSIX（Linux / macOS 等） | 16 | 同上 | 同上 |
| SYCL、Windows | 4 | 同上 | 同上 |
| SYCL、POSIX | 64 | 同上 | 同上 |

大文字小文字の比較はなく、文字列全体の妥当性も検査しない。`true` / `false` は数値として解釈されず、どちらも 1 になる。

## 有効になる条件

- PLE テーブルを持つモデルを使い、PLE の I/O が direct であること。CUDA/HIP 側では起動時に `--ple-io` を `mmap` または `ram` にすると mmap 経路となる。SYCL 側も同様に direct 以外では `DirectFile` を開かない（`engine/src/program/generate.cpp:6269-6276`; `engine/sycl/src/program/generate.cpp:3350-3357`; `engine/src/kernels/ngram.cpp:449-464`）。
- `STRATA_PLE_AUTO_RAM` による自動 RAM 選択（CUDA/HIP 側）や、低速読み込み時の `STRATA_PLE_AUTO_MMAP` による mmap 切り替え後は direct reader が閉じられるため、切り替え後の PLE 読み込みにはこのスレッド数は適用されない。明示した `--ple-io` は自動選択より優先される。低速 probe と切り替え条件は `engine/src/program/generate.cpp:6303-6315,6350-6375`、SYCL 側は `engine/sycl/src/program/generate.cpp:3373-3398`。
- `--ple-inflight` は同時に保持する PLE read の上限を別途指定する。この値は `DirectFile` のスレッド数を変更しないが、発行可能な read 数の制約になり得る（`engine/src/program/generate.cpp:6274-6276`; `engine/include/strata/kernels/ngram.hpp:167-172`）。
- `--ple-sync-submit` は PLE reader 側の submit/reap worker の使用を切り替えるが、`DirectFile::open` の発行スレッド数の読み取り・生成を分岐させない（`engine/src/program/generate.cpp:6274-6276`; `engine/src/ngram/ple_reader.cpp:347-389`）。

## 実行時の詳細

`DirectFile::open` ごとに `io_threads(default)` が呼ばれ、その時点の環境を読み、得られた数だけ worker thread を生成する。関数内 static や process-wide cache はない。開いている reader のスレッド数はその pool の生成後に変わらないが、環境を変えてから別の `DirectFile::open` が行われれば新しい pool には新しい値が評価される（`engine/src/platform/direct_file.cpp:63-66,193-197,200-210,319-333`; `engine/sycl/src/platform/direct_file.cpp:63-66,193-197,200-209,317-329`）。

PLE direct 経路では、GGUF の PLE table の位置を検証した後に `PleReader::open` が `DirectFile::open` を呼び、発行 pool を作る。Windows worker は queued request を `ReadFile` の overlapped submit に渡す。POSIX worker はキューから一件ずつ取り出して blocking `pread` を呼ぶ。したがって同じスレッド数でも OS によって役割が異なる（`engine/src/kernels/ngram.cpp:431-464`; `engine/src/platform/direct_file.cpp:106-139,193-197,289-300,319-333`; `engine/sycl/src/platform/direct_file.cpp:106-139,193-197,289-300,317-329`）。

## ログと測定値

`STRATA_IO_THREADS` の値、clamp、採用スレッド数を出す専用ログはない。PLE table の起動失敗は `strata generate: <error>` として stderr に出される（`engine/src/program/generate.cpp:6288-6290`）。direct read の実行時エラーは reader 内で `PleReader: a table read failed`、短い読み込みは `PleReader: short read inside the table` となり、`collect` のエラー文字列として呼び出し元へ返る（`engine/src/ngram/ple_reader.cpp:229-249,564-590`）。

SYCL 実装のコメントには、B70 環境の 2,184-token prompt に含まれる約 27,000 件のランダム 4 KiB `O_DIRECT` read について、16 threads で 466 ms、64 threads で 332 ms だったという記録がある。これはソースコメントに記録された条件付きの値であり、一般的な性能差を保証するものではない（`engine/sycl/src/platform/direct_file.cpp:324-327`）。

関連資料 `docs/AMD_HIP_PERFORMANCE.md:50` は POSIX PLE direct read が設定可能な worker pool を使うと説明し、同文書の再現用環境（Strata 0.2.15 以前の build）に `STRATA_IO_THREADS=32` を記載している（同:14-23）。現行ソースでも pool のサイズ設定が確認できる。`docs/DETAILS.md:1215` は direct / mmap / ram の選択を説明している。

## 根拠

- `engine/src/platform/direct_file.cpp:61-67,193-197,319-333` — 値の読み取り・clamp、CUDA/HIP 系の既定値と pool 生成。
- `engine/sycl/src/platform/direct_file.cpp:61-67,193-197,317-329` — SYCL の同じ値判定、Windows / POSIX 既定値と pool 生成。
- `engine/src/kernels/ngram.cpp:449-464` — PLE direct モードから `PleReader` を開く呼び出し。
- `engine/src/ngram/ple_reader.cpp:347-389,564-590` — DirectFile の利用開始と read error の返却。
- `engine/src/program/generate.cpp:6269-6276,6303-6315,6350-6375` — CLI / 環境による direct 経路の選択、自動切替条件。
- `engine/sycl/src/program/generate.cpp:3350-3357,3373-3398` — SYCL の経路選択と probe 後の切替。
