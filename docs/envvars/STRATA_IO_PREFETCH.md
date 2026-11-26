# `STRATA_IO_PREFETCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--mmap-experts` で使う `FileExpertSource` の Linux file tier で、uncached expert の読み取りと router が予測した後続 layer の読み取りを I/O worker の `pread` に切り替える。`experts.bin` では uncached blob を worker が page cache に読み込み、既に cache にある blob は mapping から渡す。GGUF を in-place で読む場合は expert の file range を staging buffer に読む。設定だけで通常の resident arena の読み方は変わらない。`generate.cpp` は `--mmap-experts` 側でのみこの設定を評価し、同じ処理は `--serve` のリクエスト経路でも使われる（`engine/src/program/generate.cpp:8621-8647, 8688-8725, 10251-10258`、`engine/src/core/expert_source.cpp:1896-1922, 5215-5221`）。

## 値と判定

`std::getenv` で取得し、未設定または空文字列なら既定値に任せる。それ以外は `std::atoi` の結果が 0 以外なら要求 ON、0 なら要求 OFF。文字列全体の検証や大文字小文字の扱いはなく、`atoi` が先頭の空白・符号・数字列を変換し、その後の文字は無視する。したがって `1`, `-1`, `1junk`, ` 1` は ON、`0`, `0anything`, `true`, `false`, `junk` は OFF。空文字は `atoi` 判定に入らず unset と同じ扱いになる（`engine/src/program/generate.cpp:8693-8701, 10288-10290`）。

| 条件 | unset / 空文字 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux の GGUF in-place file tier | 既定で ON（`linux_file_defaults()` が true） | `atoi(value) != 0` で ON | `atoi(value) == 0` で OFF |
| Linux の `experts.bin` file tier | 起動時の cache room が expert 全体の 55% 以上なら既定で ON。未満なら OFF | `atoi(value) != 0` で ON | `atoi(value) == 0` で OFF |
| 非 Linux | 既定 OFF | ON を要求するが setter は何もしない | OFF |

`experts.bin` の既定判定は `cache_room_ratio() >= 0.55`。cache room は `gate_cache_room()` を expert 総 byte 数で割った比率で、起動時にこの判定を行う。明示値による ON 要求は、この既定判定を上書きするが unbuffered reader では有効にならない。実装は `engine/include/strata/core/expert_source.hpp:1081-1093`、`engine/src/core/expert_source.cpp:2324-2327`、`engine/src/program/generate.cpp:8693-8701` にある。

## 有効になる条件

- `--mmap-experts` または RAM 不足時に file source へ切り替わり、`src` が `FileExpertSource` として開かれていること。resident arena 経路ではこの値を適用しない（`engine/src/program/generate.cpp:8621-8647, 8745-8747`）。
- Linux build であること。非 Linux では `set_io_prefetch` の Linux 部分がコンパイルされず、ON 要求も機能を有効にしない（`engine/src/core/expert_source.cpp:1261-1266, 1310-1312`）。
- file source が unbuffered reader ではないこと。`set_io_prefetch` は `direct_` が空でない場合に return する。`--resident-budget-gib` / `--ssd-experts` により unbuffered read になった場合は有効化されない（`engine/src/core/expert_source.cpp:1264-1267`、`engine/src/program/generate.cpp:8654-8658`）。
- I/O file descriptor を開けること。対象 file の `open` が失敗すると setter は途中で return し、有効化しない（`engine/src/core/expert_source.cpp:1267-1277`）。
- 起動時に全 expert が GPU cache にある場合、既定動作で有効化された prefetch は `STRATA_FILE_TIER_IDLE` が unset または `atoi != 0` なら停止される。明示 ON で有効化した場合はこの既定停止の対象外。後で GPU cache から expert が減ると停止した既定 prefetch を再開する（`engine/src/program/generate.cpp:10258-10285, 10341-10377`）。
- `STRATA_IO_PF_GATE` は有効時の decode prefetch をさらにゲートする。unset / 空文字なら gate は ON、非空値は `atoi != 0` で判定するため `0` は OFF。gate が閉じている間は decode の uncached range を `pread` せず mapping copy に進む。prompt 経路はこの gate の対象外（`engine/src/core/expert_source.cpp:1299-1303, 1904-1920`; gate の説明 `engine/include/strata/core/expert_source.hpp:1066-1079`）。
- `STRATA_IO_PREFETCH` が空でなく非ゼロの場合、`STRATA_LOOKAHEAD` が unset または `atoi != 0` で、router の BF16 条件を満たすと routing-aware prefetch も開始対象になる。`STRATA_LOOKAHEAD=0` はそれを止める。これは I/O prefetch 自体の有効条件とは別である（`engine/src/program/generate.cpp:10288-10339`）。

