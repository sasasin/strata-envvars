# `STRATA_Q80_ROWS1`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA native MMVQ の Q8_0 multi-column カーネルで、sm_120（Compute Capability 12.0）に限り、形状条件を満たすときに 2 出力行ずつ処理する経路から 1 出力行ずつ処理する経路へ切り替える opt-in です。切替先は `native_mmvq_multi_kernel<..., 1, ...>` で、カーネル内の行ごとの partial sum と reduction を使います。`native_mmvq` は dense Q8_0 の通常経路を `native_q8_0_mmvq` に渡します（`engine/src/kernels/cuda/native_mmvq.cu:1357-1365, 1389-1405, 1677-1710, 3800-3806`）。

`q8_0_rows1` はこの値を読むものの、値が実際の行数選択に使われるのは CUDA sm_120 だけです。sm_86 は `n_out >= 2048` なら同じ 1 行条件がコード上で常に成立し、gfx12 HIP は `n_in <= 4096 && n_out >= 4096` で成立します。どちらも `STRATA_Q80_ROWS1` の値では切り替わりません。sm_70 もこの変数では切り替わらず、別の `STRATA_NO_MMVQ_ROWS2` 判定が全アーキテクチャ共通の 1 行指定を担います（同 `native_mmvq.cu:1366-1386, 1394-1405, 1696-1705`）。

## 値と判定

カーネル内の関数 static 初期化で `std::getenv` を一度呼び、文字列の先頭文字だけを判定します。文字列全体の parse、数値変換、大文字小文字変換はありません（`engine/src/kernels/cuda/native_mmvq.cu:1400-1403`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| sm_120 の Q8_0 判定で `STRATA_Q80_ROWS1` を評価 | 無効 | 空でなく、先頭文字が `0` 以外（`1`, `true`, `-1`, ` 1`, `0anything` 以外の文字列） | 未設定、空文字、`0`, `0anything` |
| NVIDIA 自動既定値テーブル | 対象カード・他条件に応じて `1` を設定 | 利用者が事前設定した値は値にかかわらず保持 | sm_120 では `STRATA_SM120_PERF` が `0` で始まる場合、または `STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` の場合はテーブル自体を使わない |

テーブルで既定値を追加する際の「未設定」は `getenv(...) == nullptr` です。したがって明示的な空文字も利用者設定として保持され、その後カーネルでは無効扱いになります。sm_120 既定値テーブルは `STRATA_Q80_ROWS1=1` を含み、テーブルの適用時に利用者が未設定なら設定します（`engine/src/core/nv_defaults.cpp:104-117, 222-234`）。

## 有効になる条件

- 呼び出しが Q8_0 の `SmallTraits<Q80Block, 8>` である必要があります。他の trait では `q8_0_rows1` は false を返します（`engine/src/kernels/cuda/native_mmvq.cu:1389-1393`）。
- `launch_multi_n` が exact multi-column 経路に進む必要があります。`g_multi_exact` が false の場合は 2 行カーネルを起動して先に return するため、この判定には到達しません（同 `native_mmvq.cu:1685-1691`）。
- sm_120 ではデバイス判定が成功して Compute Capability 12.0 となり、かつ変数が有効である必要があります。`dev_class` はデバイスごとの分類を static 配列に cache します（同 `native_mmvq.cu:1366-1387`）。
- 入力幅は `n_in / F::DIV >= F::BPI` を満たす必要があります。Q8_0 のコメントで示す条件は `n_in / 32 >= 4` です。満たさない場合は 2 行カーネルへ進みます（同 `native_mmvq.cu:1363-1365, 1702-1710`）。
- `STRATA_NO_MMVQ_ROWS2` が空でなく先頭文字 `0` 以外なら、その共通指定だけで 1 行条件が成立し、C++ の `||` 短絡評価により `q8_0_rows1`（したがって対象変数の読み取り）を呼ばないことがあります。未設定・空・先頭 `0` は共通指定を無効にします（同 `native_mmvq.cu:1394-1405, 1696-1705`）。
- 通常起動時の NVIDIA 既定値注入は、全可視 GPU の Compute Capability が同一の場合に実行されます。混在構成では `apply_nv_defaults` を呼ばないため、このテーブルから `STRATA_Q80_ROWS1` は設定されません。sm_120 が混在する場合に別処理で設定される `STRATA_SM120_PERF=0` はアーキテクチャ既定値を止めますが、利用者が明示した `STRATA_Q80_ROWS1` をカーネルが読むこと自体は止めません（`engine/src/program/generate.cpp:4416-4464`）。
- 既定値テーブルが sm_120 で `STRATA_Q80_ROWS1=1` を設定するのは、CUDA エンジンの起動経路で、同一 Compute Capability の GPU 群に対して `STRATA_SM120_PERF` が先頭 `0` でなく、`STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` ではない場合です。`nv_default_env` はこの2条件で sm_120 の表を空にします（`engine/src/program/generate.cpp:4416-4444`, `engine/src/core/nv_defaults.cpp:104-117, 222-234`; `engine/include/strata/core/defaults_026.hpp:21-29`）。

