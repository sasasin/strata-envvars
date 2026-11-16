# `STRATA_PRIVATE_GU_PREPARED`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の grouped expert の gate/up (GU) 計算で、Battlemage 向けの private kernel 経路を選ぶ opt-in です。同じ変数が二つの独立した分岐で使われ、IQ2_S では二行再利用 kernel、IQ2_XXS と IQ1_M では prepared dot kernel を選びます。どちらも選ばれない場合は通常の GU kernel 選択に進みます。変数自体は生成設定や CLI 引数を変更しません。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4223-4238`, `5605-5639`

## 値と判定

| 経路 | 読み取りと有効条件 | unset / 無効値の例 | 有効値の例 |
|---|---|---|---|
| IQ2_S row reuse | `v != nullptr && v[0] == '1'`。文字列全体や数値としての妥当性は検査せず、先頭 1 文字だけを比較する。 | unset、空文字、`0`、`true`、` 1` | `1`、`10`、`1abc` |
| IQ2_XXS / IQ1_M prepared GU | `p != nullptr && std::atoi(p) != 0`。`atoi` が先頭の空白と符号付き整数の先頭部分を変換し、後続文字は無視する。 | unset、空文字、`0`、`0anything`、`true`、`abc1` | `1`、`2`、`-1`、`1abc`、` 1` |

前者は環境変数を設定したかではなく先頭文字を判定し、後者は `atoi` の結果を判定します。そのため、例えば `1abc` は両経路で有効ですが、` 1` は prepared GU だけで有効です。`atoi` の変換結果が 0 なら無効です。値の範囲制限や clamp はありません。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4225-4234`, `4450-4453`

両関数とも判定結果を関数内 `static const bool` に保存します。各経路で最初に判定された後のプロセス内環境変更は、その経路の値に反映されません。二つの static は別々なので、各経路が初めて評価される時点が異なる場合は、それぞれその時点の値を読みます。row reuse 側の GPU 世代判定は、呼び出しスレッドごとに `thread_local` の device キャッシュを持ち、device が変われば再判定します。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4225-4234`, `4450-4453`

## 有効になる条件

- **IQ2_S row reuse**: SYCL の lane GU 経路に入り、`TG == 22` かつ 8 lane (`LN == 8`) であること、`STRATA_GRID_SLM` が 0 でコンパイルされていること、旧 kernel (`STRATA_OLD_IQ_MMVQ`) と split expert (`STRATA_EXPERT_SPLIT`) が無効であること、device 世代が Battlemage であることが必要です。満たさない場合はこの hook を使わず、通常の lane kernel 選択へ進みます。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4225-4235`, `5630-5639`
- **IQ2_XXS / IQ1_M prepared GU**: SYCL の lane GU 経路で、形式がそれぞれ `TG == 16` / `TG == 29`、lane 数が 8、`KM == true`、`L.n_embd == 2560`、`L.n_ff == 640` であり、旧 kernel と split expert が無効で、device 世代が Battlemage である必要があります。この分岐より先に、IQ2_XXS の `p16_enabled` または IQ1_M の `i1_enabled` が成立して専用 launcher を返した場合、この変数による prepared 経路には進みません。条件不足時は通常の GU launcher に続きます。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4450-4460`, `5605-5623`
- `STRATA_GRID_SLM` はビルド時 macro です。ソース内の既定値は 0 ですが、ビルドで 1 にすると IQ2_S row reuse hook はコンパイル対象外です。prepared GU 側にはこの macro guard はありません。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:483-488`, `5630-5639`
- 旧 kernel と split expert の判定は、このファイルの `env_on` を使います。unset・空文字・`0` で始まる値は無効、それ以外は有効です。したがって、例えば `STRATA_EXPERT_SPLIT=1` は両対象経路を抑止します。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3700`
- GU lane 数は `STRATA_GU_LANES`、split 対象の一部では `STRATA_KQ_GU_LANES` によって選択されます。値が 4/8/16/32 以外なら `kExpertLanes` に戻ります。8 lane でない呼び出しは対象分岐の `if constexpr` に一致しません。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4240-4249`, `5701-5711`

## 実行時の詳細

IQ2_S の row reuse hook は `launch_gu_port` 内で `launch_gu_row_reuse<TG>` を呼び、現在の grouped expert 入力に対して gate/up 行を計算してから戻ります。prepared GU は `launch_gu_prepared<TG>` を呼び、`gu_prepared_kernel` がグループ、行、各 expert entry を走査し、`gu_prepared_entries` / `gu_prepared_dot` で gate/up 出力を書き込みます。その後も呼び出し元の既存処理が続きます。これらは GU 計算 kernel の選択を変える実装であり、このコードだけから生成結果の速度や数値差は断定できません。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5630-5639`, `4358-4460`

環境変数の値が有効でも、device が Battlemage でない場合や上記の format・shape・lane・mode 条件が合わない場合はその private kernel を起動しません。CLI 引数による同名設定や別環境変数からの値の転送は、この変数の読み取り経路では確認できません。対象コードに timeout、専用エラー、無効値警告の処理はありません。条件に合わない場合も通常の GU 分岐へ続きます。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5605-5680`

## ログと測定値

この変数の有効・無効、無効値、または device 条件を知らせる専用ログはありません。Strata の資料にこの変数の測定値は見つかりませんでした。ソースコメントは private / default-off としていますが、測定結果ではなくコード上の opt-in として記載しています。`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4223-4238`, `4450-4453`

## 根拠

- 読み取り、値判定、cache、device 条件: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4223-4238`, `4450-4453`
- prepared dot / entry / kernel と launcher: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4358-4460`
- GU launcher の条件、先行分岐、通常経路: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5605-5680`
- lane 設定、旧 kernel / split 設定: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3700`, `4240-4249`, `5701-5711`
