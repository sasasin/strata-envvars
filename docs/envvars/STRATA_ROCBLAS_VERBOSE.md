# `STRATA_ROCBLAS_VERBOSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

rocBLAS の調整済み GEMM 解を選ぶときの診断ログを有効にする。解の選択や計算経路そのものはこの変数では変更しない。Strata が環境変数を読み、選択内容、拒否時の一時的な fallback、および state の終了時集計を stderr に出す（`engine/src/prefill/gemm.cu:542-560,626-675`）。

## 値と判定

`std::getenv` の非 null 判定のみで、値の parse や文字列比較はしない。unset は無効、設定されていれば空文字を含めて有効である。したがって `0`、`false`、`anything` も有効であり、値の形式・大小文字・数値境界は判定に関係しない。判定は shape 選択時と拒否ログ時に都度行われ、終了時集計の条件も state の破棄時に都度読む。値のキャッシュはない（同ファイル `:554-558,633-647,661-674`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Strata が rocBLAS state を作成した経路 | ログ抑制 | 空文字、`0`、`1`、`false`、任意の文字列 | なし（設定値はすべて有効） |

## 有効になる条件

- HIP backend でビルドされ、rocBLAS が見つかって `STRATA_ROCBLAS_AVAILABLE` が定義されていること（`engine/cmake/hip_backend.cmake:86-99`; `engine/cmake/strata_gpu_engine.cmake:501-504`）。それ以外の build にはこの読み取りコードがない。
- 対象 GEMM の rocBLAS state が作成されていること。これは `STRATA_ROCBLAS_TUNING` が空でないパスを指し、handle・device 情報・表の読み込みに成功した場合に限る。unset / 空文字なら state は作られない（`engine/src/prefill/gemm.cu:563-565,567-603,796-798,876-878`）。表の読み込み失敗などでは rocBLAS の調整済み経路に入らず、verbose ログも出ない。
- 調整済み解を使うにはさらに FP16 in / FP16 out の prompt 経路に入り、shape が表の調整済み行に一致する必要がある。`f16_inplace` は HIP で `f16_io_` が有効かつ `beta == 0` の経路などから呼ばれる（同ファイル `:1318-1320,1460-1471`）。`f16_io_` は `prompt_f16()` のデバイス判定で設定され、`STRATA_HIP_PROMPT_F16` が別途この判定を上書きする（`engine/src/prefill/prefill.cpp:2724-2729`; `engine/src/prefill/gemm.cu:681-709`; `engine/include/strata/core/arch_defaults.hpp:79-90`）。
- 同じ `(T,N,K,ldy)` は state 内で cache されるため、選択ログはその shape の初回解決時だけ出る。表に matching row がない場合だけでなく、row はあっても tuned solution がない場合も default kernel を選び、ログ文言はどちらも `default kernel; no row for ...` となる（`engine/src/prefill/gemm.cu:546-552,632-649`）。

## 実行時の詳細

`Gemm` の初期化時に `STRATA_ROCBLAS_TUNING` による表の読み込みを試み、成功した場合は shape ごとの解を cache する。`STRATA_ROCBLAS_VERBOSE` はその後にログの有無だけを決め、table path、solution、GEMM の計算値やアルゴリズムを変えない。調整済み解が rocBLAS に拒否されると、その呼び出しは既定の GEMM に fallback し拒否回数を増やす。3 回目は verbose の設定に関係なく、その shape で以後既定 kernel を使う旨を stderr に記録する。最初の 2 回の拒否ログは、その時点で変数が設定されている場合だけ出る（`engine/src/prefill/gemm.cu:652-675`）。

変数は起動時に固定されず、shape 解決・拒否・state 破棄の各箇所で再読される。実行中に環境値を変更すれば以降の判定に反映されるが、既に cache 済みの shape の選択ログは再出力されない。CLI 引数や他の環境変数による verbose 設定の優先順位はなく、`STRATA_ROCBLAS_TUNING` と prompt FP16 条件は verbose の有効化ではなく、ログ対象となる処理が存在するための条件である。

## ログと測定値

ログは stderr に出る。shape 初回選択時の文言は `prefill gemm: rocBLAS solution ...` または `prefill gemm: rocBLAS default kernel; no row for ...`。後者の文言は表に row があるが tuned solution がない場合にも使われる。調整済み解の初回・2 回目の拒否は設定時に `...; the default kernel this time` を出し、3 回目は常に `... three times; the default kernel runs for this shape` を出す。state の破棄時に変数が設定されていれば `prefill gemm: rocBLAS tuning summary tuned_launches=... fallbacks=...` を出す。集計の `fallbacks` は rocBLAS が調整済み解を拒否した回数であり、表に行がなく最初から既定 kernel を選んだ回数ではない（`engine/src/prefill/gemm.cu:554-558,640-647,661-673`）。この変数に関する性能測定値は該当なし。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:1981-1984`。
- 環境値の読み取りとログ分岐: `engine/src/prefill/gemm.cu:554-558,640-647,661-674`。
- rocBLAS state と tuning 表の条件: `engine/src/prefill/gemm.cu:563-623,796-798,876-878`。
- rocBLAS build 条件: `engine/cmake/hip_backend.cmake:86-99`, `engine/cmake/strata_gpu_engine.cmake:501-504`。
- prompt 経路・FP16 条件: `engine/src/prefill/gemm.cu:1318-1320,1460-1474`, `engine/src/prefill/prefill.cpp:2724-2729`, `engine/include/strata/core/arch_defaults.hpp:79-90`。
