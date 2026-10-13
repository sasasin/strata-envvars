# `STRATA_FETCH_THREADS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--mmap-experts` 経路の `FileExpertSource` が、ステージバッファへ複数の未キャッシュ expert を読み込むときに使う CPU worker 数を設定します。ファイルから読む対象は pack の `experts.bin`、またはそれがない native pack で参照する GGUF shard です。変数名やヘッダーコメントは GGUF の読み取りを挙げていますが、同じ `fill_many()` は mmap の両形式に使われます。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 既定の 8 を使う |
| 空文字、数値に変換できない文字列、変換結果が 0 以下 | setter を呼ばず、既定の 8 を使う |
| `atoi()` の変換結果が正 | その整数を設定する。例: `12` と `12workers` は 12、`  +3tail` は 3 |

文字列全体の検証はなく、`atoi()` が先頭の整数部分を読むため、後続文字は無視されます。`atoi()` の結果が `int` の範囲を超える入力について、C/C++ の変換結果は保証されません。値を上限で clamp する処理はありません。`set_fetch_threads()` 自体は 1 未満を 1 にしますが、呼び出し側が `atoi(v) > 0` の場合だけ setter を呼ぶため、環境変数から 1 未満は設定できません。

根拠: CUDA/HIP 側 `src/program/generate.cpp:4622-4632`、SYCL 側 `sycl/src/program/generate.cpp:4168-4178`、setter と初期値 `include/strata/core/expert_source.hpp:645-646,803`（SYCL 側 `sycl/include/strata/core/expert_source.hpp:541-542,640`）。

## 有効になる条件

- `strata generate` が `o.mmap_experts` の経路に入る場合にだけ、この変数を読みます。明示的な `--mmap-experts` のほか、低 RAM 関連のオプションがこの状態を設定する箇所があります。通常の resident expert arena 経路では読みません。
- `FileExpertSource::fill_many()` に未処理の読み込みがあり、buffered/mapped 読み取りを行う場合に、設定した数が worker 数の上限になります。実際の worker 数は `min(todo.size(), fetch_threads_)` です。呼び出し元のスレッドも仕事を受け持つため、ここで作る追加スレッド数はその値より最大 1 少なくなります。読み込み対象が少なければ設定値より少ない数になります。
- `direct_` を使う unbuffered 読み取りでは別のバッチ読み取り経路になり、最大 4 worker（16 blob ずつ割当）を固定で使うため、この設定値はその経路の並列数を変えません。
- Linux の `STRATA_IO_PREFETCH` が利用可能で有効な場合、layer prefetch は I/O worker queue に渡され、worker 数は `STRATA_IO_PF_THREADS` が担当します。この prefetch の並列数は `STRATA_FETCH_THREADS` では制御されません。`STRATA_IO_PREFETCH` の条件を満たさず通常の `fill_many()` に進む読み込みでは、この変数の設定が適用されます。

## 実行時の詳細

環境変数は `FileExpertSource` を開く前の mmap 初期化時に読み、一度だけ `fetch_threads_` に設定します。後からプロセス環境を書き換えても再読込しません。`prefetch()` は対象 expert の読み込みが必要な分だけステージ枠を確保し、`fill_many()` は atomic な仕事番号を使って worker に割り当て、各 expert の読み込み完了後に待ち合わせます。CUDA/HIP と SYCL の実装で、この buffered/mapped 経路の worker 数の決め方は同じです。

Windows では buffered/mapped 読み取りの worker 処理に先立ち、利用可能なら `PrefetchVirtualMemory` に対象範囲をまとめて渡します。これは `STRATA_FETCH_PVM` による別制御で、`STRATA_FETCH_THREADS` はこの API の呼び出し有無や値を変えません。`STRATA_FETCH_THREADS` 固有のログ出力はありません。

## 文書との照合

`docs/DETAILS.md` は、GGUF shard からの expert 読み込みについて既定 8 thread と Windows のまとめた page request を説明しています。これはコード上の既定値および Windows の prefetch 処理と一致します。同資料では `experts.bin` の場合はこの設定に触れていませんが、コードでは同じ `fill_many()` が mapped `experts.bin` にも適用されます。`docs/UNSLOTH_Q4.md` には 16 thread でも速くならなかったという記載がありますが、測定環境・手順・結果表はその記述箇所にはないため、一般的な性能効果としては扱いません。

## 根拠

- mmap 初期化、環境変数の変換、ファイル形式の選択: `src/program/generate.cpp:4622-4637`、SYCL 側 `sycl/src/program/generate.cpp:4168-4183`。
- 既定値 8 と設定 setter: `include/strata/core/expert_source.hpp:645-646,803`、SYCL 側 `sycl/include/strata/core/expert_source.hpp:541-542,640`。
- buffered/mapped worker 上限と呼び出しスレッドを含む仕事分担: `src/core/expert_source.cpp:1519-1580`、SYCL 側 `sycl/src/core/expert_source.cpp:968-1030`。
- unbuffered 経路の固定 worker 数: `src/core/expert_source.cpp:1519-1544`、SYCL 側 `sycl/src/core/expert_source.cpp:968-993`。
- Linux I/O prefetch の別経路と別スレッド設定: `src/program/generate.cpp:4667-4678`、`src/core/expert_source.cpp:1426-1440`。
- 資料: `docs/DETAILS.md:215-223`、`docs/UNSLOTH_Q4.md:235`。
