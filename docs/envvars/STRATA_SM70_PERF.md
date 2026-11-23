# `STRATA_SM70_PERF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の compute capability `7.0`（sm_70 / Volta）向け既定値を有効にするスイッチです。CUDA の全可視 GPU が同じ compute capability のとき、Strata は未設定の環境変数 21 個を設定して、対応する sm_70 向け経路を既定で選べるようにします。`STRATA_SM70_PERF=0` または `STRATA_DEFAULTS` が v0.2.6 を示す場合、この一括設定を行いません。値が個別スイッチの設定を上書きするものではなく、個別スイッチに既に値があればその値を残します。`engine/src/core/nv_defaults.cpp:136-163,222-234`。

この変数は CUDA の sm_70 向け設定です。設定一括処理は CUDA のみの `generate` 初期化経路にあり、HIP と Metal では呼び出されません。sm_70 用ビルドは `STRATA_EXPERIMENTAL_SM60` を有効にした CUDA ビルドが対象です。`engine/src/program/generate.cpp:4416-4444`、`engine/cmake/backends/cuda.cmake:47-79`、`engine/cmake/strata_gpu_engine.cmake:82-95`。

`docs/SETTINGS.md:443` の一覧は対象を「NVIDIA and AMD」としていますが、この commit の設定呼び出しは HIP を明示的に除外しています。したがって、少なくともここで確認した一括設定と QSA の直接参照は AMD/HIP の挙動を裏付けません。`engine/src/program/generate.cpp:4416-4444`、`engine/src/kernels/cuda/qsa_select.cu:2155-2161`。

QSA の CUDA カーネルにも直接の参照があります。個別設定 `STRATA_SCORES_THREAD`、`STRATA_SCORES_HALVE`、`STRATA_TOPK_SAMPLE` が未設定の場合、それぞれの自動選択で sm_70 を既定 ON とする判定にこの変数を使います。これらは全 GPU が同一世代でないため一括設定が行われない構成でも、sm_70 デバイス上の個別経路に影響し得ます。`engine/src/kernels/cuda/qsa_select.cu:2155-2176,2179-2191,2997-3012`。

## 値と判定

`engine/src/core/nv_defaults.cpp` の `off()` は `std::getenv()` の結果が存在し、先頭文字が `'0'` のときだけ無効とします。QSA の `sm70_default_on()` も同じ先頭文字判定です。数値変換や文字列全体の真偽値 parse はしません。`engine/src/core/nv_defaults.cpp:14-18,136-140`、`engine/src/kernels/cuda/qsa_select.cu:2155-2161`。

| 条件 | 未設定 | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA sm_70 の既定値テーブル | `STRATA_DEFAULTS` が v0.2.6 を表さなければ有効 | 先頭が `0` 以外。例: `1`、`true`、` 0` | 先頭が `0`。例: `0`、`0anything`、`01` |
| QSA の個別自動選択 | `STRATA_DEFAULTS` が v0.2.6 を表さなければ sm_70 で有効 | 先頭が `0` 以外。例: `1`、`true`、空文字 | 先頭が `0`。例: `0`、`0anything` |

空文字は環境変数として存在しますが先頭文字が `\0` なので、`STRATA_SM70_PERF` 自体は無効になりません。先頭の空白は読み飛ばされず、` 0` は有効扱いです。大文字小文字や文字列全体の妥当性確認もありません。`off()` は `v[0] == '0'`、QSA 側も `e[0] != '0'` だけを判定します。`engine/src/core/nv_defaults.cpp:15-18`、`engine/src/kernels/cuda/qsa_select.cu:2156-2160`。

関連する `STRATA_DEFAULTS` は別判定です。`STRATA_DEFAULTS` は `026`、`0.2.6`、`v0.2.6` のいずれかと文字列全体が一致した場合に限って有効で、unset・空文字・`0`・`027` は該当しません。最初の呼び出し時に `static` へ一度だけ保存されます。`engine/include/strata/core/defaults_026.hpp:21-30`。

## 有効になる条件

- 一括設定には CUDA デバイスが 1 台以上あり、全可視 CUDA デバイスの compute capability が同じであることが必要です。異なる世代が混在する場合、`apply_nv_defaults()` は呼ばれません。`STRATA_SM70_PERF` が未設定または有効値でも、この場合 21 個の一括設定は行われません。`engine/src/program/generate.cpp:4422-4447`。
- 一括設定対象は compute capability `7.0` のみで、`STRATA_DEFAULTS` が v0.2.6 を示す場合は対象外です。`engine/src/core/nv_defaults.cpp:136-163`。
- 個別スイッチの環境変数がすでに設定されていると、値が空でも `apply_nv_defaults()` はその変数を変更しません。したがって、グローバルスイッチが有効でも個別スイッチで上書きできます。無効値かどうかは各個別スイッチ側の判定に従います。`engine/src/core/nv_defaults.cpp:227-234`。
- `STRATA_DEFAULTS` が v0.2.6 を示す場合、sm_70 の一括既定値と QSA の自動 sm_70 既定値を無効にします。ただし一括設定を止めるだけなので、個別スイッチが明示されている場合の扱いはその個別スイッチの判定によります。`engine/include/strata/core/defaults_026.hpp:21-29`、`engine/src/core/nv_defaults.cpp:139-140`、`engine/src/kernels/cuda/qsa_select.cu:2155-2161`。
- 一括設定の有効条件は `generate` の CUDA 経路に限られます。HIP / Metal はこの処理の `#if` 条件から除外されています。`engine/src/program/generate.cpp:4416-4444`。
- sm_70 用 CUDA 実行ファイルは通常の既定アーキテクチャ構成ではなく、`STRATA_EXPERIMENTAL_SM60=ON` を指定する実験的ビルドで用意します。`engine/cmake/backends/cuda.cmake:47-79`。

