# `STRATA_ARENA_RAM_FALLBACK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`generate` が expert arena を必要な RAM に読み込めないと判定したとき、expert をファイルから読む `--mmap-experts` 経路へ自動で切り替えてよいかを決める。通常（未設定）は切替を許可する。これは判定の許可だけを制御し、RAM 不足の解消や `--mmap-experts` 自体の強制ではない。すでに `--mmap-experts` が選ばれている実行経路ではこの変数による判定は使われない（`engine/src/program/generate.cpp:8621-8622,8745-8747,8602-8604`）。

## 値と判定

`std::getenv` で値を取得し、未設定または空文字なら許可する。空でない値は `std::atoi(value) != 0` で判定するため、文字列全体の数値検証や真偽値の文字列比較はしない（`engine/src/program/generate.cpp:8602-8603`, `engine/include/strata/core/ple_residency.hpp:70-74`）。

| 条件 | unset | 許可になる設定値の例 | 許可されない設定値の例 |
|---|---|---|---|
| arena 経路で、後述の CLI 条件を満たす | 許可 | `1`、`-1`、`1tail`、` 1`（`atoi` の結果が非ゼロ） | `0`、`0tail`、`true`、`false`、`x1`、空文字（空文字は unset と同じく許可） |

したがって `true` は有効化文字列ではなく、`atoi` が 0 を返すため許可しない。先頭の空白と数値接頭辞は `atoi` の変換に従い、後続文字は数値変換後に検証されない。数値として変換できない文字列は 0 となる。範囲検査もないため、`int` の範囲外の文字列は設定値として頼れない。先に `--ple-io ram` を明示した場合、または共有 arena ファイルを指定した場合は、値にかかわらず許可されない（`engine/include/strata/core/ple_residency.hpp:70-73`）。

## 有効になる条件

- `generate` が `o.mmap_experts == false` の arena 経路に入ること。すでに `--mmap-experts` が有効なら file source 側に進み、arena RAM fallback の判定は行われない（`engine/src/program/generate.cpp:8621-8622,8745-8747`）。
- `--ple-io ram` を明示していないこと。`--ple-io ram` を指定すると、`ple_io_explicit && ple_io == "ram"` が true になり、自動切替は抑止される。これは CLI 引数が環境変数より優先する条件である（`engine/src/program/generate.cpp:3901,8602-8603`）。
- `--shared-expert-arena` のパスが空であること。共有 arena を指定すると自動切替は抑止される（`engine/src/program/generate.cpp:4218-4219,8602-8603`）。
- arena を開く際に、利用可能 RAM またはハードメモリ上限に対して不足と判定され、RAM fallback の分岐が実際に選ばれること。RAM が足りていればこの変数が許可でも挙動は変わらない（`engine/src/core/expert_source.cpp:6533-6537,6543-6549,6604-6605,6652-6661`）。
- Linux では、shortfall がホストの空きページ・破棄可能な file cache・適合する huge page pool で賄えると判定される別経路があり、その場合は arena をロードするため自動切替には進まない（`engine/src/core/expert_source.cpp:6604-6649`）。

## 実行時の詳細

変数は `generate.cpp` の arena 初期化時に一度読み、プロセス内の `ram_fallback_ok` に保持する。以降の arena 再試行で読み直さないため、実行中の環境変更はこの判定に反映されない（`engine/src/program/generate.cpp:8595-8604,8860-8872`）。helper は「`--ple-io ram` を手動指定したか」「共有 arena が指定されたか」を先に判定し、どちらかなら環境値を見ずに false を返す（`engine/include/strata/core/ple_residency.hpp:67-74`）。

RAM 不足判定は arena の読み込み前に行われる。ハードメモリ上限が必要量を下回る場合、fallback 許可時は arena を開かず `ram_short` を返し、呼び出し側が file source を選ぶ。許可されない場合は上限エラーを出して起動に失敗する。利用可能 RAM の不足が待機後も続く場合、fallback 許可時は同じく file source に切り替える。許可されない場合は不足警告を出したうえで arena のロードを続行する（`engine/src/core/expert_source.cpp:6543-6559,6560-6564,6652-6675`）。

自動切替時は `o.mmap_experts` を true にし、最大 2 pass のループでファイル経由の source を開き直す。ファイル source を開けなければ、切替状態を戻して arena を従来どおり試す。固定 profile があり、既存の resident CPU expert 指定がなく、`STRATA_ARENA_FALLBACK_RESIDENT` の先頭文字が `0` でない場合は、fallback のファイル経路で profile 順の RAM copy も設定される。このとき RAM 予算は利用可能 RAM から headroom を引いて算出される（`engine/src/program/generate.cpp:8600-8601,8631-8640,8890-8911`）。

## ログと測定値

この変数の設定値自体を表示するログはない。fallback が実際に選ばれると stderr に `strata generate: not enough RAM for the expert arena (...)` で始まる行を出し、`--serve` では同じ案内を stdout にも出す。その後ファイル source が開けると `strata generate: experts via mmap (not enough RAM for the expert arena: the same source as --mmap-experts; ...)` と表示する（`engine/src/program/generate.cpp:8876-8888,8645-8647`）。

fallback を許可しない状態で利用可能 RAM だけが不足する場合は arena を続行し、stderr に `the expert arena needs ...: the load may swap or be stopped by the OS...` の警告を出す。ハードメモリ上限不足では `ArenaExpertSource: the expert arena needs ...: it would be killed while loading...` をエラーとして返し、呼び出し側が終了コード 1 で終了する（`engine/src/core/expert_source.cpp:6551-6558,6663-6675`, `engine/src/program/generate.cpp:8913-8915`）。測定値は記載しない。`docs/DETAILS.md` にこの環境変数の記述は見当たらず、コード内コメントの測定主張をこの変数自体の測定結果としては扱わない。

## 根拠

- `engine/src/program/generate.cpp:8595-8605` — 環境変数の唯一の実読み取り、CLI/共有 arena 条件、起動時の値保存。
- `engine/include/strata/core/ple_residency.hpp:67-74` — fallback 許可条件と `atoi` 判定。
- `engine/src/program/generate.cpp:8621-8622,8745-8747,8860-8872,8876-8915` — arena/file source 分岐、fallback 後の再試行、通知、失敗時の終了。
- `engine/src/core/expert_source.cpp:6533-6675` — RAM / hard limit 判定、待機、Linux file-cache 判定、fallback または警告。
- `engine/src/program/generate.cpp:3901,4218-4219` — `--ple-io` と `--shared-expert-arena` の引数記録。
