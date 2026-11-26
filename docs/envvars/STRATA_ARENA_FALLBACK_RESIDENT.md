# `STRATA_ARENA_FALLBACK_RESIDENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

expert arena の RAM 不足時に、通常のファイル読み込みへ切り替える fallback を、静的 expert profile がある場合に限り「profile 上位の experts を RAM にコピーし、残りをモデルファイルから読む」resident RAM mode にするかを制御する。`0` でこの自動切り替えを止め、plain file source を使う。変数は `generate` の arena 判定でだけ読まれる（`engine/src/program/generate.cpp:8595-8605,8876-8909`）。

有効な自動切り替えでは、GPU cache が保持しない experts のうち profile 順のものを、利用可能 RAM から headroom を除いた範囲でコピーする。残りはモデルファイルから読み込む。これは配置と回答を変える設定ではなく、arena 不足時の expert source を変える設定である。ソースコメントは plain file source と resident copy の回答が同じと説明する（`engine/src/program/generate.cpp:8892-8908`; `engine/src/core/expert_source.cpp:4044-4046,4134-4151`）。

## 値と判定

`std::getenv` の戻り値が null でないことに加え、先頭バイト `v[0]` が文字 `'0'` かを一度だけ調べる。先頭が `'0'` なら自動 resident fallback を無効にし、それ以外は有効にする。全体の parse、数値妥当性、空白除去、大文字小文字変換はしない（`engine/src/program/generate.cpp:8604-8605`）。

| 条件 | unset | 自動 resident fallback を有効にする値 | 無効にする値 |
|---|---|---|---|
| 全実行経路 | 有効（既定） | `1`, `true`, `false`, 空文字, ` 0`, `x` など先頭が `0` でない値 | `0`, `0anything`, `00` など先頭が `0` の値 |

`0anything` も数値変換エラーにはならず、先頭文字が `0` なので無効になる。一方、` 0` は先頭が空白なので有効扱いとなる。環境変数自体が設定されていて空文字でも有効扱いである。大文字小文字は判定に関係しない。CLI にこの値を上書きする引数はない（`engine/src/program/generate.cpp:8605,4211-4257`）。

## 有効になる条件

- Arena source を使う実行で、arena の RAM 判定後も不足し `ram_short()` になり、`generate` が `--mmap-experts` 相当の file source へ移ること（`engine/src/program/generate.cpp:8871-8891`）。既に `--mmap-experts` を選んだ実行ではこの arena 不足 fallback 分岐に入らない。
- その fallback 自体が許可されていること。`STRATA_ARENA_RAM_FALLBACK` が `0` なら無効で、手動指定の `--ple-io ram` または `--shared-expert-arena` がある場合も無効（`engine/src/program/generate.cpp:8600-8603`; `engine/include/strata/core/ple_residency.hpp:67-74`）。
- `--expert-profile` で静的 profile が指定されていること。profile の読み込みに失敗した場合はこの環境変数の fallback 以前にエラー終了する（`engine/src/program/generate.cpp:6746-6751,8898`）。
- 他の設定で既に `o.resident_cpu_experts` が true になっていないこと。`--resident-experts` や正の `--resident-budget-gib` 等による明示的 resident mode がある場合、環境変数による自動設定は上書きしない（`engine/src/program/generate.cpp:4218-4257,8898`）。
- `STRATA_ARENA_FALLBACK_RESIDENT` の先頭文字が `0` でないこと（`engine/src/program/generate.cpp:8605,8898`）。

条件を満たさない場合、arena 不足時は通常の file source に切り替わる。arena fallback の許可条件自体を満たさない場合はこの環境変数では変化せず、arena 判定側の従来処理が続く。

## 実行時の詳細

値は CLI 引数の処理後、arena source を用意する直前に `const bool` として一度読み込まれ、その後の arena fallback 分岐で参照される。リクエストごとの再読込や子プロセスへの転送はこの箇所にはなく、実行中に環境値を変えても判定は変わらない（`engine/src/program/generate.cpp:3838-3842,8595-8605`）。

