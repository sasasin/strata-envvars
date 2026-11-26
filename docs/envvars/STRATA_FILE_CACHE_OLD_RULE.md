# `STRATA_FILE_CACHE_OLD_RULE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux で RAM 予算付きの file tier を使うとき、ファイルキャッシュが再利用される expert 読み出し分を保持できるか判定する旧ルール／現行ルールを選ぶ。旧ルールは RAM の余裕で全読み出し分を確保できる場合だけキャッシュを選ぶ。現行ルールは読み出し分の 5%（最低 0.5 GiB、ただし全読み出し分を上限）を確保できればキャッシュを候補にし、条件によって起動時の drive probe で unbuffered I/O に切り替える。変更するのは expert file tier の読み出し経路であり、読み取る expert の内容ではない。実装は `file_tier_unbuffered` である（`engine/src/core/expert_source.cpp:959-963, 995-1038`）。

この変数を読むのは `__linux__` 分岐だけで、Windows では `experts_unbuffered` に進み、その他の platform では file cache を使う。Linux なら CPU / CUDA / HIP などのビルドで読み取られ、`STRATA_HIP_GFX906` ビルドだけ未設定時の初期値が旧ルールになる（`engine/src/core/expert_source.cpp:965-968, 995-1002, 1034-1038`）。

## 値と判定

Linux の `file_tier_unbuffered` 呼び出しごとに `std::getenv` で値を読み、null または空文字ならコンパイル時の既定値を保つ。空でない値は先頭文字だけを比較し、先頭が `0` なら現行ルール、その他なら旧ルールにする。文字列全体の parse、数値検査、大文字小文字変換、空白除去はない（`engine/src/core/expert_source.cpp:995-1002`）。

| 条件（build など） | unset / 空文字 | 旧ルールになる値の例 | 現行ルールになる値の例 |
|---|---|---|---|
| Linux、`STRATA_HIP_GFX906` 定義あり | 旧ルール | `1`, `true`, `false`, ` 0`, `00` | `0`, `0anything` |
| Linux、その他の build | 現行ルール | `1`, `true`, `false`, ` 0`, `00` | `0`, `0anything` |
| Windows / その他 platform | この変数は読まれず、値の影響なし | 該当なし | 該当なし |

従って `false` も先頭が `f` なので旧ルール、`0anything` は先頭が `0` なので現行ルールになる。Linux では明示的な空文字は unset と同じ扱いである。旧ルールは `file_cache_keeps(avail, arena_bytes, read_bytes)` を使い、既定の 4 GiB の余裕を引いた room が `read_bytes` 全量以上かを判定する。現行ルールは 1 GiB の余裕、5% の hot fraction、0.5 GiB の floor を指定する。必要量は 5% と 0.5 GiB の大きい方を取り、`read_bytes` を上限に clamp する（`engine/src/core/expert_source.cpp:1000-1002`; `engine/include/strata/platform/memory.hpp:54-60`）。

## 有効になる条件

- Linux で `--mmap-experts` 経路を使い、`--resident-budget-gib` に正の RAM 予算を指定する。呼び出し元は `resident_budget > 0` または `--ssd-experts` のときだけ `set_unbuffered` を呼ぶ（`engine/src/program/generate.cpp:8645-8658`）。
- `--ssd-experts` は `set_unbuffered(..., force=true)` となり、強制的に unbuffered を開く経路なので、この変数による判定は通らない（`engine/src/core/expert_source.cpp:2842-2858`）。
- `STRATA_UNBUFFERED_LOAD` が空でない値で設定されると、先にその値の先頭文字で unbuffered の有無が決まり、この変数による cache 判定を通らない。先頭が `0` なら cache、その他なら unbuffered である（`engine/src/core/expert_source.cpp:963-972`）。
- `STRATA_FILE_TIER_HONEST` は利用可能 RAM の見積もりに関係する。未設定または先頭が `0` 以外なら host memory のより小さい available 値も反映し、先頭が `0` ならその補正をしない（`engine/src/core/expert_source.cpp:978-987`）。
- 現行ルールで cache 判定が true、`read_bytes > 0`、計算した held 比率が 0.5 未満の場合、`STRATA_FILE_TIER_PROBE=0` で probe を抑止しない限り drive probe を行う。probe が direct 優位と判断すれば、現行ルールでも unbuffered になる。旧ルールではこの probe 分岐に入らない（`engine/src/core/expert_source.cpp:1009-1033`）。
- RAM copy 完成後の再判定は Linux の `--mmap-experts` かつ正の RAM 予算で、startup 中に確定済みでない場合に行われる（`engine/src/program/generate.cpp:12219-12229`）。

## 実行時の詳細

初回判定では `set_unbuffered` が expert 総量と RAM 予算から `arena_bytes` および RAM copy 外の `read_bytes` を作り、`file_tier_unbuffered` を呼ぶ。Linux では利用可能 RAM が取得できなければ unbuffered を選ばず、理由を `the available RAM is unknown` とする。判定が unbuffered を選んだ後に `open_direct` を試し、ファイルを `O_DIRECT` で開けなければ理由を付けて false を返し、file cache 経路に残る（`engine/src/core/expert_source.cpp:973-977, 2842-2864, 2797-2813`）。

この変数に static cache はなく、初回の判定と RAM copy 後の再判定それぞれで環境を読み直す。再判定は RAM copy 実績と GPU 側に残る expert 分を使って cache 判定をやり直し、結果が変われば direct file handle を開くか閉じる（`engine/src/core/expert_source.cpp:999, 2867-2903`; `engine/src/program/generate.cpp:12219-12229`）。従ってプロセス環境がこの二つの判定の間に変更されれば再判定には反映されるが、各判定の途中では読み直さない。

## ログと測定値

`strata generate` は初回に stderr へ `strata generate: the file tier reads %s (%s)\n` を出す。第 1 引数は `unbuffered` または `through the file cache`、第 2 引数は RAM 判定の理由である。理由には利用可能 RAM、RAM copy に残る量、ファイルから読む expert 量、および `the file cache can/cannot keep the ones that come back` が含まれる。再判定時は `strata generate: the file tier reads %s%s (%s)\n` を出し、方式が変わると第 2 引数が ` (changed)` になる（`engine/src/program/generate.cpp:8654-8658, 12224-12229`; `engine/src/core/expert_source.cpp:1003-1008`）。

現行ルールでは probe が走った場合、理由に direct / cached-path の速度と選択結果が追記される。probe が実行できない場合は `the drive probe could not run, the file cache stays` が追記される（`engine/src/core/expert_source.cpp:1014-1031`）。この環境変数自体に固有の警告や終了経路はなく、選んだ経路で `O_DIRECT` を開けないと file cache に fallback する（`engine/src/core/expert_source.cpp:2797-2805, 2848-2858`）。

## 根拠

- `engine/src/core/expert_source.cpp:959-1038` — platform ごとの判定、対象変数の読み取り、旧／現行ルール、probe 条件。
- `engine/include/strata/platform/memory.hpp:54-60` — room、必要量、floor、clamp の計算。
- `engine/src/core/expert_source.cpp:2797-2813, 2842-2903` — Linux の direct open、初回判定、再判定、fallback。
- `engine/src/program/generate.cpp:8645-8658, 12219-12229` — CLI 条件、初回と再判定のログ。
- `docs/AMD_HIP.md:521` と `docs/SETTINGS.md:77` は変数名と gfx906 / Linux 上書きの概要を記すが、詳細な判定は上記ソースを根拠とした。
