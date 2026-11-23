# `STRATA_ADMIT_MERGE_FIRST`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

サーバーのバッチ admission で、プロンプト末尾の複数 token と最初の生成 token を、分けた複数の verify window ではなく一つの最初の window で処理する最適化を有効にする。対象は `engine/src/program/generate.cpp` の `admit_merge_first_env()` と `merge_from` である。値が有効でも後述の条件がそろわなければ通常の prompt window と単独の最初の生成 window に戻る。コードコメントと `docs/BATCHING.md` も、batch admission の末尾 prompt token と最初の token を一つの window に入れる機能と説明している（`engine/src/program/generate.cpp:486-497,21422-21444`; `docs/BATCHING.md:110-125`）。

## 値と判定

`std::getenv` の戻り値を関数内 `static const bool` に一度保存し、設定されていて最初の文字が `'0'` でなければ有効とする。文字列全体の数値・真偽値 parse はなく、長さ・後続文字・空白・大文字小文字も検査しない（`engine/src/program/generate.cpp:491-497`）。

| ビルド／経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP engine の `generate.cpp` serve 経路 | OFF | `1`, `true`, `false`, 空文字列, ` 0` など、先頭文字が `0` 以外 | `0`, `0anything`, `0 ` など、先頭文字が `0` |

空文字列は `getenv` が null ではなく `v[0]` が終端文字になるため有効扱いとなる。値は文字単位で見るので `false` も有効、`0anything` は無効であり、数値妥当性や大文字小文字の区別はない。Metal/SYCL など別実装にこの名前の読み取りは見つからず、そこでの効果は確認できない（同ファイル `:493-495`）。

## 有効になる条件

値が有効でも、以下をすべて満たす必要がある。`merge_from` はどれかを満たさないと `-1` を返し、その区間はマージされない。理由ログは出さない（`engine/src/program/generate.cpp:21427-21444,21461-21465`）。

- server の `BGEN` admission で slot が割り当てられていること（`admit_slot >= 0`）。`BGEN` は利用可能な batch slot が必要で、slot 不在や不正な max_new は `ERR BGEN: no such free slot (--batch %d) or a bad max_new` となる（`engine/src/program/generate.cpp:18373-18389`）。
- `max_new == 1`、`batch_mtp` が無効、window pipeline (`pipe`) が無効であること。
- 最後の prompt 区間が `windows_ok` となり、その終端が `n - 1` であること。区間終端が turn/root/message/pin checkpoint の位置と重なる場合は無効。
- penalty history があり `pen_prompt` が無効、または画像入力、elastic K/V (`kvg.on`)、peer、remote cache / remote opt、filesystem swap がある場合は無効。
- `STRATA_LOGPOS` が未設定であること。設定値が空文字でも `getenv(...) != nullptr` なので無効化される。
- `host_res` が空でなく、pending swap がなく、全 expert の residency entry が VRAM 内を示すこと（`host_res` の値に負数がない）。全 verifier stage で `ar_live()` が true であり、最小 window 上限 `mt` が 2 以上であること。`mt` は `kVerifyMaxT` と各 stage の `max_t()` の最小値。

## 実行時の詳細

環境値は `admit_merge_first_env()` の最初の呼び出し時に評価される。結果は関数内 static に保存されるため、その後の同一プロセス内の環境変更は反映されない。呼び出しは window で処理する prompt 区間に限られるが、batch admission であるかを調べる前に環境値を読む（`engine/src/program/generate.cpp:491-497,21445-21461`）。

条件を満たす最終 window 区間について `merge_at = max(a0, n - mt)` とし、prompt の残り最大 `mt` token の読み込みを分離する。通常は `merge_at = -1` で最後の prompt token だけを最初の生成 window に入れるが、有効時は `merge_T = n - merge_at` として prompt の末尾 token 群と、それらを入力にした最初の生成 token の出力を同じ最初の window で処理する。`window` に prompt token 群を並べ、merged window の全 prompt row を commit し、出力として最後の row の token だけを送る（`engine/src/program/generate.cpp:21422-21444,21541-21549,22559-22605,22691-22701,22923-22924,22936-22943,22960-23010`）。

この分岐は admission request の初回生成でのみ設定され、最初の decode window が終わると `first_window` が false になる。`max_new != 1`、または適用条件のいずれかが外れる場合はマージせず通常経路を使う。子プロセスへの環境変数の転送・上書きはこの読み取り箇所では行わない（`engine/src/program/generate.cpp:22559-22605,23003-23010`）。

## ログと測定値

この変数専用の有効・無効ログや理由ログはない。`STRATA_TRACE` による trace が有効な場合、prompt 読み込み量を `strata trace: read %lld tokens (%s) in %.1f ms`、マージが成立した場合は `strata trace: the first window takes the last %lld prompt tokens` と stderr に出す（`engine/src/program/generate.cpp:21467-21475`）。読み込み・verify 処理に失敗した場合は通常の `ERR ...` 経路に入り得るが、この環境変数固有のエラー文言はない（同 `:21487-21499,22883-22887,22960-22965`）。本変数単独の性能測定値は記載しない。

## 根拠

- `engine/src/program/generate.cpp:486-497` — 値の読み取りと parse。
- `engine/src/program/generate.cpp:18373-18389` — `BGEN` での admission slot 割り当て。
- `engine/src/program/generate.cpp:21422-21475` — マージ条件、prompt window の分割、trace。
- `engine/src/program/generate.cpp:21541-21549,22559-22605,22691-22701,22923-23010` — merged first window の構成、commit、出力。
- `engine/include/strata/core/verify.hpp:212-215` — `ar_live()` が現在の stage residency table を確認すること。
- `docs/BATCHING.md:110-125` — batch admission 最適化としての説明。
