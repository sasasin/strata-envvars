# `STRATA_PROMPT_DIRECT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux で、ファイル経由の expert 読み出し全体が buffered のときに限り、prompt prefill の複数 expert 読み出しを別の `O_DIRECT` file descriptor 経由に切り替える。decode 側が使う `direct_` は変更せず、既存の file cache 経由のままにする。`FileExpertSource::copy_blobs` が prompt の複数 blob をまとめて読み、RAM copy にある expert は従来どおり RAM からコピーする。対象データの選択・値はこの変数で変えない。分岐は `strata generate` の GPU engine 初期化中にあり、prefill 実装からこの source の `copy_blobs` が呼ばれる（`engine/src/program/generate.cpp:12219-12255`、`engine/src/prefill/prefill.cpp:1233-1247`、`engine/src/core/expert_source.cpp:3885-3914`）。

## 値と判定

コードは `std::getenv` の結果が null でないことに加え、`v[0] == '1'` だけを見る。文字列全体の parse や真偽値変換はせず、大文字小文字・空白の除去・数値妥当性検査もない。先頭バイトが ASCII `1` なら有効で、後続文字は無視する（`engine/src/program/generate.cpp:12248`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux、下記の file-source 条件を満たす | buffered のまま。prompt 用 direct file は開かない | `1`, `10`, `1true` | 空文字、`0`, `01`, `true`, `TRUE`, ` 1` |
| Windows、同じ分岐まで到達 | buffered のまま | 先頭が `1` の値で open を試すが、機能は有効にならない | 上記と同じ判定 |
| macOS など Linux / Windows 以外 | この環境変数を読む分岐自体がコンパイルされない | 該当なし | 該当なし |

空文字は設定済みでも無効。値が無効な場合の警告やエラーはなく、既定の buffered prompt 読み出しを使う。CLI にこの設定を上書きする引数はない。

## 有効になる条件

- `strata` の GPU engine の経路であること。共通 GPU engine の CMake 定義は CUDA または HIP build の場合に有効になり、SYCL は独立した engine project である（`engine/cmake/strata_gpu_engine.cmake:8`、`engine/CMakeLists.txt:20-31`）。
- Linux であること。Windows では環境変数の分岐は通るものの、`open_prompt_direct` は `Linux only` を理由に失敗し、prompt 読み出しは buffered のまま。その他の OS では環境変数の分岐がない（`engine/src/program/generate.cpp:12223-12255`、`engine/src/core/expert_source.cpp:2820-2839`）。
- `o.mmap_experts` が真で `o.resident_budget > 0`、かつ起動時 buffered/unbuffered の再判定で `ub == false` であること。したがって通常は `--resident-budget-gib` または `--ram-experts-gb` に正の値を指定した file source が対象。RAM 不足で arena から file source に切り替わり、resident budget が自動設定される経路も対象になり得る（`engine/src/program/generate.cpp:4220-4256, 8876-8911, 12224-12228`）。
- `--ssd-experts` または budget 0 の経路は `resident_budget` が 0 なので対象外。file-tier がすでに unbuffered（`ub == true`）なら prompt 専用 descriptor を開かず、file-tier の設定がそのまま使われる（`engine/src/program/generate.cpp:4236-4251, 12224-12250`）。
- `STRATA_UNBUFFERED_LOAD` は間接的なゲート。Linux では空でない値の先頭が `0` なら file-tier を buffered にし、それ以外なら unbuffered にする。前者では本変数が別途有効なら prompt direct を試せるが、後者では `!ub` が偽となり本変数の分岐に入らない（`engine/src/core/expert_source.cpp:963-972, 2842-2858, 2867-2872`）。

## 実行時の詳細

読み取りは resident RAM copy を構築した後、`recheck_unbuffered` で file-tier の方式を確定した直後、prompt の処理が始まる前に行う。関数内 static cache はなく、この初期化分岐に到達するたび `getenv` を評価する。descriptor を開いた後の環境変更で実行中の方式は切り替わらない。次のプロセス起動では再評価される（`engine/src/program/generate.cpp:12108-12117, 12219-12255`）。

Linux では `open_prompt_direct` が `paths_` の全ファイルを `O_RDONLY | O_DIRECT | O_CLOEXEC` で開き、成功すると `pdirect_` に保持する。1 ファイルでも open に失敗した場合は、先に開いた descriptor を閉じて `pdirect_` を空にし、失敗理由を返す。Windows はこの段階で失敗する（`engine/src/core/expert_source.cpp:2820-2839`）。

`copy_blobs` は `direct_`（file-tier 全体の unbuffered descriptor）が空で `pdirect_` がある場合、複数の file-tier expert を `read_direct` に渡す。resident copy や override にある blob はそこからコピーする。prompt 用 direct read が失敗したときは各 blob を `copy_from_files` で再試行し、それも失敗した場合は `copy_blobs` が false を返す。prefill worker はその場合 `prefill: the expert source could not copy experts %d.. of layer %d` を stderr に出し `std::abort()` する（`engine/src/core/expert_source.cpp:3889-3914`、`engine/src/prefill/prefill.cpp:1244-1247`）。

## ログと測定値

初期化時に stderr へ `strata generate: the prompt path's expert reads go unbuffered (STRATA_PROMPT_DIRECT=1)` または `strata generate: the prompt path's expert reads stay buffered: <理由>` を出す。Linux で descriptor の open が失敗した場合、理由には失敗した path と `strerror(errno)` が入る。Windows で試行した場合の理由は `Linux only (NTFS serves unbuffered reads of a mapped file one at a time)`。読み出し時の `read_direct` 失敗は buffered fallback に進み、その失敗自体を記録する専用ログはこの経路にない（`engine/src/program/generate.cpp:12248-12252`、`engine/src/core/expert_source.cpp:2820-2838, 3906-3910`）。

`docs/QUANTS.md:132-140` は RTX A4000 16 GB / Xeon E5-2643 v3 / 62 GB、UD-Q4_K_XL、39 GiB RAM budget の測定として、Linux で prompt 4K が 152→315 tokens/s、20K が 217→500 tokens/s、decode が +2〜15%（5 組の interleaved runs、各 run 前に page cache を drop）と記す。同資料は別 PC では結果が混在したことも記載する。これらは資料記載の測定値であり、他の環境への性能保証ではない。

## 根拠

- `engine/src/program/generate.cpp:12219-12255` — 再判定後の環境変数読み取り、分岐、stderr ログ。
- `engine/src/core/expert_source.cpp:2820-2839` — Linux 専用 descriptor の open と失敗処理。
- `engine/src/core/expert_source.cpp:3885-3914` — prompt の複数 blob 読み出し、resident copy、buffered fallback。
- `engine/src/prefill/prefill.cpp:1233-1247` — prefill から `copy_blobs` を呼ぶ箇所とコピー失敗時の abort。
- `engine/src/core/expert_source.cpp:963-972, 2867-2872` — `STRATA_UNBUFFERED_LOAD` と file-tier 再判定。
- `engine/CMakeLists.txt:20-31`、`engine/cmake/strata_gpu_engine.cmake:8` — GPU engine と SYCL engine の build 分離。
- `docs/QUANTS.md:132-140` — 条件付き測定値。
