# `STRATA_CACHE_DIR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL prefill の int8 expert 経路が `auto` 判定に使う crossover 測定値を保存するファイルの親ディレクトリを指定する。値そのものを有効・無効として判定するスイッチではなく、読み書きする `i8-crossover.txt` の場所を変える。変数を読んでいるのは `engine/sycl/src/prefill/prefill.cpp` の `i8_cache_file()` である。同じ名前は SYCL 起動ラッパー `engine/sycl/serve/strata-sycl.sh` にもあり、コンテナ内の既定ディレクトリを指定して環境へ渡す。

## 値と判定

エンジンは `std::getenv` で値を得て、値が非 null かつ先頭文字が NUL でなければ、その文字列をディレクトリとして採用し、末尾に `/i8-crossover.txt` を連結する。数値・真偽値・存在するディレクトリかどうかの検査や trim はない。相対パス、空白を含む文字列、末尾 `/` もそのまま使われる（末尾 `/` の場合は `/` が二つ続く）。

| 条件 | unset | 設定時に有効になる値 | 空文字・その他 |
|---|---|---|---|
| SYCL エンジン | `HOME` が設定されていれば `$HOME/.cache/strata/i8-crossover.txt`。`HOME` が未設定なら `LOCALAPPDATA` が設定されている場合に `$LOCALAPPDATA/strata/i8-crossover.txt`。両方未設定なら cache path を空にする。 | 空でない文字列 `D` を使い `D/i8-crossover.txt`。 | 明示的な空文字は未設定と同様に扱い、上記 fallback に進む。`HOME` は getenv が非 null なら値が空でも採用し `/.cache/strata/i8-crossover.txt` になる。`HOME` が未設定の場合に限り `LOCALAPPDATA` を同様に確認し、空文字なら `/strata/i8-crossover.txt` になる。 |
| `strata-sycl.sh` 経由のコンテナ起動 | ラッパーが `/work/.strata-cache` を既定値として設定する。 | 呼び出し側から渡された非空の `STRATA_CACHE_DIR` は既定値を上書きし、値を `docker run -e` で渡す。 | 呼び出し側の値が空ならコンテナへは渡されない。ラッパーの既定値も空に置き換わっているため、エンジン内の `HOME` / `LOCALAPPDATA` fallback に進む。 |

根拠: `engine/sycl/src/prefill/prefill.cpp:958-965`; `engine/sycl/serve/strata-sycl.sh:28-43`。

## 有効になる条件

- SYCL エンジンで、int8 expert の `auto` モードが crossover 校正を呼び出す経路に入ったときだけ、このパスが cache read/write に使われる。主経路では `i8on` かつ `i8m == 2` の expert group flush 時に校正し、native expert layout、指定の gate/up・down format、`n_ff == 640`、`n_embd == 2560`、int8 kernel の利用可能性などが必要である（`engine/sycl/src/prefill/prefill.cpp:4775-4780,4862-4872`）。
- ペア処理経路では `fmt.gu_type == 22`、int8 モードが非ゼロ、kernel が利用可能で、さらに `i8m == 2` の場合に校正する（`engine/sycl/src/prefill/bmg_expert_window_walk.tpp:8-16`）。
- モードは `STRATA_PREFILL_MMQ`、空または未設定なら `STRATA_PF_I8` で選ばれる。先頭が `a` / `A` の文字列は auto、空でない値の先頭から連続する数字がすべて 0 なら off、それ以外は int8 強制となる。これらが空または未設定なら Battlemage 系デバイスかつ kernel 利用可能時に auto、それ以外は FP16 であり、auto でない場合は校正しない（`engine/sycl/src/prefill/prefill.cpp:333-345`; `engine/sycl/include/strata/prefill/esimd_moe.hpp:39-50`）。
- `STRATA_I8_FORCE` の先頭文字が `0` の場合、またはデバイスに必要な ESIMD / s8 matrix combination がない場合、kernel は利用不可となり auto 校正経路に入らない（`engine/sycl/src/prefill/esimd_moe.dp.cpp:840-858`）。利用可能判定はデバイスごとに static map へ保存される。
- CUDA、HIP、その他の backend の cache directory をこのコードが切り替える根拠は見つからない。CLI 引数による `STRATA_CACHE_DIR` の上書きもこの実装にはない。SYCL server のラッパーを使う場合は、上記の環境転送・既定値が適用される。

