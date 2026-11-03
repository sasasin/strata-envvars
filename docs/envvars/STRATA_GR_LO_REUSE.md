# `STRATA_GR_LO_REUSE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Intel SYCL backend の fused hyper-connection read で、down projection の部分和を reduce するときに low-rank SiLU 出力を計算して保存し、続く up projection で再利用するかを制御します。通常は up kernel 内で reduce と SiLU を行います。この制御が有効で後述の条件を満たすと、reduce kernel が `lo` に SiLU 結果を書き、up kernel はその値を読みます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:635-667,727-755`）。

コード上の環境読み取りは `fused_gr_read_multi()` 内の 1 箇所です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1980-1988`）。対象は SYCL の Battlemage 向け既定 on 制御で、CUDA/HIP backend にこの名前の読み取りはありません。

## 値と判定

`strata::bm_default_on()` は文字列全体を parse せず、空でない値の先頭文字だけを見ます。結果は関数内の `static const bool` に保存されます。

| 値 | helper の判定 |
|---|---|
| 未設定 | Battlemage なら on、それ以外は off |
| 空文字 | 未設定と同じ。Battlemage なら on、それ以外は off |
| 空でない値の先頭が `0` | off（例: `0`, `0abc`） |
| それ以外の空でない値 | on（例: `1`, `2`, `true`, `false`, 空白で始まる値） |

数値変換、全体一致、大文字小文字の変換、無効文字列の fallback はありません。読み取り結果は最初にこの判定へ到達したときに初期化され、その後プロセス内で再評価されません。`static` はデバイスごとではないため、未設定または空文字の場合に複数デバイスを使うと、最初の初期化時に渡されたデバイスの世代判定が共有されます。実行中に環境値を変更しても反映されません（`sycl/include/strata/sycl_queue.hpp:159-166`; `sycl/src/kernels/cuda/fused_gr.dp.cpp:1982`）。

## 有効になる条件

helper の判定が on でも、次の条件がそろわなければ low-rank SiLU の再利用は設定されません。

- fused hyper-connection read を使う。生成側では `--gr-native-mmvf` が有効で、`--no-fused-gr`、GPU stages、layer/half dump、stage timing が使われていない場合に layer 側へ有効化を伝えます。さらにモデルの `n_embd`, `hc`, `hc_lr` がこの build の固定 geometry と一致する必要があります（`src/program/generate.cpp:3096-3105`; `sycl/src/core/layer.cpp:1558-1559`; `sycl/src/kernels/cuda/fused_gr.dp.cpp:2147-2149`）。
- `gr_norm_split()` と `gr_down_sliced()` が有効で、`gr_more_groups()`、`gr_large_grf()`、`gr_up_ilp()` は無効、`gr_up_cols() == UPM_COLS` である。
- 現在の device が Battlemage であり、`gr_reuse_safe()` が scratch と入出力バッファの重なりを検出しない。

`STRATA_GR_LO_REUSE=1` などで helper を on にしても、Battlemage 以外では世代条件により無効です。`STRATA_GR_CACHED_NORM` が on なら共通の適用判定ブロックへ進みますが、この変数の判定自体が off なら `m.cached_lo` は off のままです。別変数 `STRATA_GR_REDUCE_ILP` は `m.cached_lo` が有効な場合に reduce kernel の variant を選びます。いずれもこの変数の値を上書きしません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1981-1994,2058-2073`）。また、`STRATA_GR_V3` の選択経路で V3 split が成立するとこの判定に到達する前に戻ります（同ファイル `1850-1884,1971-1979`）。

## 実行時の詳細

適用条件を満たすと `m.cached_lo` に環境判定結果が入り、down sliced kernel の reduce で各 low-rank 成分について部分和を `HC` で割り、SiLU を適用して `lo` に保存します。続く up kernel の再利用 variant は `m.cached_lo` が true のとき保存済み `lo` を work-group local memory に読み込み、再計算を省きます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:635-667,727-755,901-911`）。

条件を満たして有効化された最初の該当呼び出しでは stderr に次の形式を一度出します。`normalized activation` は別の `STRATA_GR_CACHED_NORM` 制御の結果です。

```text
strata: GR reuse enabled: normalized activation <0|1>, low-rank SiLU <0|1>
```

値を on にしても条件を満たさないときの個別の警告やエラーは、この分岐にはありません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1983-1994`）。関連する SYCL 説明資料は、この環境変数を Battlemage で既定 on とし、対応 layout で low-rank SiLU 出力を再利用すると記載しています。資料の複数制御を束ねた性能値は本変数単独の測定値として扱えないため、ここでは転記していません（`docs/INTEL.md:520-536`）。

## 根拠

- 全参照と環境値の読み取り: `sycl/src/kernels/cuda/fused_gr.dp.cpp:1980-1988`。リポジトリ全体の名前検索では、この実装箇所と `docs/INTEL.md` の説明表以外に参照はありません。
- 未設定・空文字・先頭文字による判定、Battlemage 既定値: `sycl/include/strata/sycl_queue.hpp:159-166`。
- 再利用の安全性判定: `sycl/src/kernels/cuda/fused_gr.dp.cpp:266-290`。
- 再利用値の生成・読み込みと有効ログ: 同ファイル `635-667,727-755,901-911,1983-1994`。
- fused 経路の有効条件: `src/program/generate.cpp:3096-3105`, `sycl/src/core/layer.cpp:1558-1559`, `sycl/src/kernels/cuda/fused_gr.dp.cpp:2147-2149`。
