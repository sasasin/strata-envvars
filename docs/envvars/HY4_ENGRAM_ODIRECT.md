# `HY4_ENGRAM_ODIRECT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の Engram shard を開くとき、POSIX 実装でページキャッシュを迂回する I/O を選ぶ環境変数です。`PageFile::open_impl` が直接読み、`EngramIO::open` から shard を開くときに呼ばれます。`--engram` で shard を指定し、`--no-engram` が無効になっていない経路（HIP/CUDA runner、SYCL runner/server、Metal runner）で Engram shard を開く際に関係します。キャッシュ経由かどうかを決めるもので、Engram の行 ID や読み取るデータを選ぶ分岐ではありません。`--no-engram` または空の shard path で `EngramIO::open` が呼ばれなければ、この変数も評価されません。〔`engine/src/hy4flash/run/hy4_engram.cpp:353-362,446-458`; `engine/src/hy4flash/run/hy4_engram.h:60-62`; `engine/src/hy4flash/run/hy4_graph.hip.h:1658-1676`; `engine/src/hy4flash/sycl/sy_graph.h:585-589`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:681-685,1762`〕

## 値と判定

POSIX 側は `std::getenv` の戻り値を `open_impl` の呼び出しごとに取得し、文字列全体ではなく `od_env[0]` だけを比較します。`direct` 引数が true の場合の判定は次の式です。通常の `EngramIO::open` は `PageFile::open` を使い、`direct=true` で開きます。〔`engine/src/hy4flash/run/hy4_engram.cpp:353-362,446-458`; `engine/src/hy4flash/run/hy4_engram.h:60-62`〕

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| POSIX、`PageFile::open` (`direct=true`)、`O_DIRECT` が利用可能 | cgroup のメモリ制限またはホスト RAM 条件に該当すれば direct。該当しなければ buffered | 先頭文字が `1`（`1`, `10`, `1anything`）なら direct を強制 | 先頭文字が `0`（`0`, `00`, `0anything`）なら自動判定にかかわらず buffered |
| POSIX、上記以外の値 | 自動判定 | 先頭文字が `1` | 先頭文字が `0`。空文字、`true`/`false`、`2`、`-1`、先頭空白付きの ` 1` などは明示指定にならず、自動判定 |
| Windows | この変数を読まない。通常の `PageFile::open` は `FILE_FLAG_NO_BUFFERING` 付きで開く | 該当なし | 該当なし |

大文字小文字・数値変換・文字列全体の妥当性検査はありません。POSIX で空文字は「設定済み」ですが、先頭文字が `\0` なので `0`/`1` のどちらにも一致せず、自動判定になります。`HY4_ENGRAM_ODIRECT=0` は cgroup/RAM の自動選択より優先して direct を止め、`=1` はそれらの条件がなくても direct を要求します。〔`engine/src/hy4flash/run/hy4_engram.cpp:359-362`〕

自動判定の条件は、cgroup メモリ制限が検出された場合、またはホスト RAM が厳しい場合です。macOS では `hw.memsize < 128 GiB`（`sysctlbyname` に失敗した場合も厳しい扱い）、その他の POSIX では `/proc/meminfo` の `MemTotal < 128 GiB` または `MemAvailable < 80 GiB`（各値が正の場合）で厳しいと判定します。比較は厳密な `<` です。cgroup 判定は `strata::platform::cgroup_mem::in_cgroup_memory_limit()` を呼びます。〔`engine/src/hy4flash/run/hy4_engram.cpp:324-351`; `engine/include/strata/platform/cgroup_mem.hpp:168-184`〕

## 有効になる条件

