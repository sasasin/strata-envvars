# `STRATA_COLD_OVERLAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--mmap-experts`（または RAM 不足時の同じ file-tier fallback）で `FileExpertSource` が使われる実行経路において、verify-window の CPU expert 読み込みを同期で行うか、読み込み中に読了済み expert を先に計算するか、Linux の GGUF mapping 上で page cache に全量ある expert を stage buffer へコピーせず計算するかを選ぶ。`expert_pool_dispatch_multi` が `d.cold_mode` を選び、`FileExpertSource::prefetch_begin` と CPU pool の dispatch が処理する（`engine/src/program/generate.cpp:8621-8647,1630-1637`、`engine/src/core/expert_source.cpp:5426-5469,5761-5787`）。

## 値と判定

dispatch 側は最初の `expert_pool_dispatch_multi` 呼び出しで `getenv` の結果を function-local `static` に保存する。未設定または空文字列は sentinel `-1` になり、Linux の GGUF in-place mapping なら既定値 4、それ以外は 0。非空値は `atoi` で変換後に 0〜4 へ clamp する。文字列全体の妥当性検査はなく、整数の先頭部分だけが使われる（`engine/src/core/expert_source.cpp:5462-5468`）。

| 条件 | unset / 空文字列 | 有効値 | 変換例・範囲外 |
|---|---|---|---|
| `expert_pool_dispatch_multi` の選択 | Linux 上で `role_ptr_` を持つ GGUF in-place source は 4、それ以外は 0 | 0〜4。0=同期読み込み、1=読み込みと計算を重ねる、2=計測用、3=1 + 条件付き zero-copy、4=zero-copy + 同期読み込み | `atoi`: `1tail`→1、`0anything`→0、`true` / `false` / `x`→0、` 2`→2、`-1`→0、`9`→4。大文字小文字は関係しない。数値としての全体妥当性は検証しない。 |
| `FileExpertSource::prefetch_begin` の独立 parser | Linux GGUF in-place source は 4、それ以外は 0 | 同じ値を意図した分岐だが、ここでは `atoi` 結果を clamp しない | 空文字列は unset と同じ。`5` 以上では dispatch が 4 に clamp する一方、この parser は 5 以上のまま扱い、4 専用の同期読み込み分岐に入らず非同期読み込みを起動しうる（`engine/src/core/expert_source.cpp:2557-2563,5464-5468`）。 |

`atoi` は不正な先頭文字列を 0 として扱い、数値後方の文字を無視する。`atoi` が表現できない範囲の入力は C/C++ の規則上安全な値として保証されず、Strata 側のエラー処理もない。上表のうち 0〜4 が意図された値域であり、5 以上は上記 parser 不一致のため無効値として扱うべきである。

モード 2 は `prefetch_begin` で読込みを開始した後、pending があれば全 read の完了を待ってから計算し、読込み時間を別計測する。モード 1 は pending のない expert を先に計算し、読込み完了ごとに残りを計算する。モード 3 はモード 1 に zero-copy 条件を加える。モード 4 は必要な blob を同期的に埋め、zero-copy 条件に合う expert は mapping から直接計算する（`engine/src/core/expert_source.cpp:2561-2573,5781-5787,5840-5865,5885-5920`）。

## 有効になる条件

- File expert source が選ばれる必要がある。`--mmap-experts` の経路で `FileExpertSource::open` が呼ばれ、RAM 不足時にも同じ source へ fallback する（`engine/src/program/generate.cpp:8621-8647`）。通常の expert arena / RAM copy だけを使う場合、この変数の file-tier 分岐は使われない。
- 対象処理は `drive_pool_multi_impl` から呼ばれる verify-window の CPU expert dispatch。対象層に CPU が処理する未 resident expert がない場合、読み込み・重ね合わせの仕事自体がない（`engine/src/program/generate.cpp:1630-1637`、`engine/src/core/expert_source.cpp:5737-5748,5771-5788`）。
- モード 1〜3 の非同期部分は、source が staged で、`io_fill_ && io_pf_ && direct_.empty()` の page-fill 経路でない場合に限り `prefetch_begin` の async worker を起動する。この page-fill 経路では同期的な `prefetch` 呼び出しに委ね、関数は pending なしで戻る（`engine/src/core/expert_source.cpp:2547-2553,2575-2612`）。
- zero-copy はモード 3 / 4 で要求されるだけでは足りない。GGUF の role mapping があり、mapping が unmap されておらず、direct-read でなく、CPU expert layout が native で、層 format の `tail_off == 0` であることが必要。さらに対象 expert の全 span が page cache に resident で、RAM complement や override にない場合に限り mapping の role pointers を返す。条件を満たさなければ stage buffer 経由で処理する（`engine/src/core/expert_source.cpp:2480-2498,2519-2530`）。Linux 以外では `linux_file_defaults()` は true にならず、zero-copy 判定の page-residency query を行う実装も Linux の `mincore` による（`engine/include/strata/core/expert_source.hpp:1081-1083`、`engine/src/core/expert_source.cpp:1088-1110`）。
- `STRATA_IO_PREFETCH` が page-fill 経路を有効にしている構成では cold-overlap の async worker 分岐が bypass される。`STRATA_IO_PREFETCH` や `STRATA_IO_PF_GATE` は別の file-tier read-ahead 機能であり、`STRATA_COLD_OVERLAP=0` だけではそれらを無効にしない（`engine/src/core/expert_source.cpp:2550-2553`、`engine/src/program/generate.cpp:8693-8704`）。
- `experts.bin` source は `linux_file_defaults()` が false のため未設定時の cold mode は 0。明示的な 1〜4 は overlap を選べるが、`role_ptr_` がないため GGUF mapping の zero-copy 条件は満たさない（`engine/include/strata/core/expert_source.hpp:1081-1089`、`engine/src/core/expert_source.cpp:2486-2498`）。

