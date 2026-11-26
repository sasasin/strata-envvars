# `STRATA_IQ3XXS_GU_ROW_REUSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL grouped expert の IQ3_XXS gate/up 計算で、通常の grouped kernel の代わりに 2 行をまとめて計算し、行データの再利用を行う kernel を選ぶ制御です。IQ3_XXS は `TG == 18` としてこの分岐に入ります。選ばれる kernel は gate/up の浮動小数点出力を書きます。環境変数がモデル形式や expert の選択自体を変える処理はありません。読み取りと選択は `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5895-5909`、2 行の計算と出力先は同ファイル `:4374-4425` にあります。

この変数を読むコードは SYCL kernel のみです。CUDA/HIP 側の IQ3_XXS kernel に同名の読み取りはありません（候補名の全参照検索で確認）。

## 値と判定

読み取りは `bm_default_on(name, device)` に委譲されます。同 helper は `getenv` の結果が null でなく、かつ先頭文字が NUL でない場合に、先頭文字が `'0'` かどうかだけを判定します。文字列全体の parse、数値妥当性、大文字小文字、空白の除去は行いません。未設定または空文字なら Battlemage 判定に基づく既定値へ進みます（`engine/sycl/include/strata/sycl_queue.hpp:193-200`）。

| 条件 | unset | 設定時に reuse 判定が ON | 設定時に reuse 判定が OFF |
|---|---|---|---|
| SYCL grouped expert IQ3_XXS。通常の `STRATA_GRID_SLM=0` ビルド | Battlemage は ON、それ以外は OFF | 空でない値の先頭文字が `0` 以外（例: `1`, `true`, `false`, ` 1`, `2tail`） | 空でない値の先頭文字が `0`（例: `0`, `0anything`, `00`） |

空文字は unset と同じ既定判定です。したがって `false` は先頭文字が `f` のため ON、`0anything` は後続文字を読まず OFF です。明示値による helper の判定が ON でも、後述の Battlemage 条件などを満たさないと kernel は選ばれません。

## 有効になる条件

- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp` の `STRATA_GRID_SLM` が 0 でコンパイルされている必要があります。1 の場合は対象分岐が `#if !STRATA_GRID_SLM` で除外されます。同ファイルは未定義時に 0 とします（`:484-489`, `:5895-5910`）。
- grouped expert の gate/up が IQ3_XXS（`L.gu_type == 18`）として `launch_gu` へ到達する必要があります。形式別 dispatch は同ファイル `:7874-7878`、IQ3_XXS の型番号は `:1393` にあります。
- grouped lane 経路で 8 lanes/row（テンプレートの `LN == 8`）が選ばれる必要があります。lane 数は `STRATA_GU_LANES`、コンパイル時の `STRATA_EXPERT_LANES`（未定義時 8）で決まり、IQ split 形式では `STRATA_KQ_GU_LANES` が設定されていればそちらが使われます。受理される lane 値は 4, 8, 16, 32 で、不正値は compile-time default に戻ります（同ファイル `:1175-1180`, `:4478-4488`, `:4515-4518`, `:5940-5949`）。
- `STRATA_OLD_IQ_MMVQ` が有効でなく、`STRATA_EXPERT_SPLIT` が有効でないことが必要です。どちらかが有効ならこの reuse 分岐を通らず、旧 kernel または multi kernel 経路になります（同ファイル `:3931-3938`, `:5897-5908`, `:6053-6067`）。
- 実行 device は Battlemage でなければなりません。`bm_default_on` は明示値で helper 判定を上書きできますが、reuse 分岐には別途 `intel_gpu_gen(...) == Battlemage` の条件があります。したがって他世代の SYCL GPU で `=1` を指定してもこの kernel は選ばれません（同ファイル `:5897-5900`; helper は `engine/sycl/include/strata/sycl_queue.hpp:193-200`）。
- 通常の expert grouped dispatch で gate/up を実行する必要があります。`g_exp_phase == 2` では gate/up を実行しません。また `fused_gu_sycl` が選ばれる実行では fused kernel を使い、この通常 dispatch 内の reuse 分岐を通りません（同ファイル `:7797-7819`）。

## 実行時の詳細

`launch_gu_port<TG,LN,KM>` の `TG == 18`, `LN == 8` specialization で初めて該当箇所に到達したとき、関数内 `static const bool` を初期化します。値判定は specialization ごとにキャッシュされ、プロセス中に環境を変更しても再評価されません。`KM` の true/false は別 specialization です。static 初期化に渡す device は最初の呼び出しの device であり、この bool 自体は device ごとの map ではありません（同ファイル `:5895-5899`、helper `engine/sycl/include/strata/sycl_queue.hpp:196-200`）。

reuse 条件が成立すると `launch_gu_row_reuse<18>` を呼び出して通常 kernel を return します。kernel は 8 lanes を 1 row に割り当て、work item ごとに 2 行分の weight row を処理し、各 expert entry の結果を gate/up の該当バッファへ書きます。entry は 4 件単位で処理し、残りは 3（`STRATA_EXPERT_ROW_E3` が有効な場合）、2、1 件に分けます（同ファイル `:4374-4425`, `:4428-4459`）。reuse 条件が成立しない場合は `native_gu_kernel` を使う通常経路へ続きます（同ファイル `:5895-5918`）。

## ログと測定値

reuse kernel を選んだ最初の呼び出しでは stderr に次の行を出します。C++ の関数内 static により、その specialization につき 1 回です。

```text
strata: IQ3_XXS raw two-row GU reuse enabled (8 lanes, SIMD16)
```

`STRATA_EXPERT_ROW_E3` により 3-entry tail kernel も選択された場合、`launch_gu_row_reuse` 側からさらに `strata: IQ3_XXS exact three-entry row reuse enabled` が stderr に出ます。通常 kernel に戻る場合、この reuse 固有ログは出ません。対象変数の無効値に対する専用警告やエラーはありません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4437-4444`, `:5897-5906`）。

この変数に対する性能測定値は、参照した現行 Strata ソース内では確認できません。近接する `STRATA_GRID_SLM` コメントの計測値は別の機能についての記述であり、ここには転用していません（同ファイル `:484-489`）。

## 根拠

- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5895-5918` — 環境変数 helper 呼び出し、Battlemage・旧 kernel・split 条件、reuse kernel と通常 kernel の分岐。
- `engine/sycl/include/strata/sycl_queue.hpp:193-200` — helper の値判定と未設定時の Battlemage default。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4374-4459` — 2 行 reuse kernel、gate/up への出力、E3 分岐とログ。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1175-1180`, `:4478-4488`, `:4515-4518`, `:5940-5949` — lane 数の compile-time default、環境変数による選択、許容 lane 値。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3931-3938`, `:6020-6067`, `:7797-7819`, `:7874-7878` — 旧 kernel / split / fused / expert type dispatch の条件。
