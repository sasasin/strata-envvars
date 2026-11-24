# `INK_SY_TIMING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Intel SYCL Inkling runner の decode step ごとに、host が処理を submit するまでの時間と、最後の queue wait を含む時間を集計して stderr に出す診断用スイッチです。`INK_SY_TIMING` 自体は演算や token 選択を変更せず、フェーズ間の追加 wait も行いません。計測状態は `ink_sycl::sy_prof()` が初回呼び出し時に作る `static SyProf` に保持されます。`INK_SY_PROF` が `1` または `2` で有効な場合は、この変数が未設定でも同じ集計が有効になります（`engine/src/inkling2/sycl/ink_sy_common.h:195-223`）。

## 値と判定

`std::getenv` の結果の先頭 1 文字だけを比較します。文字列全体の parse、数値変換、空白除去、大文字小文字変換はありません。次の表の timing は、別途 `INK_SY_PROF` が有効でない場合の判定です（`engine/src/inkling2/sycl/ink_sy_common.h:212-221`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| すべての SYCL build | timing 無効 | 先頭文字が `1`（例: `1`, `1anything`） | 空文字、`0`、`0anything`、`true`、`TRUE`、先頭が空白の ` 1` など |

`INK_SY_PROF` の先頭文字が `1` または `2` の場合は、同じ `SyProf` 初期化で `timing` も有効になります。このため `INK_SY_TIMING=0` や未設定でも timing 集計は有効です。無効な値を受け取ったときの警告や error fallback はありません（`engine/src/inkling2/sycl/ink_sy_common.h:214-220`）。

## 有効になる条件

- `STRATA_ENABLE_SYCL=ON` の別 backend build が必要です。トップレベル CMake は既定でこの option を `OFF` にし、有効時は CUDA/HIP と同時指定できず SYCL のサブプロジェクトへ進みます（`engine/CMakeLists.txt:23-32`）。
- SYCL Inkling runner の `forward_batch` が呼ばれ、その呼び出しの `M` が `1` である必要があります。`M <= 0` または `M > max_batch` は計測開始前に `false` を返します（`engine/src/inkling2/sycl/ink_sy_runner.h:467-475`）。
- `INK_SY_PROF` が `1` または `2` なら timing はそちらでも有効になります。`INK_SY_PROF=2` はフェーズごとの細粒度計測も有効にしますが、`INK_SY_TIMING` だけでは有効にしません（`engine/src/inkling2/sycl/ink_sy_common.h:214-220, 240-241`）。
- この値を読む箇所に CLI 引数・設定ファイルによる上書きはありません。読み取り箇所は SYCL 共通ヘッダー内の `std::getenv` です（`engine/src/inkling2/sycl/ink_sy_common.h:218-220`）。

## 実行時の詳細

`sy_prof_begin(M)` は `M == 1` かつ `p.on || p.timing` のときだけ step を計測対象にし、開始時刻を記録します。単独の `INK_SY_TIMING` では `p.on` が false のため、`begin` やフェーズ mark に追加の `wait()` は行われません。runner は全 enqueue 後、head mark の直後に submit 時刻を記録し、通常の `wait()` を実行してから end 時刻を記録します。したがって `host-submit` は begin から wait 直前まで、`total` は wait 完了までの区間を示します（`engine/src/inkling2/sycl/ink_sy_common.h:224-254`; `engine/src/inkling2/sycl/ink_sy_runner.h:935-940`）。

集計はプロセス内で累積され、計測 step が 64 回に達するごとに stderr へ平均値を出力します。`M != 1` の batch は step 数に入りません。最後に 64 回へ満たない分を flush する処理はこの実装にはありません。環境変数は `sy_prof()` の関数内 static 初期化で一度だけ読み取られるため、初回呼び出し後にプロセス環境を変更しても設定は反映されません（`engine/src/inkling2/sycl/ink_sy_common.h:212-223, 248-275`）。

## ログと測定値

64 計測 step ごとに、次の形式の集計行を stderr に出します。`host-submit` と `total` はミリ秒単位の step 平均です。単独の `INK_SY_TIMING` では phase 別の値は付かず、通常の newline で行を終えます（`engine/src/inkling2/sycl/ink_sy_common.h:255-275`）。

```text
[ink_sy_prof] steps=<累積step数> host-submit=<平均ms> ms total=<平均ms> ms per step
```

この環境変数について、参照したソースと Strata の資料内に特定 hardware・model 条件付きの測定値は見つかりませんでした。エラー文や無効値の警告も実装されていません。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_common.h:195-223` — profiler 状態、環境変数判定、static 初期化。
- `engine/src/inkling2/sycl/ink_sy_common.h:224-275` — 計測対象条件、集計、stderr 出力周期と書式。
- `engine/src/inkling2/sycl/ink_sy_runner.h:467-475, 935-940` — runner 呼び出しと submit/queue wait を含む測定区間。
- `engine/CMakeLists.txt:23-32` — SYCL backend の build 条件。
