# `HY4S_WARM_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4S_WARM_GB` は、旧 `hy4s::CpuExperts` 実装が Section 4（expert bodies）のファイルページを予熱するときのメモリ予算を、10進 GB 単位で指定する。予算は実際にロードする範囲だけでなく、モデルを開いた時点の `streaming_` / `bypass_` 判定にも使われる。実装は `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp` の `ram_budget_bytes()`、`CpuExperts::open()`、`CpuExperts::warm()` にある（同ファイル:332-345, 480-506）。

この実装は旧 SYCL CPU expert 経路で、`hy4s_cpuexp_test` と `sy_gpuexp_test` から呼ばれる。`sy_gpuexp_test` のソースには旧実装の手動ビルド手順があり（`engine/src/hy4flash/sycl/sy_gpuexp_test.cpp:1-3`）、SYCL の CMake が `strata` に登録する main は `src/program/generate.cpp` のみである（`engine/sycl/CMakeLists.txt:375-377`）。通常の SYCL `strata` とサーバーは unified `hy4::CpuExperts` を使い、その RAM 予算は `HY4S_RAM_BUDGET_GB` または自動計算で決まる（`engine/src/hy4flash/sycl/sy_graph.h:155-171, 123-126`; `engine/src/hy4flash/sycl/sy_main.cpp:280-305`; `engine/src/hy4flash/sycl/sy_serve.h:259-285`）。したがって、この変数を設定しても通常の `strata` 実行やサーバーの RAM 予算は変わらない。

## 値と判定

`std::getenv` で設定有無を調べ、設定されていれば `atof(e) * 1e9` を byte 予算として使う。単位は 1 GB = 1,000,000,000 bytes。文字列全体の検証や無効値エラー処理はなく、`atof` が先頭から数値として読める部分を変換する。先頭空白と符号は変換対象になり、末尾の非数値文字は無視される。数値が始まらない文字列と空文字は 0 になる（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:491-493`）。

| 条件 | unset | 設定時に予算へ変換される値 | 結果の例 |
|---|---|---|---|
| 旧 SYCL CPU expert 実装の `open()` / `warm()` | `/proc/meminfo` の `MemAvailable` が読めて正なら、その値から 9 GB を引く。読めない、または 0 なら初期値の `1e30` bytes のまま | `atof(value) * 1e9`。`0`、負数、変換不能な文字列、空文字は予算 0 以下。正数はその GB 数。無限大は全 Section 4 を上限とする | `4.5` → 4.5 GB、`4GB` → 4 GB、`0anything` / `true` / 空文字 → 0 GB、`-1` → -1 GB |

値の小数部分は許容される。`atof` のため、たとえば `1.5junk` は 1.5 として変換され、`TRUE` も `true` も数値として始まらないので 0 になる。`nan` は数値変換されるが、`open()` の `std::min(1.0, budget / sec4_bytes_)` は比率 1 を返す一方、`warm()` の `std::max(0.0, budget / sec4_bytes_)` は比率 0 を返す。値の上限検査・エラー表示はない。`open()` では予算を Section 4 の byte 数で割って 1 に上限を切り、比率が 1 未満なら `streaming_`、0.85 未満なら `bypass_` にする。`warm()` ではファイル全体以上の予算を比率 1 とし、0 未満は 0 に clamp する（同ファイル:341-345, 504-506）。

## 有効になる条件

- 値を使うのは `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp` の旧 `hy4s::CpuExperts` に限られる。通常の SYCL `strata` / サーバーは unified 実装を通り、別の `HY4S_RAM_BUDGET_GB` を読む（`engine/src/hy4flash/sycl/sy_graph.h:155-171`）。
- `warm()` が呼ばれ、かつ `open_synthetic()` で作ったデータではないことが必要。synthetic pool では `warm()` は直ちに 0 を返し、予算を読まない（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:396-465, 496-498`）。
- 診断プログラム `hy4s_cpuexp_test real <model> [nthreads] [warm] [quick]` では `warm` 引数がある場合に最初の予熱を行う。`quick` を付けない実行では、後段の cold-read 比較後にも `warm()` が呼ばれる。`sy_gpuexp_test` は `open()` 後に `warm()` を呼ぶ（`engine/src/hy4flash/sycl/hy4s_cpuexp_test.cpp:321-343, 444-456, 461-485`; `engine/src/hy4flash/sycl/sy_gpuexp_test.cpp:61-76`）。
- `open()` 時の `streaming_` 判定は Section 4 が予算に収まらないと true になる。`bypass_` は残り予算比率が 0.85 未満なら true になるが、同じ `open()` 内で `HY4S_DIRECT` が設定されていれば、その先頭文字が `'1'` のときだけ true に上書きし、それ以外は false にする（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:341-345`）。`bypass_` が true の場合、ページキャッシュにない expert body の適格な読み取りは `O_DIRECT` descriptor を使う（同ファイル:568-620）。
- `warm()` は予算比率に従ってファイル中の 8 MiB chunk を均等に選び、選択分を `pread` してからページを populate する。0 予算なら選択 chunk はなく、予熱によるファイル読み込みは行われない。1 以上ならファイル全体を対象とする（同ファイル:500-506, 508-544）。

## 実行時の詳細

`ram_budget_bytes()` は static cache せず、`CpuExperts::open()` で `streaming_` / `bypass_` を決めるときと、各 `warm()` 呼び出しのたびに環境を読み直す（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:332-345, 480-505`）。したがって、プロセス内で環境を変更できる実行経路なら、`open()` 後の変更も次の `warm()` の予熱量に反映される一方、`open()` 時に決まった `streaming_` と `bypass_` はそのまま残る。通常のコマンドラインには GB 予算引数がなく、診断 CLI の `[warm]` は最初の `warm()` を呼ぶかどうかだけを決める（`engine/src/hy4flash/sycl/hy4s_cpuexp_test.cpp:461-485`）。

