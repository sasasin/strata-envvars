# `STRATA_WIN_HIP_RISKY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows の HIP ビルドで、利用者が要求した `--adapt-async 1` または `STRATA_ADAPT_OVERLAP=1` を既定で拒否する安全ガードを解除する。変数だけではどちらの機能も有効にならず、各機能の設定が別途必要。解除した場合も、その機能が Windows/HIP で実行できると検証する処理ではなく、Strata は警告を出して要求された設定を後続処理へ渡す。判定は `_WIN32` と `STRATA_USE_HIP` のビルド条件によるもので、実行時の GPU 型番を調べていない（`engine/src/program/generate.cpp:2254-2262,2264-2283,11682-11689`、`engine/include/strata/core/win_hip_risky.hpp:20-25`）。

このガードは2つの機能を対象とする。`--adapt-async 1` はサーバーの adaptive tier の交換処理を非同期化する要求であり、`STRATA_ADAPT_OVERLAP=1` は adaptive tier のコピーと次の decode window を重ねる要求である（`engine/src/program/generate.cpp:2248-2253,11675-11681`）。

## 値と判定

Strata は `std::getenv` の結果を helper に渡し、文字列全体が空でないことと、文字列全体が `"0"` と異なることだけを判定する。数値変換、真偽値の構文検査、大文字小文字変換はしない（`engine/include/strata/core/win_hip_risky.hpp:17-18`）。

| ビルド・要求条件 | unset | 設定時にガード解除となる値 | 設定時に解除されない値 |
|---|---|---|---|
| Windows + HIP で対象機能を要求 | 拒否 | 空でない文字列。ただし文字列全体が `0` の場合を除く。例: `1`、`true`、`00`、`0anything`、` 0` | 空文字列、文字列全体が `0` |
| Windows + HIP で対象機能を要求していない | 対象機能は要求されていないため何もしない | 同左。要求を新たに有効化しない | 同左 |
| その他の OS / backend build | 許可判定（このガードによる変更なし） | 同左 | 同左 |

比較は文字列比較であり、値を `"0"` と照合する以外に大文字小文字を解釈しない。空白の trim もないため、空白だけの値や前後に空白を含む `0` は解除として判定される。`STRATA_ADAPT_OVERLAP` は別途、先頭文字が `1` のときだけ要求扱いとなる（例: `1anything` は要求、`true`・`01`・空文字は要求ではない）。`--adapt-async` は CLI 値を `atoi(...) != 0` で判定する（`engine/src/program/generate.cpp:2264-2282,4056`）。

## 有効になる条件

- ガード解除の対象は、Windows (`_WIN32`) かつ HIP (`STRATA_USE_HIP`) の engine build に限られる。いずれかが偽なら helper は `Allow` を返し、この変数による拒否・警告は発生しない（`engine/src/program/generate.cpp:2254-2262`、`engine/include/strata/core/win_hip_risky.hpp:22-25`）。
- `STRATA_ADAPT_OVERLAP` 経由では、その変数の先頭文字が `1` である必要がある。ガード解除値を与えても overlap の要求がなければ有効化されない（`engine/src/program/generate.cpp:2264-2282`）。
- `--adapt-async 1` 経由では、CLI 引数が 0 以外である必要がある。ガード解除値は `--adapt-async 0` を上書きしない（`engine/src/program/generate.cpp:4056,11682-11689`）。
- ガード解除後も `--adapt-async` は `--serve`、有効な adaptive tier、resident RAM mode / `--resident-experts` / expert arena などの条件を満たさないと停止され blocking tier に戻る。batch groups、arena での layer split や pipeline windows、peer device、remote expert optimization などにも制限がある（`engine/src/program/generate.cpp:11691-11732`）。
- ガード解除後も overlap は layer split、remote expert optimization、`--adapt-async`、pipeline windows、page-locked swap sources、`STRATA_DMA_BATCH`、lag/nowait 設定、resident RAM mode の条件、adaptive tier の稼働状態、device-planned layers などで実行されない場合がある（`engine/src/program/generate.cpp:15027-15048`）。
- CLI で `--adapt-async` を指定せず自動選択に委ねる経路は、CUDA build かつ serve、adaptive tier、arena、単一 GPU などを条件とする。Windows HIP build では自動選択の対象外であり、この変数は自動的に `--adapt-async` を要求しない（`engine/src/program/generate.cpp:11698-11715`、`engine/include/strata/core/adapt_async_default.hpp:19-60`）。

