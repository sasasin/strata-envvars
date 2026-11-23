# `STRATA_CKPT_VRAM_SLOTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

CUDA 系の会話 checkpoint 保存で、GDN running state の device-to-device コピー先を保持する VRAM slot 数の上限を指定する。保存時には選ばれた slot に GDN state を置いたうえで host 側 checkpoint にも非同期コピーし、slot の tag が残っている checkpoint を復元するときは host image の代わりに同じ device の slot から復元する。slot が使えない場合も host image から復元する経路がある。対象は checkpoint の GDN state であり、回答内容や token 選択を変える設定ではない（`engine/src/core/conversation_state.cpp:319-388,417-464`）。

## 値と判定

値は `std::getenv` で取得し、未設定なら 0、設定されていれば `std::atoi` の結果を `std::max(0, std::min(16, ...))` で 0〜16 に制限する。整数文字列全体の妥当性検査はなく、`atoi` が数値として読めない先頭なら 0 になる。したがって空文字・`true`・`x3` は 0、`3tail` や先頭空白付きの ` 3` は 3、`-1` は 0、`17` は 16 になる。`atoi` による数値変換のため、小数や指数表記を解釈する設定ではない。`int` の範囲外の数値文字列については `atoi` の結果が保証されないため、clamp 前の値を含め動作を確定できない。値は `vram_slots_n()` の初回呼び出し時に static local として読み込まれ、その後プロセス内で環境を変えても更新されない（`engine/src/core/conversation_state.cpp:194-197`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| 上記の slot 数判定 | 0 | `1`〜`16`（`3tail` のような数値接頭辞も変換後に有効。17 以上も 16 に clamp） | 空文字、非数値接頭辞、`0`、負値（0 に clamp）。`int` 範囲外の数値文字列は結果不定 |

## 有効になる条件

- `STRATA_CKPT_ASYNC` が設定され、値の先頭文字が `1` である必要がある。`1`, `10`, `1anything` は on、空文字・`true`・`0`・` 1` は off。こちらも初回判定結果を static cache する（`engine/src/core/conversation_state.cpp:214-220`）。
- HIP、`STRATA_HIP_GFX906`、または Metal build では `ckpt_async_on()` が常に false を返すため、この slot 機能は使われない（`engine/src/core/conversation_state.cpp:214-220`; Metal の保存・復元分岐は同:303-306,417-425）。
- GDN checkpoint が 1 MiB 以上である必要がある。小さい状態は非同期 staging / slot 選択の分岐に入らない（`engine/src/core/conversation_state.cpp:319-320`）。
- 保存時に最大 16 個の slot の範囲内で、同じ device・同じサイズの既存 slot があれば再利用する。空き slot を新規確保する場合は `cudaMemGetInfo` が成功し、確保前の空き VRAM が checkpoint サイズより 1.5 GiB 超多く、さらに `cudaMalloc` が成功する必要がある。条件を満たさないと新規 slot は使わず、slot 数が上限に達して同サイズ・同 device の slot もなければその保存は slot なしで進む（`engine/src/core/conversation_state.cpp:198-212`）。
- async の staging buffer、pinned host buffer、stream の確保が揃わない場合は slot に保持せず通常のコピーへ進む（`engine/src/core/conversation_state.cpp:331-350,387-388`）。

## 実行時の詳細

保存時、非同期 checkpoint 条件を満たすと mutex を取って前のコピーを join し、必要なら staging 資源を作り直す。slot が有効なら `vram_slot_for` が同じ device・サイズの候補を選び、なければ条件付きで新規確保する。slot は書き換え前に tag を無効化し、device-to-device copy が成功すると checkpoint と slot に新しい tag を付けてから GDN の host コピーを background thread に渡す。slot がない場合は staging buffer が device-to-device copy の中継先になる。コピーが非同期条件を満たさない場合は `c.gdn` へ通常コピーする（`engine/src/core/conversation_state.cpp:319-388`）。

復元時は checkpoint の `dev_tag` が 0 でなければ mutex 下で現在 device・tag・GDN byte 数が一致する slot を探し、見つかれば LRU 使用時刻を更新して slot から session state へコピーする。一致する slot がない場合は該当 checkpoint の host コピーが完了するのを待ち、`c.gdn` から復元する。残りの PLE / indexer state も復元され、最後に device synchronize を行う（`engine/src/core/conversation_state.cpp:427-464`）。保存と slot 数は初回使用後 cache される。実行中の環境変数変更で slot 数は変わらない。slot 自体はプロセス内の static `VramSlots` に保持される（同:191-197）。

## ログと測定値

`STRATA_CKPT_VRAM_SLOTS` 固有の有効・無効ログは実装にない。VRAM 空き量チェックや slot 確保が失敗しても、その失敗は `cudaGetLastError()` で消費され slot なしで続行する経路がある（`engine/src/core/conversation_state.cpp:204-212,337-350`）。非同期 copy が失敗した場合は stderr に `strata: STRATA_CKPT_ASYNC: a checkpoint copy failed (%s)` が出る（同:276-281）。保存・復元全体が失敗した場合、serve 側 wrapper はそれぞれ `strata serve: checkpoint save: %s` / `strata serve: checkpoint restore: %s` を stderr に出す（`engine/src/program/generate.cpp:2561-2566,2578-2583`）。

`docs/DETAILS.md:1766,1771` は、変更作者が CMP 170HX（GA100 / sm_80）、PCIe Gen2 x4 で測定した報告として restore `114-126 -> 28-47 ms` を掲載する。同資料は手元で同等の sm_80 機を使った測定ではないと明記しているため、これは当該環境についての報告値であり、現 checkout で再測定した値ではない。

## 根拠

- 読み取り・変換・cache: `engine/src/core/conversation_state.cpp:191-197`
- slot の選択・空き VRAM 条件: `engine/src/core/conversation_state.cpp:198-212`
- async build guard と別変数の判定: `engine/src/core/conversation_state.cpp:214-220`
- checkpoint 保存時の slot コピー・fallback: `engine/src/core/conversation_state.cpp:319-388`
- slot からの復元と host fallback: `engine/src/core/conversation_state.cpp:427-464`
- 観測可能な失敗ログ: `engine/src/core/conversation_state.cpp:276-281`; `engine/src/program/generate.cpp:2561-2583`