未設定時の既定予算は `/proc/meminfo` の `MemAvailable` から 9 GB を引く。ファイルを開けない、または `MemAvailable` が 0 の場合は `budget` の初期値 `1e30` bytes が残るため、`open()` の判定と `warm()` は実質的にファイル全体を収まるものとして扱う。`MemAvailable` が正でも 9 GB 未満なら負の予算となり、`open()` は `streaming_` / `bypass_` を有効にし、`warm()` の予熱比率は 0 に clamp される（同ファイル:481-493, 504-506）。この実装は `/proc/meminfo`、`mmap`、`pread`、`O_DIRECT` を使う POSIX/Linux 向けの旧テスト実装であり、Windows 向けの挙動はこのソースから確認できない。

## ログと測定値

旧実装の `warm()` は stderr に `[cpuexp] warm: read %.2f GB of %.2f GB (%.0f%%) in %.1f s (%.2f GB/s), map %.1f s` を出し、`MADV_POPULATE_READ` の失敗時は末尾に ` (touch fallback)` を付ける。設定値の変換失敗について専用の警告・エラーはない。synthetic pool の早期 return でも warm ログは出ない（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:496-552`）。

予熱中の `posix_memalign` が失敗した chunk は読み飛ばされ、`pread` が 0 以下を返した場合もその chunk の読み込みを打ち切るが、これらを理由に `warm()` が失敗を返したり終了したりはしない。部分比率での `madvise` の戻り値も確認されない。全体予熱時の `madvise` 失敗だけはページを touch する fallback に進み、ログ末尾に ` (touch fallback)` を付ける（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:507-552`）。Strata の `docs/DETAILS.md` と `docs/INTEL.md` を確認したが、`HY4S_WARM_GB` の説明やこの旧実装の予熱測定値は見つからなかった。ここではソース中の計測を新たな性能評価として解釈していない。

## 根拠

- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:480-506` — 予算取得、`HY4S_WARM_GB` の変換、streaming 比率と chunk 選択。
- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:332-345, 496-552` — open 時の判定、warm の早期 return と予熱・ログ。
- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:563-620` — page cache miss 時の buffered / direct read。
- `engine/src/hy4flash/sycl/hy4s_cpuexp_test.cpp:321-343, 444-485`、`engine/src/hy4flash/sycl/sy_gpuexp_test.cpp:1-3, 61-76` — 診断プログラムからの呼び出し。
- `engine/sycl/CMakeLists.txt:375-377`、`engine/src/hy4flash/sycl/sy_graph.h:155-171`、`engine/src/hy4flash/sycl/sy_serve.h:259-285` — 通常の SYCL CLI / サーバーの unified expert 経路と RAM 予算。