## 実行時の詳細

`cold_env` と `mode_env` は別々の function-local `static` であり、それぞれ最初に評価された値をプロセス内で保持する。実行中に環境値を変更しても、dispatch mode と `prefetch_begin` の mode は更新されない。`cold_log` も最初の serve log 判定時に static cache される（`engine/src/core/expert_source.cpp:2557-2561,5464-5468`、`engine/src/program/generate.cpp:23879-23880`）。

モード 0 は CPU が必要とする miss をまとめて同期 `prefetch` してから pool 計算に進む。モード 1 / 3 は pending miss の読み込みを worker thread で進め、decode thread は ready expert を計算し、worker が読み終えた expert ごとに残りを計算する。pending が残る場合は landing 待ちを行い、最後に worker を join する。モード 2 は開始した非同期 read を先にすべて join し、それから ready 分と read 分を計算するため、overlap の実行モードではなく計測モード。モード 4 は read を同期で埋めるが、zero-copy 条件に合う expert は mapping から読む（`engine/src/core/expert_source.cpp:2547-2612,5776-5790,5885-5929`）。

mode 3 / 4 の zero-copy expert は `zc_roles` が返す3つの mapping pointers を native CPU job format に組み直して使い、stage buffer を使わない。通常の miss は blob を取得して同じ CPU pool job に入る。ソースのコメントでは同一 token の expert 重み付き合算と結果 bit は batch order によって変わらないとしているが、この調査では別途実行検証していない（`engine/src/core/expert_source.cpp:5840-5865`）。

worker の direct read が失敗すると `fill_stage` fallback を試み、publish 失敗時には待ち側が blob を再読込する経路がある。最終的に source が blob を返せなければ dispatch は `d.failed` を設定し、`the expert source could not produce a blob` を失敗理由にする。環境変数の値自体に対する専用エラー・警告はない（`engine/src/core/expert_source.cpp:2590-2603,2621-2625,5842-5850`）。

## ログと測定値

Linux file-tier default により `io_pf_default` が成立して io prefetch が有効な場合、起動時に `strata generate: file tier (Linux defaults, ...): page-cached experts computed from the mapping (STRATA_COLD_OVERLAP=...), ...` を stderr に出す。ここで変数が未設定または空なら GGUF in-place source は `4`、別 source は `0` と表示する。これは cold mode 実行後の確認ログではなく、環境値（または既定値）の表示である（`engine/src/program/generate.cpp:8693-8714`）。

serve の各 request では、`STRATA_COLD_OVERLAP` が設定済み（空文字も含む）または `STRATA_IO_STATS` が設定済みで、かつ `cold_mode != 0` のとき stderr に `strata serve: cold reads (STRATA_COLD_OVERLAP=%d) this request: ...` から始まる累積差分ログを出す。cold mode 0 ではこのログを出さない（`engine/src/program/generate.cpp:23879-23896`）。

`docs/DETAILS.md:302-318` は Linux file tier の既定動作として GGUF in-place source の zero-copy（mode 4）を記載し、`docs/release-notes-0.2.0.md:60` は特定の構成での速度比を報告している。これらは Strata 文書に記載された測定値であり、本調査では再測定していない。モード 1〜3 の効果や一般的な性能差としては扱わない。

## 根拠

- 値の読み取り、既定値、clamp と parser の差: `engine/src/core/expert_source.cpp:2557-2563,5462-5468`
- mode に応じた CPU dispatch / wait / failure: `engine/src/core/expert_source.cpp:5761-5790,5840-5865,5885-5929`
- zero-copy の前提と stage buffer 回避: `engine/src/core/expert_source.cpp:2480-2530,2632-2644`
- file source / Linux default 判定: `engine/src/program/generate.cpp:8621-8647`、`engine/include/strata/core/expert_source.hpp:1081-1089`
- 起動・request log: `engine/src/program/generate.cpp:8693-8718,23879-23896`
- 関連資料: `docs/DETAILS.md:302-318`、`docs/release-notes-0.2.0.md:60`