## 実行時の詳細

`generate.cpp` は CUDA 系起動時にデバイス数と各デバイスの capability を調べ、全デバイスが同一 capability なら `apply_nv_defaults` を呼びます。これは engine のスイッチ読み取り前に行われます。既定値適用は `getenv` で既存値の有無だけを確認し、未設定なら `setenv(..., overwrite=0)`（Windows は `_putenv_s`）で値を設定します（`engine/src/program/generate.cpp:4416-4444`, `engine/src/core/nv_defaults.cpp:222-237`）。

対象変数の実値は `q8_0_rows1` の関数 static bool に最初に初期化されるときに cache されます。初期化は Q8_0 trait の呼び出しで、かつ共通 `rows1` 条件が true で短絡しないときに限り発生します。それ以降に環境を変更しても、この値の判定には反映されません。適用可能な 1 行条件が成立すれば `ROWS=1` のカーネルを起動して return し、成立しなければ `ROWS=2` のカーネルを起動します（`engine/src/kernels/cuda/native_mmvq.cu:1389-1405, 1696-1710`）。

## ログと測定値

既定値テーブルが一つ以上の値を追加すると stderr に `strata: sm_120 (Blackwell): ... speed switches on by default ...` 形式の行を出し、追加したキー名一覧に `Q80_ROWS1` が含まれます。すでに利用者が `STRATA_Q80_ROWS1` を設定している場合はそのキーを追加一覧に含めません。対象変数のカーネル内判定自体はログを出しません（`engine/src/core/nv_defaults.cpp:227-253`）。

カーネルコメントは RTX 5090 / sm_120 の `q8_gemv_bench` の 2〜6 列表に測定結果があると述べていますが、この文書ではソースコメント以上の速度値や一般化を行いません（`engine/src/kernels/cuda/native_mmvq.cu:1363-1365`）。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:1357-1387` — 行数選択の背景と GPU 分類。
- `engine/src/kernels/cuda/native_mmvq.cu:1389-1405` — 対象変数の読み取り・値判定・アーキテクチャ別条件。
- `engine/src/kernels/cuda/native_mmvq.cu:1685-1710` — exact 経路、共通行指定、shape gate、1/2 行 kernel dispatch。
- `engine/src/core/nv_defaults.cpp:104-117, 222-253` — sm_120 既定値の条件、既存値優先、環境への設定と stderr 行。
- `engine/src/program/generate.cpp:4416-4464` — 起動時の適用条件、混在 GPU の経路。

索引外の補足: `engine/src/core/nv_defaults.cpp` は sm_86 と sm_70 の既定値リストにもこの名前を含めます。また `docs/NVIDIA_V100.md:55-57` は sm_70 の既定一覧に記載します。しかし現行 `q8_0_rows1` は sm_70 を有効クラスにせず、sm_86 でも対象変数を使わずに `n_out >= 2048` を判定します。sm_70 の 1 行指定は別の `STRATA_NO_MMVQ_ROWS2` によります（`engine/src/core/nv_defaults.cpp:41-72, 136-163`; `engine/src/kernels/cuda/native_mmvq.cu:1366-1405, 1696-1705`）。
