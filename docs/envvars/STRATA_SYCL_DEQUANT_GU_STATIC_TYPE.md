# `STRATA_SYCL_DEQUANT_GU_STATIC_TYPE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL backend の IQ gate/up 行列を FP16 へ dequantize する tiled 経路で、対象の量子化型を kernel のテンプレート引数として固定するかを選びます。ON の場合、型 ID 16・22・29 ではそれぞれ `launch_dequant_gu_tiled<..., 16>`、`<..., 22>`、`<..., 29>` を起動し、kernel 内で型を選ぶ `dq_dispatch` の実行時 switch を避ける構成になります。OFF、またはこの3型以外では型引数を 0 とした共通 kernel に進み、引数 `type` を使って `dq_dispatch` が型を選びます。これは入力の型を指定・変更する設定ではありません。`iq_dequant_gu_f16` の実装と tiled dispatch は `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6592-6609,6638-6649`、decoder の型 switch は同 `:3596-3630` にあります。

## 値と判定

値は `env_on` helper が `std::getenv` で取得します。環境変数が未設定、または値が空文字なら OFF、先頭文字が `'0'` なら OFF、それ以外は ON です。文字列全体や数値としては parse せず、先頭文字だけを比較します。従って `0`、`0anything`、`0.1` は OFF、`1`、`1anything`、`true`、`-1`、` 0` は ON です（`'0'` の前にある空白や符号を除去しません）。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL tiled gate/up 経路で初めて当該分岐に到達 | OFF | 空でない値で先頭文字が `0` 以外 | 空文字、先頭文字 `0` |

## 有効になる条件

- SYCL backend の `strata_kernels` にこの実装が含まれる必要があります。SYCL CMake は `iq_kernels.dp.cpp` を kernel source として追加し、`strata` は `strata_kernels` にリンクします（`sycl/CMakeLists.txt:240-255,305-307`）。CUDA 実装は別ファイル `src/kernels/cuda/iq_kernels.cu` にあり、この名前の参照はありません。
- gate/up dequantization が `iq_dequant_gu_f16` に到達する必要があります。SYCL prefill は native expert などの経路から同関数を呼びます（`sycl/src/prefill/prefill.cpp:4692-4717`）。SYCL の `dequant_bench` も同じ関数を呼びます（`sycl/src/kernels/dequant_bench.cpp:49`）。
- `STRATA_SYCL_DEQUANT_GU_SG` が `atoi` で 2・4・8 と判定され、tiled 経路へ進む必要があります。未設定時は 1、その他の変換結果も 1 に fallback するため、この変数は参照されません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6611-6617,6645-6649`）。
- 先行する `STRATA_SYCL_DEQUANT_GU_BOUNDED` 経路が処理を完了しない必要があります。bounded が ON で型 ID 16・22・29 の入力がその実装に受理されると、そこで return するため本変数は参照されません。bounded が OFF、または bounded 関数が false を返す場合は後続へ進みます（同 `:6537-6558,6643-6648`）。
- tiled 経路でも型別 specialization があるのは型 ID 16・22・29 だけです。他の受理型ではフラグが ON でも共通 kernel に fallback します（同 `:6592-6609`）。また入口は `n_embd % 256 != 0`、未知の IQ 型、または `tail != nullptr` をエラーにして終了するため、その入力ではこの設定による処理に至りません（同 `:6638-6643`）。
- CLI 引数や設定ファイルによる上書きはこの実装にはありません。別環境変数による選択条件は上記の `STRATA_SYCL_DEQUANT_GU_SG` と bounded 経路です。

## 実行時の詳細

`iq_dequant_gu_f16` はまず引数を検証し、関数内 `static` の `bounded` を初期化して bounded 経路を試します。続いて `dequant_gu_subgroups()` の関数内 `static` 値を参照し、値が 1 以外なら、初めてその tiled 分岐へ来たときに `static_type` と `static_row` をそれぞれ一度だけ `env_on` で読みます。従って本変数はプロセス起動時には読まれず、最初に tiled 分岐へ到達した時点の値がその後の呼び出しにも使われます。プロセス実行中に環境を変更しても、その static 値は更新されません。bounded 経路が毎回処理を終える場合、または subgroup 数が 1 の場合は `static_type` の初期化自体が起きません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6611-6617,6638-6649`）。

`static_type` が true であっても、dispatch は実際の `type` 引数で分岐します。ID 16・22・29 だけをコンパイル時型付きの tiled kernel に送り、それ以外は型 0 の汎用 tiled kernel に送り、`dq_dispatch` に実際の型 ID を渡します。処理先は gate/up の各 block から対応する FP16 出力位置への dequantization です（同 `:6562-6589,6592-6609`）。この分岐が生成 token や型の選択を変えるとはコードから確認できません。

## ログと測定値

この環境変数の読み取りや ON/OFF を知らせるログはありません。対象関数の引数検証に失敗した場合は `iq_dequant_gu_f16: type %d / %lld\n` を stderr に出して `exit(1)` します。これはこの環境変数固有のエラーではありません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6643`）。`docs/DETAILS.md` を含む Strata の文書に本変数名または tiled gate/up の測定条件付き性能値は見つからなかったため、性能差は記載しません。

## 根拠

- 読み取り規則: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692,6645-6648`
- bounded 経路・subgroup 既定値・tiled dispatch: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6558,6592-6617`
- validation と通常 dequant kernel: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6675`
- compile-time 型付き／実行時型 dispatch: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3596-3630,6562-6609`
- SYCL build target: `sycl/CMakeLists.txt:240-255,305-307`
- 通常の prefill 呼び出し: `sycl/src/prefill/prefill.cpp:4692-4717`
- bench 呼び出し: `sycl/src/kernels/dequant_bench.cpp:49`
