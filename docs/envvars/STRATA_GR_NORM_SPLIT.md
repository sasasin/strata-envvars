# `STRATA_GR_NORM_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版の fused GR（hyper-connection read）で、正規化の計算をトークンごとに 1 work-group で処理するか、トークンと stream（`HC`）ごとに分けて処理するかを選びます。未設定時は分割側です。分割側のカーネルは各 stream の正規化係数と正規化済み activation を書き、通常の後続 down / up 計算へ渡します。設定値は正規化カーネルの選択に使われます（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:415-420, 3320-3339`）。

この読み取り実装は SYCL ポートにあります。通常の生成では、`--no-fused-gr` がなく、native GR の FP32 activation 経路が有効で、GPU stage / dump / stage timing を使わず、モデル形状が `fused_gr_supported` に一致する場合に fused read が選ばれます（`engine/sycl/src/program/generate.cpp:3221-3228`, `engine/sycl/src/core/layer.cpp:1558-1559`, `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508`）。その条件を満たさない読み取りにはこのスイッチは適用されません。

## 値と判定

関数 `gr_norm_split()` は `std::getenv` で値の有無を見て、設定されていれば `std::atoi` の結果が非ゼロかを判定します。`atoi` は先頭の空白と符号の後の10進数字列を読み、数字以降の文字を検査しません。値全体の厳密な boolean parse や範囲検証はありません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:574-577`）。

| 条件 | unset | 分割側が有効になる値（例） | 分割側が無効になる値（例） |
| --- | --- | --- | --- |
| SYCL 実装で `gr_norm_split()` が評価される場合 | 有効（`getenv` が `nullptr` なら `true`） | `1`, `-1`, `1tail`, `  +2` | 空文字, `0`, `0tail`, `true`, `false`, `tail` |

数値変換後の `int` が非ゼロなら `true`、ゼロなら `false` です。大文字小文字は比較対象でなく、`true` / `false` は整数として変換されるためどちらも `0` になります。数値の後ろに文字があっても無視されます。整数の表現範囲を超える入力は `atoi` の範囲外であり、コードに検査や fallback はありません。

CLI 引数や設定ファイルによる上書きはこの関数にはありません。`--no-fused-gr` は fused read 全体を選ばない条件ですが、環境変数との値優先順位を作るものではありません（`engine/sycl/src/program/generate.cpp:3227-3228`）。

## 有効になる条件

- Strata の SYCL 実装を使い、fused GR read が選択された経路であること。通常の生成では `gr_native_mmvf`、`--no-fused-gr`、GPU stage、dump、stage timing、およびモデル形状の条件により fused read が選ばれない場合があります（`engine/sycl/src/program/generate.cpp:3227-3228`, `engine/sycl/src/core/layer.cpp:1558-1559`）。
- fused read が `fused_gr_read_multi` の正規化カーネル選択へ到達すること。そこで `true` なら `gr_norm_split_port_kernel` 系、`false` なら `gr_norm_multi_kernel` が選ばれます（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3320-3339`）。
- `STRATA_SYCL_GR_NORM_BOUNDS` が先頭文字 `'1'` であり、分割が有効な場合は bounds 付き分割カーネルが選ばれます。分割を無効にするとこの分岐も成立せず、通常の1 work-group-per-token カーネルへ進みます（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:569-572, 3324-3339`）。
- `STRATA_SYCL_GR_CACHED_NORM` 等の条件を満たす cached norm 経路も `gr_norm_split()` が真であることを条件にします。分割を無効にすると cached norm 判定とその経路は使われません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:76-79, 3298-3300, 3320-3323`）。
- `STRATA_GR_CACHED_NORM` または `STRATA_GR_LO_REUSE` による再利用経路も分割を前提とし、Battlemage、sliced down、他の GR kernel 設定、および安全性判定などの条件があります。分割を無効にするとこの再利用条件は成立しません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3301-3314`）。
- `STRATA_GR_V3` が有効で、デバイス上で V3 の split が選択されると `fused_gr_read_multi` は通常の norm カーネル選択へ進まずに戻ります。その経路では、この変数による norm カーネル切り替えは行われません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202, 3296-3297`）。

## 実行時の詳細

値は `gr_norm_split()` の関数内 `static const bool` に保存されます。したがって環境値を読むのはプロセス起動時ではなく、この関数の初回評価時で、その後の環境変更は反映されません。設定値が未設定か調べた後、設定されている場合は `getenv` を再度呼んで `atoi` します（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:574-577`）。

`true` の通常経路は work-group 数を `n_tok * HC` とし、各グループが 1 token / 1 stream を処理します。`false` の経路は `n_tok` グループで、1 グループがその token の全 stream を処理します。どちらも norm の `rs` と正規化済み activation `xn` を後段へ渡します（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:351-411, 420-470, 3324-3339`）。コメントと実装は分割カーネルが stream ごとの同じ要素順と reduction 順を維持する設計だと記していますが、この調査では実行時の数値一致や性能を測定していません（同ファイル `:415-420`）。`STRATA_GR_V3` が先に有効な経路では通常の norm カーネル選択に届かない場合があります（同ファイル `:3168-3202, 3296-3297`）。

単一 token の `fused_gr_read` も、`kDownXnTooBig`、down-sliced、分割 norm、down-direct のいずれかが有効なら scratch を用意して `fused_gr_read_multi(..., 1, ...)` に委譲します。したがって `STRATA_GR_NORM_SPLIT=0` でも、他の条件（例えば既定で真の down-sliced）が成立すれば multi read 内の正規化カーネル選択には到達し、非分割カーネルになります（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:834-837, 3510-3533`）。

## ログと測定値

この環境変数の読み取り、値の採用、分割 / 非分割カーネルの選択に固有のログや警告はありません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:574-577, 3320-3339`）。ソースコメントは同じ要素・和の順序を維持する設計を述べていますが、当該環境変数について資料に条件付きの性能測定値は確認できません。ここでは速度差を記載しません。

## 根拠

- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:574-577` — `getenv` / `atoi` による判定と static cache。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:351-411, 415-470` — token 単位と token-stream 単位の norm カーネル。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3320-3339, 3522-3533` — カーネル選択と single-read から multi-read への委譲。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3298-3314` — cached norm / reuse 経路の条件。
- `engine/sycl/src/program/generate.cpp:3227-3228`, `engine/sycl/src/core/layer.cpp:1558-1559`, `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508` — 通常生成で fused GR が有効になる条件。