## 実行時の詳細

`generate.cpp` は CUDA デバイス数と各デバイスの compute capability を調べ、同一世代であれば `apply_nv_defaults()` を呼びます。そこで `nv_default_env()` が sm_70 表を選び、`STRATA_SM70_PERF` の先頭が `0` か、`STRATA_DEFAULTS` が v0.2.6 かを判定します。どちらでもなければ下記 21 個の環境変数について、未設定のものだけをプロセス環境に設定します。設定値は `setenv(..., 0)`（Windows は `_putenv_s`）であり、すでに設定済みの値は維持されます。`engine/src/program/generate.cpp:4422-4444`、`engine/src/core/nv_defaults.cpp:136-163,222-237`。

既定値として設定する変数は `STRATA_ADAPT_OVERLAP=1`、`STRATA_SM70_TABLE=1`、`STRATA_B6_MMVQ_ROWS=1`、`STRATA_TSUM=1`、`STRATA_SMALL_UNR=3`、`STRATA_GR_NORM_FAST=1`、`STRATA_SIDE_MIXER=2`、`STRATA_ARGMAX_ROWS_SM70=1`、`STRATA_LFUSE=1`、`STRATA_GDN_SPLIT=1`、`STRATA_SH_STREAM=1`、`STRATA_Q80_ROWS1=1`、`STRATA_NO_MMVQ_ROWS2=1`、`STRATA_CPU_IQ_ALL_EXACT1=1`、`STRATA_GR_Q8_DOWN_MODE=2`、`STRATA_GR_Q8_UP_COLS=16`、`STRATA_GR_Q8_UP_MODE=2`、`STRATA_SCORES_HALVE=1`、`STRATA_SCORES_THREAD=1`、`STRATA_TOPK_SAMPLE=1`、`STRATA_SELECT_LONG=1` です。`engine/src/core/nv_defaults.cpp:141-163`。

QSA の `sm70_default_on()` は `STRATA_SM70_PERF` と `STRATA_DEFAULTS` を関数内 `static` に保存し、初回呼び出し時に一度読みます。`STRATA_SCORES_THREAD`、`STRATA_SCORES_HALVE`、`STRATA_TOPK_SAMPLE` はそれぞれ別の `static` 値を持ち、個別変数が設定されていればその数値判定を優先します。未設定時は現在の CUDA デバイスの compute capability を確認し、sm_70 または sm_75 の既定条件を使います。プロセス中に環境変数を変更しても、これらの static 判定が初期化済みなら反映されません。`engine/src/kernels/cuda/qsa_select.cu:2155-2176,2179-2191,2997-3012`。

ここでの処理は環境変数を設定し、後続の個別機能が各スイッチを読めるようにするものです。各スイッチの実際の適用条件はそれぞれの実装に依存し、この変数だけで 21 機能の実行や性能向上を保証するものではありません。コード中の説明と測定条件は `docs/NVIDIA_V100.md:53-59,83-90` に記載されています。測定をこの調査で再実行していません。

## ログと測定値

`apply_nv_defaults()` が少なくとも 1 個の個別スイッチを新規設定した場合だけ、stderr に次の形式で 1 行を出します（sm_70 の場合）。末尾には実際に設定したスイッチ名が空白区切りで続きます。21 個すべてが未設定なら `21` 個が列挙されます。

```text
strata: sm_70 (Volta): 21 exact speed switches on by default (STRATA_SM70_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): ...
```

個別スイッチがすべて事前設定済みの場合、またはグローバルスイッチ / `STRATA_DEFAULTS` により既定テーブルが空の場合、この関数からこの行は出ません。実装の書式文字列は `engine/src/core/nv_defaults.cpp:237-253`。

`docs/NVIDIA_V100.md` は 21 スイッチを bit-exact の既定値として記載し、管理された dual V100-SXM2 測定の条件を記しています。これは文書上の測定記録であり、この環境変数単体の実行時性能を示すものではありません。`docs/NVIDIA_V100.md:53-59,83-90`。

## 根拠

- `engine/src/core/nv_defaults.cpp:14-18,136-163,222-253` — 値判定、sm_70 表、個別環境変数への設定、stderr 出力。
- `engine/src/program/generate.cpp:4416-4447` — CUDA 経路、全デバイス同一 compute capability の条件と呼び出し箇所。
- `engine/include/strata/core/defaults_026.hpp:21-30` — `STRATA_DEFAULTS` の受理文字列と一度限りの読み取り。
- `engine/src/kernels/cuda/qsa_select.cu:2155-2176,2179-2191,2997-3012` — QSA の直接読み取りと関連する個別既定判定。
- `engine/cmake/backends/cuda.cmake:47-79`、`engine/cmake/strata_gpu_engine.cmake:82-95` — 実験的 sm_70 CUDA ビルド条件と CUDA カーネルの構成。
- `docs/NVIDIA_V100.md:53-59,83-90`、`docs/DETAILS.md:1456-1466` — ソースと照合した既定スイッチ・測定記録。
