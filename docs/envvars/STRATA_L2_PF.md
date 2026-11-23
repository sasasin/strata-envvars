# `STRATA_L2_PF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA verifier の window graph で、MoE の GPU / CPU expert 処理中に次層の dense weight 範囲へ L2 prefetch hint を発行する機能を有効にします。値が有効でも、1 group の非 batch・非 profiler・非 all-resident window でなければ範囲を作りません。対象値の計算結果を変える処理はこのコードにありません。`Verifier::record_window` が対象を集め、`l2_prefetch_ranges` が CUDA kernel を起動します（`engine/src/core/verify.cpp:1553-1565,1568-1608,2833-2845,2897-2906`; `engine/src/kernels/cuda/verify_kernels.cu:1932-1948,1952-1965`）。

## 値と判定

`record_window` 内の関数ローカル `static const int` 初期化で `std::getenv` を一度読み、設定があれば `std::atoi`、未設定なら `0` とします。判定は `l2pf_env != 0` です。空文字や数値接頭辞のない文字列は `atoi` により `0` となり無効です。先頭の空白・符号と数値接頭辞は変換され、後続文字は検査されません（例: `1junk` は 1、`0junk` は 0）。`true` / `false` は数値接頭辞がないため無効です。負数を含む非ゼロ整数は有効です。値の範囲検査や clamp はありません。`std::atoi` の整数範囲外の入力について、ソースに定義された扱いはありません（`engine/src/core/verify.cpp:1558,1565`）。

| 条件 | 未設定 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA verifier | `0`（OFF） | `1`, `2`, `-1`, `  +1tail` | 空文字, `0`, `0anything`, `true`, `false`, `abc` |
| HIP verifier | 値にかかわらず prefetch 機能は無効 | 該当なし | 該当なし |

この変数を設定する CLI 引数や、Strata の GPU default table から値を注入する処理は見つかりませんでした。したがって実装上は環境変数の parse 値が gate となり、別の CLI 値による上書きはありません。GPU defaults の sm_120 table にも `STRATA_L2_PF` は追加されていません（`engine/src/core/nv_defaults.cpp:104-115`）。

## 有効になる条件

- CUDA verifier であること。`STRATA_USE_HIP` build は `l2pf_cuda=false` とし、CUDA kernel の HIP compile 分岐も kernel 本体を no-op にします（`engine/src/core/verify.cpp:1560-1565`; `engine/src/kernels/cuda/verify_kernels.cu:1932-1948`）。このコードに OS 別の条件はありません。
- `G == 1`、`batch_rec_ == false`、`prof_on_ == false`、`ar_on() == false` が必要です。`G` は split window、または `T > kVerifyMaxT` の非 batch window で 2 になるため、その経路は対象外です（`engine/src/core/verify.cpp:1484-1486,1565`）。
- 次層 `l + 1` が window の範囲内にあり、その層に登録された `L2PrefetchSet` に少なくとも 1 範囲あることが必要です。範囲は `wt.all()` の `blk.<layer>` weight から、`hc_q8`、`native_data`、または resident な `data` があり byte 数が非ゼロのものを選びます（`engine/src/core/verify.cpp:1567-1602,2838-2839,2897-2898`）。
- prefetch の呼び出しには `STRATA_SH_STREAM` による shared-expert stream が有効で、`sh_cs_` と fork/join event が存在する必要があります。`STRATA_SH_STREAM` は未設定なら CUDA で有効、設定時は先頭文字が `'0'` でなければ有効です。したがって `STRATA_SH_STREAM=0` または `0anything` ではこの prefetch 呼び出しも行われません（`engine/src/core/verify.cpp:415-425,2838-2845,2897-2906`）。
- `STRATA_L2_PF_MIB` は任意の上限です。`std::atol` で初回の有効 window 時に一度読み、正数なら各層の先頭からその MiB 数までを含めます。未設定・空文字・0・負数は上限なしです。数値接頭辞後の文字は検査されません（`engine/src/core/verify.cpp:1565-1567,1594-1599`）。
- `STRATA_L2_PF_BLOCKS` は kernel grid の調整値です。`l2_prefetch_ranges` の初回起動時に `std::atoi` で読み、未設定なら 8、設定時は `std::max(1, std::min(value, 64))` により 1〜64 に clamp します。したがって `0` や `abc` は 1、`100` は 64 です（`engine/src/kernels/cuda/verify_kernels.cu:1962-1965`）。
- 適用位置は partial-residency の expert 分岐です。device-hits 分岐では GPU expert 処理後、CPU rows の wait / copy 前に呼びます。通常の partial-residency 分岐では CPU share の処理後、CPU rows の wait 前に呼びます。後者は `device_plan_` のとき呼びません（`engine/src/core/verify.cpp:2833-2857,2893-2910`）。device-hits 分岐は `--pcie-frac 0` でも prefetch 条件に入るコードですが、その場合は同じログ上 CPU rows の flag wait / PCIe staging がないとされています（同 `verify.cpp:2833-2849`）。

