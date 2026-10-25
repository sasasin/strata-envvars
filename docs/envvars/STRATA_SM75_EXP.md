# `STRATA_SM75_EXP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の native expert grouped kernel が、Turing（compute capability 7.5）で expert layout mode 4 を使うかを選びます。未設定なら `STRATA_SM75_PERF` に従い、この変数を設定すると Turing 上でその既定を上書きします。Turing 以外のデバイスでは、この変数を設定しても mode 4 は選ばれません。

## 値と判定

値は `std::atoi` で整数変換され、文字列全体の妥当性検査はありません。

| `STRATA_SM75_EXP` | Turing での扱い |
|---|---|
| 未設定 | `STRATA_SM75_PERF` の値に従う。`STRATA_SM75_PERF` も未設定なら OFF |
| 設定され、`atoi(value) == 0` | OFF。例: `0`、空文字、`false`、`x` |
| 設定され、`atoi(value) != 0` | ON。例: `1`、`-1`、`1junk` |

したがって、文字列が厳密に `1` かどうかではなく、`atoi` が先頭から読み取った整数が 0 かどうかで判定します。空白や符号などの扱いも `atoi` に従います。`STRATA_SM75_PERF` 側も `atoi(value) != 0` で判定されます。根拠: `include/strata/core/sm75_series.hpp:24-44`。

## 有効になる条件

- CUDA の `iq_kernels.cu` で `STRATA_EXP_LAYOUTS` が有効であること。同ファイルでは CUDA コンパイル（`!defined(__HIPCC__)`）時に有効です。HIP GFX906 では `exp_mode()` が別の経路を使い、`STRATA_SM75_EXP` は参照しません (`src/kernels/cuda/iq_kernels.cu:4361-4376,5124-5132`)。
- 実行デバイスが compute capability 7.5 であること。実装は `strata::is_sm75()` で判定し、`STRATA_EMULATE_CC=75` の仮想 capability もこの判定に含まれます。別の capability では設定値にかかわらず OFF です (`include/strata/core/sm75_series.hpp:33-43`)。
- grouped native expert の CUDA 実行経路であること。さらに CUDA では `grid_groups > 0 && grid_groups < cap_groups` の呼び出しは `exp_mode()` を使わず mode 0 に固定します (`src/kernels/cuda/iq_kernels.cu:5119-5132`)。

この設定で選ばれる mode 4 は gate/up の expert layout に使われます。down projection は、Turing で `cap_groups > 30` の場合 `sm75_down_em()` が mode 4 を mode 0 に戻します。ただし、`STRATA_EXP_MODE` が設定されている場合、またはベンチ用 `native_expert_set_mode()` で明示 mode が与えられている場合は、この down 側の戻し処理を行いません (`src/kernels/cuda/iq_kernels.cu:4990-5000,5237-5248`)。

## 実行時の詳細

`exp_mode()` はデバイスごとの mode を `per_dev[64]` に初回計算時に保存します。その計算で `STRATA_SM75_EXP` を読み、`STRATA_SM75_PERF` が未設定時の既定として有効か、あるいは明示設定で上書きされたかを決めます。`sm75_series()` も `static const bool` で最初の評価結果を保存します。そのため、これらの値がキャッシュされた後にプロセス環境を書き換えても、そのデバイスの mode 判定には反映されません (`include/strata/core/sm75_series.hpp:24-44`, `src/kernels/cuda/iq_kernels.cu:4951-4986`)。

選択された mode は gate/up と down の kernel 選択に渡され、down では mode 4 用の AMD layout kernel、または通常の CUDA kernel が起動されます。`STRATA_SM75_EXP` 自体がログを出す処理はありません (`src/kernels/cuda/iq_kernels.cu:5133-5148,5237-5264`)。

## 文書との照合

`docs/DETAILS.md:2526-2539` は Turing 向け kernel 群を opt-in とし、`STRATA_SM75_PERF=1` で有効化、個別変数で `=0` / `=1` の上書きができると説明しています。`STRATA_SM75_EXP` の「expert layout mode 4」という用途と、ソースの `sm75_switch()` による既定追従・個別上書きは一致します。同資料が引用する RTX 2080 Ti の測定値は同資料の記載であり、本調査では再測定していません。

## 根拠

- `include/strata/core/sm75_series.hpp:24-44` — `STRATA_SM75_PERF` の読み取り、Turing 判定、個別スイッチの値解釈。
- `src/kernels/cuda/iq_kernels.cu:4361-4376` — CUDA/HIP の layout compile 条件と既定 mode。
- `src/kernels/cuda/iq_kernels.cu:4951-5003` — mode 決定、デバイス単位キャッシュ、Turing の down projection fallback。
- `src/kernels/cuda/iq_kernels.cu:5119-5134,5237-5264` — grouped expert の mode 適用と kernel 分岐。
- `docs/DETAILS.md:2526-2539` — Turing kernel 系列と個別スイッチの説明。