- **OS と build:** 変数を読むのは `_WIN32` 以外の `PageFile::open_impl` です。Windows 分岐には `getenv` がなく、`direct=true` の通常 open は `FILE_FLAG_NO_BUFFERING` を指定します。POSIX でも `O_DIRECT` が未定義ならその flag での open はコンパイルされず、必要に応じて `F_NOCACHE` の分岐だけが使われます。〔`engine/src/hy4flash/run/hy4_engram.cpp:248-257,353-375`〕
- **Backend / runner:** 同じ `hy4_engram.cpp` を使う HIP/CUDA、SYCL、Metal の各グラフが Engram shard を開く場合に共通です。起動モードがサーバーか CLI かでは読み取り式は変わりません。〔`engine/src/hy4flash/run/hy4_graph.hip.h:1658-1676`; `engine/src/hy4flash/sycl/sy_graph.h:585-589`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:681-685`〕
- **モデル / CLI:** Engram metadata のロード後、`engram_path` が空でない場合にだけ `eio.open` を呼びます。HIP/SYCL/Metal の CLI には `--engram` と `--no-engram` があり、`--no-engram` は空 path を渡して Engram I/O 自体を省略します。〔`engine/src/hy4flash/run/hy4_main.hip.cpp:483,493,703`; `engine/src/hy4flash/sycl/sy_main.cpp:153,174,294`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1508,1518,1762`〕
- **別の設定:** HIP/CUDA runner の `HY4_ENGRAM_CACHE_MIB` と `--engram-cache-mib` は LRU 行キャッシュの容量を扱います。ファイルの direct/buffered 判定には使われません。〔`engine/src/hy4flash/run/hy4_graph.hip.h:1660-1676`; `engine/src/hy4flash/run/hy4_main.hip.cpp:467-468`〕
- **明示的な buffered 呼び出し:** `PageFile::open_buffered` は `direct=false` であるため、この環境変数や自動条件にかかわらず direct open をしません。通常の `EngramIO::open` は `PageFile::open` を使います。〔`engine/src/hy4flash/run/hy4_engram.h:60-62`; `engine/src/hy4flash/run/hy4_engram.cpp:353-362,457`〕

## 実行時の詳細

`EngramIO::open` は shard のヘッダーを検査した後、`pf_.open(shard, err)` を呼びます。POSIX の `PageFile::open_impl` はその時点で環境変数を読み、判定が有効なら `O_RDONLY | O_DIRECT` で開こうとします。失敗した場合は `fadv_dontneed_` を立て、`O_RDONLY` で開き直します。`O_DIRECT` がない build では通常 open の後、`F_NOCACHE` が定義され、判定が有効なら `fcntl(fd, F_NOCACHE, 1)` を試しますが、戻り値は無視します。Windows では環境変数を参照せず、`direct` 引数で `FILE_FLAG_NO_BUFFERING` の有無を決めます。〔`engine/src/hy4flash/run/hy4_engram.cpp:248-257,353-382,446-458`〕

値は open のたびに読み直され、関数内 static cache や起動時固定値はありません。いったん開いた `PageFile` の方式はその file descriptor/handle に設定されるため、プロセス実行中に環境変数を変更しても既に開いた shard には反映されません。再 open があればその時点の値を再評価します。ページ読み取りは後続の `read_pages` が POSIX では `pread` を行い、fallback 時には成功したページについて `POSIX_FADV_DONTNEED` を要求します。〔`engine/src/hy4flash/run/hy4_engram.cpp:353-382,389-423,446-458`〕

読み取り方式はページキャッシュ利用に関する I/O 分岐です。`fetch_raw` は同じページを読み、同じ行バイトを出力バッファへコピーします。このソース上、この環境変数による row ID、Engram 値、生成 token の選択変更はありません。〔`engine/src/hy4flash/run/hy4_engram.cpp:389-423,557-673`〕

## ログと測定値

この変数の値や direct 判定を報告する専用ログはありません。POSIX で direct open が失敗すると buffered open へ無言で fallback します。buffered open も失敗した場合は `open failed for <path>` を `err` に設定して `false` を返し、初期化側が `init: <err>` を stderr に出して終了コード 1 を返します。ページ読み取り時は短い読み取りで `short pread at page <n>`、未 open なら `PageFile not open` がエラーになります。runner の非同期準備経路は `eio.fetch_raw` の失敗を `err` に保持して呼び出し側へ返します。〔`engine/src/hy4flash/run/hy4_engram.cpp:366-370,389-408,422,557-558,629-673`; `engine/src/hy4flash/run/hy4_graph.hip.h:1802-1819`; `engine/src/hy4flash/run/hy4_main.hip.cpp:703-705`; `engine/src/hy4flash/sycl/sy_main.cpp:294-296`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1762-1764`〕

`docs/DETAILS.md` にはこの環境変数や Engram shard I/O の説明・測定値が見当たらないため、性能差は記載しません。

## 根拠

- `engine/src/hy4flash/run/hy4_engram.cpp:248-257,324-382,389-423,446-458,557-673`
- `engine/src/hy4flash/run/hy4_engram.h:53-72`
- `engine/include/strata/platform/cgroup_mem.hpp:168-184`
- `engine/src/hy4flash/run/hy4_graph.hip.h:1658-1676,1802-1819`
- `engine/src/hy4flash/sycl/sy_graph.h:585-589,655-671`
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:681-685,755-768`
- `engine/src/hy4flash/run/hy4_main.hip.cpp:483,493,703`; `engine/src/hy4flash/sycl/sy_main.cpp:153,174,294`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1508,1518,1762`