## 実行時の詳細

`STRATA_L2_PF` は `record_window` が初めて該当箇所へ到達したときに static 初期化され、以後プロセス内で再読込されません。起動後の環境変更は反映されません。`STRATA_L2_PF_MIB` は gate を通る最初の window、`STRATA_L2_PF_BLOCKS` は最初の非空 range の kernel 起動でそれぞれ static 初期化されます。window graph の capture 中に条件を満たすと、各 layer の重みから層ごとの prefetch 範囲を作ります。対象 weight は attention-side hyper-connection、mixer / projection、FFN-side の順に rank 付けされます。`L2PrefetchSet::add` は 16 byte 未満、null pointer、上限 32 range 到達後の項目を捨てます（`engine/src/core/verify.cpp:1567-1602`; `engine/include/strata/kernels/verify_kernels.hpp:85-100`; `engine/src/kernels/cuda/verify_kernels.cu:1952-1965`）。

expert layer `l` の GPU / CPU 処理中、`l2pf[l+1]` を shared-expert stream に投入し、次層の dense weights に対する hint kernel を起動します。CUDA kernel は 16 KiB chunks に分け、sm_90 以上では `cp.async.bulk.prefetch.L2.global`、それ未満では `prefetch.global.L2` を発行します。HIP compile では本体は no-op です（`engine/src/core/verify.cpp:2838-2845,2897-2906`; `engine/src/kernels/cuda/verify_kernels.cu:1928-1948`）。

## ログと測定値

範囲を構築する条件に入ると、プロセス内で一度 stderr に次の形式を出します（`largest layer` は構築された最大 layer 範囲の MiB、`STRATA_L2_PF_MIB` による上限が正なら末尾に `, capped` が付きます）。無効値や適用条件を満たさない場合、この箇所のログは出ません（`engine/src/core/verify.cpp:1565-1567,1603-1608`）。

```text
strata: STRATA_L2_PF=<値>: next-layer dense-weight L2 prefetch while the window waits for CPU experts (largest layer <数値> MiB[, capped])
```

kernel 起動時の CUDA エラーは `l2_prefetch_ranges: <CUDA error string>` を stderr に出し、`exit(1)` します（`engine/src/kernels/cuda/verify_kernels.cu:37-40,1952-1965`）。`docs/DETAILS.md` にこの変数の測定値や個別説明は見つかりませんでした。ここでは性能値を記載しません。

## 根拠

- `engine/src/core/verify.cpp:1553-1566` — feature comment、値の static parse、backend / window gates、および `STRATA_L2_PF_MIB` の読み取り。
- `engine/src/core/verify.cpp:1567-1608` — weight 範囲の選択と順序、cap、stderr log。
- `engine/src/core/verify.cpp:2833-2857,2893-2910` — partial-residency の各呼び出し位置と CPU-row wait との順序。
- `engine/src/core/verify.cpp:415-425` — shared-expert stream の既定と `STRATA_SH_STREAM` 判定。
- `engine/src/kernels/cuda/verify_kernels.cu:37-40,1928-1965` — prefetch hint kernel、blocks 設定、起動エラーの扱い。
- `engine/include/strata/kernels/verify_kernels.hpp:82-102` — range 集合の上限と kernel API。
- `engine/src/core/nv_defaults.cpp:104-115` — sm_120 default table に当該変数がないこと。