arena が RAM 不足で開けず、`ram_short()` が true の場合、stderr に理由付きの「not enough RAM for the expert arena」行を出し、file source に切り替えて再試行する。`--serve` では同じ行を stdout にも出す（`engine/src/program/generate.cpp:8876-8891`）。変数が有効で profile があり、既存の resident mode がなければ、`STRATA_RESIDENT_PIN` を helper に渡して resident mode を設定し、ホストメモリをサンプルできた場合は `available - headroom` を予算として使う。headroom は `STRATA_RESIDENT_HEADROOM_GIB` が有効値ならそれ、そうでなければ `max(--ram-keep-gib, safety headroom)` であり、安全 headroom は Windows 8 GiB、それ以外 4 GiB（`engine/src/program/generate.cpp:8606-8617,8898-8908`; `engine/include/strata/core/ple_residency.hpp:174-182`）。

resident copy は GPU cache にない expert を profile 順で保持し、予算に収まらないものはファイル側に残す。ホストメモリをサンプルできた場合の自動予算は `available - headroom`（ただし headroom + 1 GiB 以下なら 0）である。予算が 0 の場合、呼び出し先は全 complement を保持する通常経路を試し、失敗して `resident_soft` が有効なら使用可能な分だけ保持する再試行を行う。正の予算で profile 上位が 1 件も入らない場合のように再試行も失敗すれば file source で続ける（`engine/src/program/generate.cpp:8904-8908,12077-12106`; `engine/include/strata/core/ple_residency.hpp:180-182`; `engine/src/core/expert_source.cpp:4044-4046,4145-4147`）。resident mode が作れた場合は `resident RAM mode: ...`、予算が使えない場合は warning が stderr に出る（`engine/src/program/generate.cpp:12196-12216`）。file source 自体を開けない場合は arena を旧方式で再試行し、その経路では自動 resident 状態を解除する（`engine/src/program/generate.cpp:8631-8640`）。

## ログと測定値

arena 不足時のログは `strata generate: not enough RAM for the expert arena (%s): this run reads the experts from the file, like --mmap-experts (slower; the answers are the same). To get the arena back, free that RAM and start again`。`--serve` 時は stderr と stdout の両方に出る（`engine/src/program/generate.cpp:8876-8888`）。resident allocation が成功した場合は `strata generate: resident RAM mode: ...`、予算 mode が成立しない場合は `WARNING: the RAM budget ... cannot be kept ...` などが stderr に出る（`engine/src/program/generate.cpp:12196-12216`）。この環境変数自体の値を表示するログはない。

`docs/DETAILS.md:878-896` は、12 GB GPU・63 GB PC・44.6 GiB available の条件で IQ3_S、128K 時に 9.4 tok/s から 25–28 tok/s になった測定を記載する。同節は arena 不足時の RAM copy fallback の説明に続けてこの測定を載せている。ソースコメントにも RTX 5070、63.1 GB RAM、44.6 GiB available、46.84 GiB arena の例として plain file source 9–10 tok/s と RAM copy 27–28 tok/s があるが、これはコメント中の一例であり、他環境の性能を示すものではない（`engine/src/program/generate.cpp:8892-8895`）。

## 根拠

- `engine/src/program/generate.cpp:8595-8617` — arena fallback 用状態、対象変数の読み取り、headroom の準備。
- `engine/src/program/generate.cpp:8871-8911` — RAM 不足時のログ、file source への切り替え、自動 resident mode の設定。
- `engine/src/program/generate.cpp:12077-12106,12196-12216` — profile 順の RAM copy、soft fallback、結果ログ。
- `engine/include/strata/core/ple_residency.hpp:67-74,174-182` — arena fallback の許可条件と自動予算計算。
- `engine/include/strata/core/resident_ram_copy.hpp:17-23` — 自動 resident mode のフラグ設定と `STRATA_RESIDENT_PIN` 判定。
- `engine/src/core/expert_source.cpp:4044-4046,4134-4151` — RAM 予算内で profile 順にコピーし、残りをファイル読み込みにする処理。
- `docs/DETAILS.md:878-896` — fallback の説明と条件付き性能測定。