## 実行時の詳細

`--adapt-async` の経路では、`o.adapt_async` が真のとき設定時に `std::getenv("STRATA_WIN_HIP_RISKY")` を読み、Windows HIP で値が unset・空・`0` なら stderr に拒否行を出して `o.adapt_async = 0` にする。解除値があれば警告を出し、要求を保ったまま後続の適用条件を調べる（`engine/src/program/generate.cpp:11682-11689,11717-11732`）。この直接読み取りに static cache はない。

Overlap 経路では `adapt_overlap()` の関数内 `static const bool` 初期化時に `STRATA_ADAPT_OVERLAP` と `STRATA_WIN_HIP_RISKY` を読み、判定結果をキャッシュする。関数の初回呼び出しは、自動選択の条件判定中または serve の overlap 設定時に起きる。以降、そのプロセス内で環境変数を変更しても結果は更新されない（`engine/src/program/generate.cpp:2264-2283,11698-11715,15027-15042`）。

この環境変数を使う Strata の子プロセスへの転送・上書き処理は、候補名の全参照からは確認できない。Strata は `std::getenv` の結果を判定 helper に渡す（`engine/src/program/generate.cpp:2275,11683`）。

## ログと測定値

Windows HIP で要求が拒否された場合、stderr に対象設定に応じて次のいずれかを出す。

- `--adapt-async 1`: `strata: --adapt-async 1 is off on Windows with an AMD card: it reset the display driver there during long answers. STRATA_WIN_HIP_RISKY=1 turns it on anyway.`
- `STRATA_ADAPT_OVERLAP=1`: `strata: STRATA_ADAPT_OVERLAP=1 is off on Windows with an AMD card: it ended the first request with a GPU fault there, and it was only checked on NVIDIA cards. STRATA_WIN_HIP_RISKY=1 turns it on anyway.`

解除値で対象設定を要求した場合は、stderr に `strata: STRATA_WIN_HIP_RISKY=1: <setting> is on as asked, on Windows with an AMD card; it has reset the display driver or ended requests with a GPU fault there.` の形で警告する。`<setting>` は `--adapt-async 1` または `STRATA_ADAPT_OVERLAP=1`。後続条件で機能が止まる場合でも、この警告は要求を受け入れた時点で出る。その後 async 側は条件に応じて `strata generate: --adapt-async 1 is off (<reason>): the blocking adaptive tier` を出す。Overlap 側は起動時に稼働状態または停止理由を `strata serve: ...` として出す（`engine/include/strata/core/win_hip_risky.hpp:27-40`、`engine/src/program/generate.cpp:11682-11693,15081-15091`）。

ソースコメントには Windows HIP 上での過去の GPU fault / display-driver reset の報告があるが、この調査では新たな測定を行っていない（`engine/include/strata/core/win_hip_risky.hpp:3-7`）。

## 根拠

- `engine/include/strata/core/win_hip_risky.hpp:15-40` — 値判定、条件付きの拒否・許可、ログ文言。
- `engine/src/program/generate.cpp:2254-2283` — OS/backend build 判定、overlap の要求値・キャッシュ・判定。
- `engine/src/program/generate.cpp:4056,11675-11732` — CLI 値の扱い、`--adapt-async` のガード、後続条件と fallback。
- `engine/src/program/generate.cpp:15018-15091` — overlap の実行条件と serve 起動ログ。
- `engine/include/strata/core/adapt_async_default.hpp:19-60` — async の自動選択条件。
