# `STRATA_MMVQ_SHAPE_RPW`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL native MMVQ の wide Q4_K/Q5_K カーネルで、Battlemage 向けに限定された projection shape のとき、1 subgroup が処理する行数を 1 行から 2 行にし、同じ入力列の activation をその 2 行で再利用します。自動選択の対象外では、この変数による選択は行わず、`STRATA_MMVQ_WIDE_K_RPW` がなければ `rpw=1` のままです。制御判定は `launch_wide`、行再利用カーネルは `native_mmvq_wide_rpw_kernel` にあります（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1883-1916,1961-2004`）。

## 値と判定

`strata::bm_default_on` は `std::getenv` の結果が null でなく、かつ空文字でない場合、先頭文字が `'0'` なら false、それ以外なら true を返します。文字列全体の parse や数値検査はしません。未設定と空文字はどちらも Battlemage 判定に戻り、それ以外のデバイスでは false です（`engine/sycl/include/strata/sycl_queue.hpp:193-200`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `launch_wide<F, NCOLS>`（既定引数 `bm_default=true`） | Battlemage なら true、それ以外は false | 空でなく先頭文字が `0` 以外。例: `1`, `true`, `false`, ` 0`, `anything` | 空文字は unset と同じ。先頭が `0` の値（`0`, `0anything`）は false |

大文字小文字、前後空白、後続文字は検査されません。したがって `false` は有効、`0anything` は無効、先頭に空白がある ` 0` は有効です。`launch_wide` 内の関数 template ごとの `static const bool` に保存され、各 `<F, NCOLS>` の初回呼び出し時に渡されたデバイスと環境から一度だけ決まります（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1961-1966`）。

## 有効になる条件

- SYCL の native MMVQ 経路で Q4_K または Q5_K が選ばれ、`try_wide` が `STRATA_MMVQ_WIDE_K` を有効と判定し、`1 <= ncols <= 8` かつ `n_in` が QK の倍数である必要があります。`STRATA_MMVQ_WIDE_K` は未設定なら有効、設定時は `atoi` が 0 以外なら有効です（空文字や数値に変換できない文字列は 0 扱い）。他の変数や CLI から `STRATA_MMVQ_SHAPE_RPW` の値を上書きする処理はこの経路にはありません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2066-2083,3861-3868,3457`）。
- Shape 自動選択には、呼び出し時点のデバイスが Battlemage で、`STRATA_MMVQ_WIDE_K_RPW` が未設定であり、`ncols <= 4` であることも必要です。この変数が設定されていると、値が空でも自動選択は抑止されます。設定値は `atoi` で読む別の RPW 制御に渡され、2 または 4 のときは対応する行再利用カーネルを選びます（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1918-1920,1967-1975,1984-1991`）。
- Q4_K の対象は `(n_in,n_out)=(2560,6144)`, `(2560,10240)`, `(2560,12288)`, `(6144,2560)`。Q5_K は `(2560,12288)`, `(6144,2560)` です。他の shape、`ncols` が 5〜8、IQ4_XS 等の別形式はこの制御では 2 行再利用にしません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1970-1975,2071-2083,3867,3465,3773-3776`）。
- 通常の SYCL native MMVQ の dispatch は GGML type 12 を Q4_K、13 を Q5_K に振り分けます。wide 経路に入らない場合は既存の multi/kernel 経路へ進みます（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4222,3867-3872,3465-3467`）。

## 実行時の詳細

`native_mmvq` から Q4_K/Q5_K 実装に入り、`try_wide` が wide kernel 経路を選ぶと、列数ごとに `launch_wide<F, NCOLS>` が呼ばれます。`STRATA_MMVQ_SHAPE_RPW` の判定値はその template specialization ごとに static cache されます。プロセス実行中に環境を変更しても、既に初期化された specialization には反映されません。異なるデバイスを同一プロセスで使う場合も、その specialization は最初に渡されたデバイスでの結果を再利用します（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1961-1968,2071-2083,4204-4217`）。

条件を満たすと `rpw=2` となり、`native_mmvq_wide_rpw_kernel<F,NCOLS,2>` を launch します。各 subgroup は連続する 2 行分の重みを読み、各入力列の activation を読み込んで両行の dot 積に使います。Q4_K/Q5_K はこの条件でのみ対象となり、対象外なら `rpw` の初期値 1 に対応する通常 wide kernel が使われます（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1883-1916,1962-2004`）。

## ログと測定値

初めて条件を満たした `launch_wide<F, NCOLS>` specialization では stderr に `strata: shape-guarded Q4_K/Q5_K dense row reuse enabled` を出力します。同じ specialization では `note` も static なので以後この箇所からは再出力しません。条件に合わない場合、このログは出ません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1975-1982`）。この checkout の対象コードから本変数による測定値は確認できません。

## 根拠

- `engine/sycl/include/strata/sycl_queue.hpp:193-200` — 値の解釈と Battlemage 既定値。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1883-1916,1961-2004` — wide row reuse kernel、shape 条件、ログ、launch 分岐。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2066-2083,3457-3467,3861-3872,4204-4222` — wide 経路の条件と Q4_K/Q5_K dispatch。
