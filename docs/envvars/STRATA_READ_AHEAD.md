# `STRATA_READ_AHEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

ファイルを読む前に Strata が OS へ出す先読みヒントを有効・無効にする。Linux/macOS の engine では、メモリマップ範囲に `madvise(..., MADV_WILLNEED)`、ファイル範囲に `posix_fadvise(..., POSIX_FADV_WILLNEED)` または macOS の `fcntl(..., F_RDADVISE, ...)` を要求する。いずれも 128 KiB 単位で要求し、要求自体は待たず、戻り値も無視する。Windows の共通 memory helper は常に無効で、この変数を読まない（`engine/src/platform/memory.cpp:160-162,205-231`）。

engine では重み・ネイティブ tensor・MTP draft ファイルを読み込む前のヒント、および mapped expert の profile fill / expert-cache 構築時のヒントが対象（`engine/src/core/weights.cpp:315-320`、`engine/src/core/native_dense.cpp:424-427`、`engine/src/core/native_head.cpp:185-188,241-245,534-542`、`engine/src/core/mtp.cpp:159-166,473-481`、`engine/src/core/expert_source.cpp:2675-2689,4607-4613`）。SYCL にも対応する呼び出しがある（`engine/sycl/src/core/weights.cpp:303-320`、`engine/sycl/src/core/native_dense.cpp:297-300`、`engine/sycl/src/core/native_head.cpp:59-62,190-197`、`engine/sycl/src/core/mtp.cpp:156-163,395-405`、`engine/sycl/src/core/expert_source.cpp:962-976,2059-2065`）。

この変数が止めるのは OS への advisory 要求であり、実際のファイル読み込みや Strata 内部の expert prefetch 全般を止めるものではない。unbuffered expert 読み込みの batch prefetch は別経路で行われ、`STRATA_IO_PREFETCH` 等の制御も別である（`engine/src/core/expert_source.cpp:2659-2673,2692-2719`）。

別プロセスの `strata-vision` も Linux で mmproj を読む前に同名変数を直接読み、同ファイル全体への `posix_fadvise` 要求を行う（`terminal/tools/vision/strata_vision.cpp:127-140`）。

## 値と判定

engine の Linux/macOS 共通 helper は `std::getenv` の結果を `std::atoi(v) != 0` で判定する。未設定は ON、設定済みは `atoi` の変換結果が非 0 なら ON。文字列全体の妥当性検査、clamp、警告はない（`engine/src/platform/memory.cpp:205-211`）。

| 条件（build / 実行経路） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Windows 以外の engine 共通 helper | ON | `1`、`-1`、`2`、`1tail`、` 1`（`atoi` が非 0） | `0`、`0anything`、空文字、`true`、空白だけ（`atoi` が 0） |
| Windows の engine | OFF（値を読まない） | なし | 常に無効 |
| Linux の `strata-vision` | ON | engine と同じ `atoi` 判定 | engine と同じ `atoi` 判定 |
| Windows / macOS の `strata-vision` | 適用外 | なし | このコードは判定箇所ごと compile 対象外 |

`atoi` は先頭の空白と符号を許し、数字列の後ろは検査しないため、`1tail` は ON、`0tail` は OFF、`1.5` は ON になる。`true` / `false` はどちらも 0 として扱われる。数値の範囲検査は実装されていない。vision での `getenv` も同じ条件式を使う（`terminal/tools/vision/strata_vision.cpp:127-135`）。

## 有効になる条件

- engine の OS advisory は Windows 以外でのみ実装される。Windows は `read_ahead_enabled()` が常に `false` を返し、両方の `advise_willneed` overload も no-op（`engine/src/platform/memory.cpp:160-162`）。
- マッピングへの要求はポインターが null でなく byte 数が正の場合に限る。file descriptor への要求は fd が非負の場合に限る（`engine/src/platform/memory.cpp:213-223`）。
- expert source の mapped-file hint は、source が開かれ、unmapped でなく、direct/unbuffered でない場合に限る。SYCL 実装も mapped source かつ非 direct の場合に限る（`engine/src/core/expert_source.cpp:2675-2689`、`engine/sycl/src/core/expert_source.cpp:962-976`）。
- profile-fill の先読み候補数は別の `STRATA_FILL_AHEAD` が設定されていればその `atoi` 値（負数は 0 に clamp）、未設定なら 256。候補数が正でも `advise_pairs` が false（例えば `STRATA_READ_AHEAD=0` または Windows）なら候補数は 0 になる（`engine/src/program/generate.cpp:9767-9774`、`engine/sycl/src/program/generate.cpp:5375-5382`）。
- `strata-vision` の専用ヒントは `!_WIN32 && !__APPLE__` のビルドだけで実行する。mmproj 引数が必須で、ファイルを開けた場合に限って `lseek` で得た長さまで 128 KiB ごとに要求する（`terminal/tools/vision/strata_vision.cpp:93-95,127-140`）。

