# `STRATA_SH_STREAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MoE の shared expert（共有 expert）の計算を、その層の routed expert 等が使う通常の GPU stream から分け、専用 stream で並行実行するかを制御する。CUDA/HIP の実装では `Verifier::record_window` 内で shared expert の計算を `sh_cs_` に投入し、event で通常 stream と依存関係を結ぶ。SYCL 実装も同様に専用 queue と barrier を使う。変数が切り替えるのは実行 stream と同期順序であり、ルーターの expert 選択を変更する分岐ではない（CUDA: `engine/src/core/verify.cpp:2615-2628,2735-2758`、SYCL: `engine/sycl/src/core/verify.cpp:1561-1575,1653-1677`）。

未設定時の基準は CUDA と SYCL で ON、HIP で OFF。ただし HIP は gfx1151 の Linux 既定表や gfx1103/gfx1150 用のセットアップ設定で ON になる場合がある。明示的な設定はアーキテクチャ既定値より優先される（`engine/src/core/verify.cpp:415-424`、`engine/sycl/src/core/verify.cpp:253-263`、`engine/src/core/arch_defaults.cpp:64-105,302-310`）。

## 値と判定

エンジンは `std::getenv` で値を取得し、文字列全体の parse や比較はせず `v[0] != '0'` だけで判定する。環境変数が未設定なら build macro に応じた既定値を使う。空文字は「設定あり」だが、実行時判定では先頭文字が `'0'` でないため ON になる。文字列の後続部分、大文字小文字、数値としての妥当性、空白は検査しない（CUDA/HIP: `engine/src/core/verify.cpp:415-424`、SYCL: `engine/sycl/src/core/verify.cpp:253-263`）。

| 条件 | unset | ON になる例 | OFF になる例 |
| --- | --- | --- | --- |
| CUDA build | ON | `1`, `true`, 空文字, ` 0`, `00x` | `0`, `0anything`, `01` |
| HIP build | 原則 OFF。ただし起動時の既定表・セットアップが値を設定する場合は、その設定値を読む | `1`, `true`, 空文字, ` 0`, `00x` | `0`, `0anything`, `01` |
| SYCL build | ON（`STRATA_USE_HIP` が定義された共用実装では HIP の OFF 分岐） | `1`, `true`, 空文字, ` 0`, `00x` | `0`, `0anything`, `01` |

したがって `false` や `0.5` は OFF を意味せず、どちらも先頭が `0` でないので ON。`0anything` は先頭が `0` のため OFF。無効値エラーや数値の範囲チェックはない。アーキテクチャ既定値の適用側は値を parse せず、環境変数が存在するだけで利用者設定として扱うため、空文字や `0anything` も既定値によって上書きされない（`engine/src/core/arch_defaults.cpp:302-310`、`engine/src/core/nv_defaults.cpp:222-234`）。

## 有効になる条件

- 検証 window の層処理で shared expert が実行されること。CUDA/HIP は `sh_stream_on()` が真、profiler が OFF、専用 stream と fork/join event が作成済みなら `sh_fork` を有効にする。SYCL はこれらに加えて stepped 実行でなく、専用 queue が in-order queue と異なることが条件（`engine/src/core/verify.cpp:2617-2628`、`engine/sycl/src/core/verify.cpp:1563-1575`）。
- `STRATA_VERIFY_PROFILE` が設定されていると profiler が有効になり fork は抑止される（CUDA/HIP: `engine/src/core/verify.cpp:1262-1276,2621`、SYCL: `engine/sycl/src/core/verify.cpp:816,1567-1569`）。
- SYCL の stepped serve（`g_stepped`）では fork を使わない（`engine/sycl/src/core/verify.cpp:1567-1569`）。
- CUDA/HIP の stream または event 作成に失敗すると検証初期化が `verify: stream create failed` または `verify: event create failed` で失敗する。これは変数値の検証エラーではない（`engine/src/core/verify.cpp:1352-1362`）。
- HIP で unset のときは通常 OFF。gfx1151 の既定表は Linux で `STRATA_SH_STREAM=1` を加えるが、通常の Windows gfx1151 表では除外される。`STRATA_DEFAULTS=026` は旧表を返すため Windows の除外より先に戻り、SH stream を含む表になる。`STRATA_GFX1151_DEFAULTS` が先頭 `0` ならこの表全体を止める（`engine/src/core/arch_defaults.cpp:64-105`）。
- HIP の gfx1103 と gfx1150 は `terminal/setup.py` が用意する `GFX1103_SWITCHES` / `GFX1150_SWITCHES` に含まれ、対応する設定の `env` に `STRATA_SH_STREAM=1` を書く。エンジン単体の HIP 既定 OFF をこの明示設定が上書きする（`terminal/setup.py:4465-4485,7543-7547`）。
- CUDA は unset なら既定 ON。さらに sm_70 の CUDA 既定表にも `STRATA_SH_STREAM=1` があり、`STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026` でその表を止めた場合も、unset の実行時既定は CUDA の ON のまま（`engine/src/core/verify.cpp:417-422`、`engine/src/core/nv_defaults.cpp:136-153,222-234`）。
- CUDA/HIP の gfx1151 表や NVIDIA の既定表は環境変数が既に存在すると値を設定しないため、明示値が表より優先される（`engine/src/core/arch_defaults.cpp:302-310`、`engine/src/core/nv_defaults.cpp:222-234`）。
- Server は親プロセスの環境を引き継いだ後、設定ファイルの `env` を上書き適用して engine 子プロセスに渡す。したがって設定の `env` にある値は親環境の同名値に優先し、その後に engine がアーキテクチャ既定値を適用する（`terminal/serve/server.py:4007-4028`）。`STRATA_SH_STREAM` 専用の CLI 引数による別優先順位は見つからなかった。

