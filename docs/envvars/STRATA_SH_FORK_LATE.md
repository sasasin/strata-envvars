# `STRATA_SH_FORK_LATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

shared expert の処理を専用 CUDA stream / SYCL queue に fork する機能そのものではなく、fork を開始するタイミングを選ぶ。既定（unset）では router と doorbell の処理後に開始する。値の先頭が `0` なら、router の前に開始する。該当する実装は CUDA/HIP 共通の `Verifier::record_window` と SYCL の同名処理である。`engine/src/core/verify.cpp:2615-2627`、`engine/sycl/src/core/verify.cpp:1560-1575`。

## 値と判定

両実装とも `std::getenv` の戻り値を関数ローカル `static const bool` に保存し、値全体の parse や数値検査はしない。unset なら `sh_fork_late_env=true`。設定されていれば `e[0] != '0'` の結果を使うので、空文字も true になり、先頭文字が文字 `'0'` の場合だけ false になる。比較は大文字小文字の影響を受けないが、空白を読み飛ばさない。`engine/src/core/verify.cpp:2617-2620`、`engine/sycl/src/core/verify.cpp:1563-1566`。

| 条件 | unset | 遅延 fork になる例 | 早い fork になる例 |
|---|---|---|---|
| CUDA/HIP 共通、SYCL 共通 | true（遅延） | 空文字、`1`、`true`、`false`、` 0` など先頭が `0` でない文字列 | `0`、`00`、`0anything` など先頭が `0` の文字列 |

これは環境から直接読む設定で、対象名を読む CLI 引数や別の環境変数による上書き処理はこの実装にはない。`STRATA_SH_STREAM` は別途 fork 自体を有効にする設定であり、この変数の値判定には使われない。`engine/src/core/verify.cpp:415-424,2617-2627`、`engine/sycl/src/core/verify.cpp:253-263,1563-1575`。

## 有効になる条件

- `sh_fork` が true であること。CUDA/HIP 共通実装では `STRATA_SH_STREAM` が有効で、profiler が無効、`sh_cs_` と fork/join event が存在することが必要。SYCL ではさらに stepped mode でないこと、`sh_cs_` が既定 in-order queue でないことが必要。`engine/src/core/verify.cpp:2621-2623`、`engine/sycl/src/core/verify.cpp:1567-1571`。
- `STRATA_SH_STREAM` が無効なら shared expert は `cs` 上で実行され、fork のタイミング設定は実動作に影響しない。`STRATA_SH_STREAM` の値は unset 以外では先頭文字が `0` かどうかで判定され、未設定時の backend 既定は HIP で off、それ以外で on。アーキテクチャ既定がこの変数を設定する経路もある。`engine/src/core/verify.cpp:415-424`、`engine/sycl/src/core/verify.cpp:253-263`、`engine/src/core/arch_defaults.cpp:89-98`、`engine/src/core/nv_defaults.cpp:140-153`。
- 値が遅延を選んでも `ar_on()` のときは `sh_fork_late` が false となり、早い fork に戻る。`ar_on()` は `all_resident_ && !ar_off_`。この経路は device-only / zero-doorbell graph で doorbell publish を行わないため、遅延位置を選べない。`engine/src/core/verify.cpp:2621-2627,2686-2715`、`engine/include/strata/core/verify.hpp:602`、`engine/sycl/src/core/verify.cpp:1567-1575,1612-1641`、`engine/sycl/include/strata/core/verify.hpp:370`。
- CUDA/HIP 共通実装と SYCL 実装で判定式は同じ。サーバーモードやモデル種別に応じてこの変数自体を別解釈するコードは見つからなかった。

## 実行時の詳細

値は `record_window` 内の最初の該当処理で評価される。その時点で `getenv` の値を static に保存し、以後の window / layer で再読込しないため、プロセス起動後でも初回評価後の環境変更は反映されない。読み取り時に別プロセスへ転送する処理もない。`engine/src/core/verify.cpp:2617-2622`、`engine/sycl/src/core/verify.cpp:1563-1570`。

遅延 fork が選ばれると、GPU 側の router と doorbell publish の後に fork event を記録し、shared-expert stream/queue がその event を待つ。CUDA/HIP 共通実装は `cudaEventRecord` / `cudaStreamWaitEvent`、SYCL は queue barrier を使う。早い fork では同じ待ち合わせを router より前に置く。どちらの場合も shared expert の計算は同じ `shared_expert_multi(...)` に渡され、その後の join event/barrier を combine 側が待つ。`engine/src/core/verify.cpp:2624-2628,2708-2720,2746-2759,2939-2943`、`engine/sycl/src/core/verify.cpp:1572-1575,1622-1642,1667-1677,1803-1809`。

この値が直接変更するのは stream/queue 間の順序と重なり方であり、router の選択値や `shared_expert_multi` の引数を選ぶものではない。別 stream が有効でないときは計算先もタイミングも変えない。`engine/src/core/verify.cpp:2621-2627,2731-2750`、`engine/sycl/src/core/verify.cpp:1567-1575,1653-1671`。

## ログと測定値

この変数の値や「早い/遅い fork」を直接表示するログは見つからなかった。CUDA/HIP 共通経路には `win ... sh_stream=%ld ...` の診断表示があるが、示すのは stream fork が有効かどうかであり、fork 位置ではない。`engine/src/core/verify.cpp:1545-1548`。shared expert の処理で例外が起きた場合は通常の verify エラー経路として `verify shared expert: <例外内容>` を `err` に設定して false を返すが、この環境変数に固有の失敗処理ではない。`engine/src/core/verify.cpp:2746-2755`、`engine/sycl/src/core/verify.cpp:1667-1676`。

`docs/AMD_HIP.md:276-282` は doorbell 後に shared expert を fork する目的と stream fork 全体の測定例を記載するが、`STRATA_SH_FORK_LATE` の値ごとの比較ではないため、この変数の性能差としては記載しない。

## 根拠

- `engine/src/core/verify.cpp:2615-2627` — 値の読み取り、parse、fork 条件と早い fork の event。
- `engine/src/core/verify.cpp:2708-2720` — doorbell publish 後の遅延 fork。
- `engine/src/core/verify.cpp:2731-2759,2939-2943` — shared expert 実行と join。
- `engine/sycl/src/core/verify.cpp:1560-1575,1622-1642` — SYCL 側の読み取りと fork event/barrier の配置。
- `engine/sycl/src/core/verify.cpp:1644-1677,1803-1809` — shared expert 実行と join barrier。
- `engine/include/strata/core/verify.hpp:602`、`engine/sycl/include/strata/core/verify.hpp:370` — `ar_on()` の定義。
- `engine/src/core/verify.cpp:415-424`、`engine/sycl/src/core/verify.cpp:253-263` — `STRATA_SH_STREAM` の既定と判定。
