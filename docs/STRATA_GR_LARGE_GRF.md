# `STRATA_GR_LARGE_GRF`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。調査対象は Strata 所有ソース。外部 SYCL ランタイム・コンパイラ・ドライバーの内部動作は対象外。

## 役割

SYCL 版の融合 hyper-connection read に使う一部カーネルで、Intel GPU の GRF（General Register File）サイズを通常の128レジスタ/スレッドから256レジスタ/スレッドへ要求するかを選びます。対象は sliced down カーネルと multi-token up カーネルです。値はカーネル起動時に `grf_size<256>` プロパティを付ける分岐を切り替えます。Strata のソースは「256」を要求しますが、コンパイラやデバイスがその要求をどう実現するかはここでは扱いません。

## 値と判定

環境変数の値全体を厳密に検証せず、`std::atoi` の結果が0かどうかで判定します。

| 設定 | 判定 |
|---|---|
| 未設定 | SYCL デバイスが Alchemist（Arc A-series）なら有効。それ以外は無効 |
| `1` など、`atoi` が0以外を返す値 | 有効 |
| `0`、空文字、数値として先頭を変換できない文字列（例: `true`） | 無効 |

`atoi` は先頭の空白と符号を許し、10進数として読める先頭部分を変換します。したがって ` 1tail` や `-1` は有効、`0tail` は無効です。大文字小文字の比較はありません。未設定時の Alchemist 判定は、デバイス情報の architecture、デバイス名、または PCI ID を使う `intel_gpu_gen()` によります。

## 有効になる条件

- Strata の SYCL 実装で、融合 hyper-connection read の通常の multi-token 経路が実行されることが必要です。生成処理では `--gr-native-mmvf` が有効で、`--no-fused-gr`、GPU stage、layer/half dump、stage timing などによる無効化条件に該当しない場合に融合 read を設定します。対象の形状も `fused_gr_supported()` に合う必要があります。
- `STRATA_GR_V3=1` の二カーネル経路が利用可能な場合は、`fused_gr_read_multi()` がその経路から戻るため、この変数の分岐は通りません。V3 が未設定・無効、またはデバイスの容量条件で通常経路に fallback した場合は、以降の通常経路で判定されます。
- 通常経路では上りカーネルに判定が使われます。下りカーネルへの適用は `STRATA_GR_DOWN_SLICED` が有効な場合だけです。下りが sliced でない direct/tiled 経路でも、通常経路の上りカーネルには設定が反映されます。

## 実行時の詳細

`gr_large_grf(q)` 内の `static const bool` が初回呼び出しで一度だけ評価されます。その時点の環境値と渡された queue のデバイス世代をキャッシュし、後から環境を変更しても再評価しません。同じ静的変数は全 queue で共有されるため、未設定時に複数デバイスを使う場合、既定値は最初にこの関数へ渡された queue の GPU 世代で決まり、その後の queue に対しても同じ値が使われます。

有効時は、sliced down カーネルと通常または more-groups の multi-token up カーネルに `grf_size<256>` を付けます。無効時は同じカーネルの GRF 指定なしの variant を起動します。ログや警告を出す処理はこの変数の実装箇所にはありません。

ソースコメントは A770 で up カーネルが128レジスタ時に約3.4 KB/スレッド spill した（unitrace）こと、256レジスタでは Xe core の常駐スレッド数が半分になること、および既定 ON は測定された Arc A-series に限ることを記しています。これらはソースコメント上の説明であり、当調査で測定を再実施したものではありません。`docs/DETAILS.md` にこの変数固有の測定結果は見当たりません。`docs/A770_SPEED_SPEC.md` の GRF 128/256 に関する記述は調査項目・別設定の結果で、この環境変数の性能結果としては扱いません。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:625-650` — 変数の読み取り、`atoi` 判定、未設定時の Alchemist 既定値、およびより多いグループ数の経路。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:803-834, 850-875` — more-groups の down/up と通常 up における `grf_size<256>` variant。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1770-1824, 1956-2044` — V3 経路の先行 return と、通常経路での down/up の分岐。
- `sycl/include/strata/sycl_queue.hpp:120-158` — Alchemist 世代の分類方法。
- `sycl/src/program/generate.cpp:423, 579, 767, 1771, 2002, 2911-2920` — `--gr-native-mmvf` 等の既定値・CLI 設定と融合 read の有効化条件。
- `sycl/src/core/layer.cpp:1558-1559, 1620-1652` — 形状条件および融合 read の呼び出し。
- `docs/A770_SPEED_SPEC.md:178-194, 260-264` — GRF 調査の背景。変数固有の測定根拠ではない。