## 実行時の詳細

CUDA/HIP の `sh_stream_on()` と SYCL の同名関数は関数内 `static const bool` で初回評価結果を cache する。通常はアーキテクチャ既定値が適用された後、最初の verify window の記録時に評価される（`engine/src/program/generate.cpp:4319-4320`、`engine/src/core/verify.cpp:415-424,1546-1548`、`engine/sycl/src/core/verify.cpp:253-263`）。同一プロセスで後から環境を書き換えても、この cache を経由する判定には反映されない。

fork が有効な場合、通常 stream の処理を event で区切り、shared expert の gate/up/down と必要な変換を専用 stream に投入する。shared expert の完了 event を通常 stream が待ってから後続の combine に進む。fork が無効なら同じ計算を通常 stream に投入する（`engine/src/core/verify.cpp:2621-2628,2735-2758,2939-2943`、`engine/sycl/src/core/verify.cpp:1567-1575,1653-1677,1803-1809`）。

CUDA の all-resident / partial-residency や CPU expert の有無は fork 自体の有効条件ではない。ただし CPU expert がある通常の window では `STRATA_SH_FORK_LATE`（未設定または先頭が `0` 以外）により shared expert の fork を routed expert の doorbell 公開後へ遅らせる。all-resident の場合は遅延しない（`engine/src/core/verify.cpp:2617-2628,2716-2720`）。また CUDA の L2 prefetch が有効な経路では同じ専用 stream/event を使って次層の重みを先読みする条件にも `sh_stream_on()` が使われる（`engine/src/core/verify.cpp:2838-2845,2897-2906`）。

## ログと測定値

CUDA の gfx1151、HIP の gfx1151 などで既定表が新しい値を設定したときは、起動時に `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...` の一覧に `SH_STREAM` が出る。sm_70 の NVIDIA 既定表も同様に設定した switch 名を stderr に列挙する。既に環境変数が設定済みならその項目は一覧に含まれない（`engine/src/core/arch_defaults.cpp:302-310,397-404`、`engine/src/core/nv_defaults.cpp:222-255`）。

verify の dispatch 統計を出す場合、各 window に `win df_branch=%ld sh_stream=%ld prof=%ld` を記録し、`sh_stream` に cache 済み判定の `0` / `1` を出す。dispatch 統計は `STRATA_DISPATCH_STATS=0` で停止でき、レポートは `STRATA_DISPATCH_REPORT=<path>` または CLI の `--stats` で取得する（`engine/src/core/verify.cpp:1546-1548`、`engine/include/strata/core/dispatch_stats.hpp:9-12,107-120`）。

`terminal/serve/server_parts/engines.py` は Windows で HIP を使い、設定 env の値を空・`0` 以外（Python の `strip()` 後）にして `--kv-resident` も指定している場合、次の警告を出す。警告は拒否や値の削除をせず、そのまま engine に環境を渡す（`terminal/serve/server.py:4027-4028,4054-4058`、`terminal/serve/server_parts/engines.py:1091-1102`）。

```text
[strata] WARNING: STRATA_SH_STREAM=1 with --kv-resident (KV streaming) failed on the first request on one Windows RX 6000 PC ("verify: unspecified launch failure", #3895). If the engine stops that way, take STRATA_SH_STREAM out of the config's env (AMD runs without it by default) or run without --kv-resident, and tell us the card and the driver.
```

警告側は空白を `strip()` して比較する一方、engine は先頭文字だけを比較するため、たとえば値 `" 0"` は警告上は OFF 扱いでも engine では ON になる。

`terminal/tools/calibrate.py` は HIP で `STRATA_SH_STREAM=0` と `=1` を engine 再起動ごとに測り、既定の `0` を 3% 超えて上回った場合だけ `=1` を設定に残す。Windows で `--kv-resident` の組み合わせは測定をスキップする（`terminal/tools/calibrate.py:21-25,431-454,464-468`）。これらは calibrator の条件であり、エンジン自体が性能向上を保証するものではない。

## 根拠

- `engine/src/core/verify.cpp:405-424` — CUDA/HIP の用途、値の判定、既定値、初回 cache。
- `engine/src/core/verify.cpp:1262-1276,1352-1362,2615-2628,2716-2720,2735-2758,2838-2845,2897-2906,2939-2943` — profiler 抑止、stream/event の初期化、fork と join、関連する CUDA 経路。
- `engine/sycl/src/core/verify.cpp:245-263,816,1561-1575,1638-1642,1653-1677,1803-1809` — SYCL の値判定、 stepped 条件、queue と barrier。
- `engine/src/core/arch_defaults.cpp:28-29,64-105,218-223,302-310,397-404` — gfx1151 の platform 差、明示値優先、起動ログ。
- `engine/src/core/nv_defaults.cpp:136-153,222-255` — sm_70 既定値と適用ログ。
- `engine/src/program/generate.cpp:4319-4320` — GPU 検出後の arch defaults 適用時期。
- `terminal/setup.py:4465-4485,7543-7547` — gfx1103/gfx1150 設定への値の登録。
- `terminal/serve/server.py:4007-4028,4054-4058`、`terminal/serve/server_parts/engines.py:1091-1102` — 子プロセスへの環境引き渡しと Windows HIP の警告。
- `terminal/tools/calibrate.py:21-25,431-454,464-468` — HIP の校正経路。
- `engine/include/strata/core/dispatch_stats.hpp:9-12,107-120` — 統計の出力条件。
- `docs/DETAILS.md:1480-1488` — sm_70 表に `STRATA_SH_STREAM=1` が載る。現行ソースの `nv_defaults.cpp` と一致。