## 実行時の詳細

- engine の `read_ahead_enabled()` は関数内 `static const bool` に初回評価結果を保存する。したがって Linux/macOS の engine では最初の helper 呼び出し時に一度読み、プロセス実行中に環境を変更しても反映しない（`engine/src/platform/memory.cpp:205-211`）。CLI 引数による上書きはない。
- engine は memory-mapped データに対してページ境界から 128 KiB ごとに `madvise` を行い、fd に対しても範囲の先頭から 128 KiB ごとに要求する。macOS の fd 経路は `F_RDADVISE`、その他は `POSIX_FADV_WILLNEED`。各 OS 呼び出しの戻り値は無視され、失敗時に Strata の fallback 処理や終了にはつながらない（`engine/src/platform/memory.cpp:213-231`）。
- GPU/backend の CUDA・SYCL 等に応じて上記 platform helper の実装が変わるのではなく、engine の呼び出し元が helper を使う箇所で共通判定される。Windows は platform 実装によって全て無効。読み込み自体の失敗は各読み込み元の通常のエラー処理に従い、この変数はそれを抑止しない。
- mapped expert profile fill が `advise_pairs` に依存する場合、無効時はその advisory が行われず fill の `fill_ahead` も 0 にされる。一方、direct/unbuffered source の `prefetch_pairs` batch 読み込みは別経路で、`STRATA_READ_AHEAD` の判定を受けない（`engine/src/program/generate.cpp:9764-9793`、`engine/src/core/expert_source.cpp:2659-2673`）。
- vision は `main` 内で mmproj の advisory 前に環境を直接読む。engine helper の static cache とは共有せず、プロセスごとに一度判定する。mmproj を open できない場合は advisory を飛ばして通常の reader に進み、advisory のエラー戻り値も無視する（`terminal/tools/vision/strata_vision.cpp:127-140`）。
- `STRATA_READ_AHEAD` が変えるのは読み込みの先行要求である。tensor/expert の選択やデータ内容を変更する分岐はこれらの呼び出し元にはない。OS が要求をどう実行するかは Strata のコードからは保証されない。

## ログと測定値

memory helper と `strata-vision` はこの変数について有効・無効ログを出さない。OS advisory の失敗もログ化しない。例外的に engine の profile fill では `strata generate: the profile fill asks for %lld pairs ahead (STRATA_FILL_AHEAD)` を stderr に出し、`STRATA_READ_AHEAD=0` などで `advise_pairs` が使えない場合、表示される候補数は 0 になる（`engine/src/program/generate.cpp:9767-9774`、SYCL: `engine/sycl/src/program/generate.cpp:5375-5382`）。

Strata の `docs/DETAILS.md:320-322` は weights と MTP draft を読み込み前に 128 KiB 単位で要求し、この変数で無効化できると記す。`docs/TROUBLESHOOTING.md:119-121` は Linux での先読みと変数による停止を案内する。これらは advisory の効果を保証する記述ではない。資料中の cold-start 測定値はこの変数の比較条件・測定環境と結び付いていないため、本書では性能値として扱わない。

## 根拠

- `engine/src/platform/memory.cpp:160-162,201-231` — Windows no-op、非 Windows の変換/cache、および OS advisory。
- `engine/include/strata/platform/memory.hpp:80-86` — API の範囲と Windows / `STRATA_READ_AHEAD=0` の説明。
- `engine/src/core/expert_source.cpp:2675-2689,4607-4613`、`engine/sycl/src/core/expert_source.cpp:962-976,2059-2065` — mapped expert に対する条件付き advisory。
- `engine/src/program/generate.cpp:9764-9793`、`engine/sycl/src/program/generate.cpp:5372-5391` — `STRATA_FILL_AHEAD` との連携と観測ログ。
- `engine/src/core/weights.cpp:315-320`、`engine/src/core/native_dense.cpp:424-427`、`engine/src/core/native_head.cpp:185-188,241-245,534-542`、`engine/src/core/mtp.cpp:159-166,473-481` — CUDA engine のファイル / tensor 読み込み前呼び出し。
- `engine/sycl/src/core/weights.cpp:303-320`、`engine/sycl/src/core/native_dense.cpp:297-300`、`engine/sycl/src/core/native_head.cpp:59-62,190-197`、`engine/sycl/src/core/mtp.cpp:156-163,395-405` — SYCL の対応呼び出し。
- `terminal/tools/vision/strata_vision.cpp:127-140` — Linux の vision reader が行う直接判定と mmproj advisory。
- `docs/DETAILS.md:320-322`、`docs/TROUBLESHOOTING.md:119-121` — Strata 文書との照合。
