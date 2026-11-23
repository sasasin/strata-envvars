# `STRATA_SM89_PERF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の sm_89（Ada、RTX 40 系など）で、Strata が起動時に 17 個の速度スイッチの既定値をプロセス環境へ設定するかを制御する。未設定または先頭文字が `0` でない値なら既定値表を使い、`STRATA_SM89_PERF` の先頭文字が `0` なら表を適用しない。表の適用は `nv_default_env` と `apply_nv_defaults` が行う（`engine/src/core/nv_defaults.cpp:15-18,75-103,222-237`）。

## 値と判定

`off(name)` は `std::getenv` の戻り値が null でないことと、その先頭文字が `'0'` であることだけを見る（`engine/src/core/nv_defaults.cpp:15-18`）。文字列全体の数値変換や真偽値 parse はしない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| sm_89 の表選択 | 表を適用する | 空文字、`1`、`true`、`false`、` 0` など、先頭文字が `0` でない値 | `0`、`0anything`、`00` など、先頭文字が `0` の値 |
| `STRATA_DEFAULTS` との組み合わせ | `STRATA_DEFAULTS` が `026` 系でなければ表を適用する | `STRATA_DEFAULTS` 未設定、空文字、`0` など | `STRATA_DEFAULTS=026`、`0.2.6`、`v0.2.6` は表を適用しない。それ以外の文字列はこの条件では無効化しない（`engine/include/strata/core/defaults_026.hpp:21-29`、`engine/src/core/nv_defaults.cpp:81-82`） |

空白除去、大文字小文字変換、数値としての妥当性検査はない。たとえば `false` は先頭が `0` でないため、sm_89 表の停止値にはならない。

## 有効になる条件

- CUDA の起動経路で GPU が 1 台以上見つかり、表示されている全 GPU の compute capability が同じ場合に `apply_nv_defaults` が呼ばれる。先頭 GPU の capability が 8.9 の場合にこの表が候補になる（`engine/src/program/generate.cpp:4416-4444`、`engine/src/core/nv_defaults.cpp:37-40,75-83`）。異なる capability の GPU が混在するとこの呼び出しはスキップされる（`engine/src/program/generate.cpp:4423-4432,4445-4464`）。
- `STRATA_SM89_PERF` が上記の停止値でなく、かつ `STRATA_DEFAULTS` が 026 系トークンでないこと。どちらかを満たさない場合は sm_89 表が空になり、表由来のスイッチは自動設定されない（`engine/src/core/nv_defaults.cpp:81-82`）。
- `nv_default_env` が返す既定値は、`STRATA_ADAPT_LAG=2`、`STRATA_ATTN_DAILY=1`、`STRATA_GR_UP75=1`、`STRATA_GU_SWIGLU=1`、`STRATA_QSA_ROWS=1`、`STRATA_B6_MMVQ_ROWS=1`、`STRATA_HC_UPMIX=1`、`STRATA_Q80_ROWS1=1`、`STRATA_EXP_MODE=8`、`STRATA_SIDE_MIXER=2`、`STRATA_DEQUANT_SIDE=1`、`STRATA_LFUSE=1`、`STRATA_PLE_COMPACT=1`、`STRATA_PLE_COPY_STREAM=1`、`STRATA_PF_FUSED_KQ=1`、`STRATA_PREFILL_CPU_SHARE_NT=32`、`STRATA_PREFILL_CPU_SHARE_MAX=6144`（`engine/src/core/nv_defaults.cpp:83-101`）。これらの各スイッチの機能が実際に使われるかは、それぞれの実装側の条件にも従う。
- 追加で `STRATA_ADAPT_FETCH=2` が候補になるのは、メイン GPU の VRAM が 13 GiB 以下の場合。16 GiB より大きい場合は代わりに `STRATA_VERIFY_DEVICE_HITS=1` が候補になり、13 GiB 超 16 GiB 以下ではどちらも追加されない（`engine/src/core/nv_defaults.cpp:21-26,102-103`）。メイン GPU は `STRATA_PRIMARY_DEVICE` を読み、範囲外や未設定なら device 0 とする（`engine/src/program/generate.cpp:4433-4443`）。
- 個別スイッチがすでに環境に存在すれば、その値が空文字や `0` を含めて優先され、Strata は上書きしない（`engine/src/core/nv_defaults.cpp:227-233`）。このため個別スイッチを明示設定すれば、sm_89 表が有効でもそのスイッチの表既定値は設定されない。

## 実行時の詳細

起動時に GPU 数と全 GPU の compute capability を調べ、同一 capability のとき `apply_nv_defaults` が表を選び、まだ設定されていない名前だけをプロセス環境へ追加する。Windows では `_putenv_s`、それ以外では `setenv(..., 0)` を使う（`engine/src/program/generate.cpp:4422-4444`、`engine/src/core/nv_defaults.cpp:222-237`）。ソース上にリクエストごとの再読込やこの変数自身の static cache はない。表選択時に `STRATA_DEFAULTS` は `qwen_defaults_026()` が初回呼び出し時に static cache する（`engine/include/strata/core/defaults_026.hpp:26-30`）。起動後に `STRATA_SM89_PERF` を変更しても、適用済みの既定値は取り消されない。

sm_89 の表が一つ以上の名前を設定した場合だけ stderr に既定スイッチ一覧を出す。停止条件に該当する場合、または表の全スイッチが既に環境に存在する場合は、この表による行は出ない（`engine/src/core/nv_defaults.cpp:227-253`）。ログは `strata: sm_89 (Ada): <件数> exact speed switches on by default (STRATA_SM89_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): <設定名一覧>` の形式で、`STRATA_ADAPT_FETCH` も新規設定する場合は `exact` がなく `; ADAPT_FETCH is on because this card has 16 GiB of memory or less, it does not give bit-for-bit the same text, STRATA_ADAPT_FETCH=0 turns it off` が続く。

## ログと測定値

表のスイッチを一つ以上新規設定したときのログ形式と出力先は上記のとおり（`engine/src/core/nv_defaults.cpp:238-253`）。この変数自体によるエラー、終了、timeout の経路は見つからなかった。

`docs/DETAILS.md` の「bitwise decode switches on by default」表には sm_89 の行がなく、同資料だけではこの表を確認できない。ここでの有効条件と既定値は、対象 commit の実装を根拠に記載した（`docs/DETAILS.md:1456-1468`、`engine/src/core/nv_defaults.cpp:75-103`）。この文書では独立に確認していない性能値を記載しない。

## 根拠

- 候補変数の唯一の実行時読み取りと値判定: `engine/src/core/nv_defaults.cpp:15-18,81-82`
- sm_89 の既定値表と VRAM 条件: `engine/src/core/nv_defaults.cpp:75-103`
- 既定値の適用、既存値の優先、ログ: `engine/src/core/nv_defaults.cpp:222-253`
- 呼び出し条件とメイン GPU 選択: `engine/src/program/generate.cpp:4416-4444`
- `STRATA_DEFAULTS` の値判定と cache: `engine/include/strata/core/defaults_026.hpp:21-30`
- 対応する DETAILS 節: `docs/DETAILS.md:1456-1468`