## 実行時の詳細

値と Linux default 判定は `--mmap-experts` source の open 後、初回 I/O に先立って評価される。ON なら `STRATA_IO_PF_THREADS` を `atoi` で読み、正数を worker 数にする。未設定・0・負値は setter 内の既定 8 thread になる。setter は file handle と staging 領域を準備して worker を起動し、gate を既定 ON にする。gate の境界値などは別変数 `STRATA_IO_PF_GATE_LO` / `_HI` が調整する（`engine/src/program/generate.cpp:8621-8647, 8693-8704`; `engine/src/core/expert_source.cpp:1261-1309`）。

file tier の demand read は page cache 状態を見て uncached ranges を `pread` で読む。読み取りに失敗した range はそのまま mapping から `memcpy` される。`experts.bin` で cache 済みの blob は mapping から渡され、未 cache blob は worker が cache に読み込み、kernel に渡す。router 先読み分は I/O worker が layer 計算中に読む。これらの経路は `engine/src/core/expert_source.cpp:1896-1922, 2450-2460, 2500-2530, 5215-5221` にある。

起動時の `STRATA_IO_PREFETCH` 判定は保存されるが、lookahead の `la_asked` 計算では同じ環境変数をもう一度読み取る。プロセス実行中に環境を変更する運用については、コード上の読み取りタイミングが異なるため、I/O prefetch の起動済み状態に遡って反映されない（`engine/src/program/generate.cpp:8693-8704, 10288-10290`）。自動停止・再開時に読む `STRATA_IO_PF_THREADS` はその時点の環境値を使う（`engine/src/program/generate.cpp:10352-10368`）。

## ログと測定値

- file tier の Linux 既定が有効なら `strata generate: file tier (Linux defaults, ...): ...`、明示設定で有効なら `strata generate: file tier io prefetch ON (STRATA_IO_PREFETCH=1): ...` を stderr に出す（`engine/src/program/generate.cpp:8705-8718`）。
- `experts.bin` で既定 OFF の場合、cache room 比率と「it helps from 55%」を含む理由を stderr に出し、`STRATA_IO_PREFETCH=1 turns it on anyway` と案内する（`engine/src/program/generate.cpp:8696-8699`）。
- ON 要求が使えない場合は `strata generate: STRATA_IO_PREFETCH=1 is not available here (Linux mapped file tier only, not with unbuffered reads); the file tier reads as before` を stderr に出す。ただし Linux 既定が ON と判定されたケースで setter が失敗した場合、この unavailable 分岐には入らず、明示的な失敗ログもない（`engine/src/program/generate.cpp:8701-8724`; setter の失敗経路 `engine/src/core/expert_source.cpp:1264-1277`）。
- `--serve` の request log では `io prefetch: ... read ahead ... used ... unused ... dropped; decode waited ...` 等を stderr に出すのは prefetch が実際に ON の場合だけ（`engine/src/program/generate.cpp:23837-23873`）。
- `docs/DETAILS.md:302-318` には Linux GGUF / `experts.bin` の既定条件、gate と測定の説明がある。本書では測定値を独立に確認した事実としては扱わず、挙動は上記ソースの実装に基づいて記述した。

## 根拠

- 読み取り、既定値、起動ログ: `engine/src/program/generate.cpp:8621-8647, 8688-8745`
- file tier への適用条件: `engine/src/program/generate.cpp:8654-8658`; `engine/src/core/expert_source.cpp:1261-1312`
- page cache 判定と読み取り処理: `engine/include/strata/core/expert_source.hpp:1012-1023, 1081-1097`; `engine/src/core/expert_source.cpp:1886-1940, 2324-2327, 2418-2460, 5215-5238`
- 全 expert が GPU cache にある場合の停止・再開: `engine/src/program/generate.cpp:10251-10377`
- 観測ログ: `engine/src/program/generate.cpp:8705-8737, 23837-23873`