## 実行時の詳細

`i8_cache_file()` は呼び出されるたびに `STRATA_CACHE_DIR` と fallback 環境を読み直すため、プロセス環境が実行中に変更されれば次回の path lookup に反映される。読み取ったパスは `i8_cache_read()` / `i8_cache_write()` から使われる。通常の held-group 経路は queue と format の組ごとに `static std::map` へ校正結果を保持し、ペア処理経路は `Prefill::Impl::pair_i8_cutoff` に保持するため、同じプロセス内の同じ経路・format では初回校正後に再校正しない。cache file はプロセスをまたいで測定結果を再利用するためのもので、キーは device name、driver version、gate/up・down type、`n_ff`、`n_embd` である（`engine/sycl/src/prefill/prefill.cpp:1005-1018,4868-4872`; `engine/sycl/src/prefill/prefill.cpp:774-779`; `engine/sycl/src/prefill/bmg_expert_window_walk.tpp:11-14`）。

cache path が空なら読み書きを行わない。読み込みは `fopen(..., "r")` が失敗するか、一致キーを parse できなければ miss となり、その呼び出しで測定する。書き込みは既存ファイルの他キー行を残し、一致するキーの行を置き換える。最初の書き込み open が失敗すると親 directory に `mkdir(..., 0755)` を一度試し、再度 open する。mkdir または再 open に失敗しても書き込みは中止され、エラーは報告されない。親 directory を再帰作成する処理はない（`engine/sycl/src/prefill/prefill.cpp:967-1003`）。

## ログと測定値

- cache hit では stderr に `strata: int8 experts: crossover %.0f rows per expert (%s) from the cache for %s\n` を出す（`engine/sycl/src/prefill/prefill.cpp:1015-1018`）。
- miss 時に校正が成功すると stderr に `strata: int8 experts, measured here (%s): us per expert at 16/32/64/128/256 rows, int8 %.1f/%.1f/%.1f/%.1f/%.1f, FP16 %.1f/%.1f/%.1f/%.1f/%.1f -> crossover %.0f rows per expert (%s)\n` を出す。その後 cache へ書き込むが、書き込み失敗のログはない（`engine/sycl/src/prefill/prefill.cpp:1126-1129`）。
- 校正中の例外では stderr に `strata: int8 experts: the crossover measurement failed (%s): the int8 path is used below 64 rows per expert` を出し、64 rows を cutoff として返す。この失敗結果はこの分岐から cache へ書かれない（`engine/sycl/src/prefill/prefill.cpp:1099-1108`）。
- 読み込み miss、cache path が空、cache file の読み込み失敗、書き込み失敗について、それ自体を示すログはない。

## 根拠

- 環境値の読み取りと fallback path: `engine/sycl/src/prefill/prefill.cpp:958-965`
- cache file の read / write と失敗時の扱い: `engine/sycl/src/prefill/prefill.cpp:967-1003`
- 校正、キー、cache hit / miss、ログ: `engine/sycl/src/prefill/prefill.cpp:1005-1019,1099-1129`
- 主経路の条件と queue ごとの保持: `engine/sycl/src/prefill/prefill.cpp:4775-4780,4862-4878`
- ペア処理経路: `engine/sycl/src/prefill/bmg_expert_window_walk.tpp:8-16`; cutoff の初期値: `engine/sycl/src/prefill/prefill.cpp:774-779`
- int8 mode の環境値読み取りと選択: `engine/sycl/src/prefill/prefill.cpp:333-345`; `engine/sycl/include/strata/prefill/esimd_moe.hpp:39-50`
- kernel availability 条件: `engine/sycl/src/prefill/esimd_moe.dp.cpp:840-858`
- SYCL server wrapper の既定値と環境転送: `engine/sycl/serve/strata-sycl.sh:28-43,47-53`
