# `STRATA_MMVQ_LARGE_GRF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL native MMVQ の一部の複数列 wide kernel について、通常の 128 GRF 構成の代わりに `grf_size<256>` を指定した kernel を選びます。対象は Q6_K wide、Q4_K/Q5_K/IQ4_XS wide、および登録済みの Q6_K planar 行列です。1 列ではこの変数による切り替えは行いません。値はカーネル選択を変えますが、この変数を読むコードは数値計算結果を加工しません。読み取りと選択は `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp` の `mmvq_large_grf` と各 launch 関数にあります（1635-1646、1648-1685、1961-2004、2981-3002 行）。

## 値と判定

`mmvq_large_grf` は `std::getenv` で値を読み、設定されていれば `std::atoi(e) != 0`、未設定なら queue の device が Alchemist かを判定します。文字列全体の検証や値域チェックはありません。したがって空文字、`true`、`0anything` は `atoi` の結果が 0 となり無効、`1`、`-1`、`1tail` は非 0 となり有効です。先頭の空白や符号は `atoi` の規則で扱われます（例: ` 1` は有効）。数値変換不能も 0 になります。数値範囲外の文字列について実装上の保証はありません。

| 条件 | 未設定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `mmvq_large_grf` の既定判定 | Alchemist なら有効、それ以外は無効 | `atoi` が非 0 を返す値 | `atoi` が 0 を返す値（空文字、`0`、`0anything`、`true` など） |
| Q6_K Battlemage 形状ガード | `STRATA_Q6_SHAPE_GRF` が有効で、対象形状なら別経路で有効になり得る | 設定値が非 0 なら通常判定で有効 | 明示値が 0 なら形状ガードを抑止し、通常判定も無効 |

Q6_K の Battlemage 形状ガードは、この変数が未設定であることを追加条件にします。そのため空文字や `0` のように値変換上は無効でも、設定されているだけでこの自動ガードを止めます（1661-1663 行）。

## 有効になる条件

- この実装は `engine/sycl/CMakeLists.txt` に含まれる SYCL engine の native MMVQ です（同ファイル 43 行）。CUDA/HIP の MMVQ でこの変数を読む実装は、名前の全参照検索では見つかりません。
- Kernel の列数が 2-8 である必要があります。Q4_K/Q5_K/IQ4_XS の wide kernel は `STRATA_MMVQ_WIDE_K` が有効で、`n_in` が 256 の倍数の場合に候補になります。ただし `STRATA_MMVQ_WIDE_K_RPW` 由来の `rpw` が 2 または 4 なら別 kernel を選び、この GRF 判定には進みません。`STRATA_MMVQ_WIDE_K=0` などで wide 経路を選ばない場合も対象外です（1961-2004、2066-2083 行）。
- Q6_K の通常 wide kernel は `g_q6k_wide` が有効で、列数が 1 以上 `STRATA_MMVQ_WIDE_MAXC` 以下、`n_in` が 256 の倍数、`n_out >= STRATA_MMVQ_WIDE_MIN` の条件を満たすと候補になります。さらに `STRATA_MMVQ_WIDE_RPW` が 1 で `STRATA_MMVQ_A2` が有効な A2 経路に限り、複数列で GRF256 kernel を選択できます。RPW が 2 または 4 の経路、および A2 無効時はこの GRF 判定を通りません（1545-1547、1631-1633、1648-1708、3935-3956 行）。
- Q6_K の planar MMVQ は `STRATA_Q6_PLANAR` が未設定または `0` 以外で planar 行列が登録された場合にこの判定を使い、2-8 列で GRF256 kernel を選べます。`STRATA_Q6_PLANAR=0` は planar 経路を無効にします。`STRATA_Q6_PACKED=1` で登録された packed 行列は MMVQ 時に先に試され、そこで処理されると planar または通常 wide 経路には進みません。packed の有効判定は値全体がちょうど `1` の場合です（2876-2898、2981-3002、3091-3104、3935-3939 行）。
- Alchemist 既定は `mmvq_large_grf` の初回評価時に選ばれます。明示値があれば GPU 世代による既定値を置き換えます。コメント上、Battlemage では未設定時に限って `STRATA_Q6_SHAPE_GRF` と対象 shape による Q6_K の限定的な有効化があります。対象は `(n_in,n_out)=(6144,2560)`、`(2560,512)`、`(2560,640)`、3 列以上の `(2560,6144)`、4 列以上の `(2560,10240)` または `(2560,12288)` です（1635-1638、1655-1671 行）。

## 実行時の詳細

`mmvq_large_grf` 内の `static const bool` は最初に呼ばれたときだけ初期化され、以後の呼び出しで環境を読み直しません。未設定時の Alchemist 判定に使う device もその初回呼び出しの queue です。同一プロセスで後から環境値を変更しても、このキャッシュ済み判定は変わりません（1640-1646 行）。

判定が true の場合、対象 launch 関数は `sycl::ext::intel::experimental::grf_size<256>` property を付けた kernel を投入して return し、通常 kernel の投入を避けます。false の場合は通常 kernel を選びます。Q6_K A2 wide、generic wide、Q6_K planar の各分岐がこの選択を行います（1671-1685、1992-2004、2981-3002 行）。

別経路の Battlemage Q6_K 形状ガードは `std::getenv(...) == nullptr` を launch 時に確認するため、こちらは `mmvq_large_grf` のキャッシュとは別に設定有無を判定します。条件を満たすと stderr に `strata: shape-guarded Q6_K large-GRF dispatch enabled` を出し、Q6_K A2 wide の GRF256 kernel を選びます（1655-1678 行）。この guard の値は `strata::bm_default_on("STRATA_Q6_SHAPE_GRF", ...)` の戻り値にも依存します。

## ログと測定値

この変数を明示して GRF256/通常 kernel を選んだこと自体を示すログはありません。Battlemage の形状ガードが有効になった場合に限り、上記の stderr メッセージが出ます（1664-1669 行）。起動時の kernel 実行失敗時にこの変数固有の fallback やエラーメッセージを出すコードは確認できませんでした。

ソースコメントは A770 で 128 GRF 時に spill が起き、`mmvq_bench` の Q6_K 4 列で 70-80 から 150-237 GB/s、checksum は同じだったと記しています。これはコメントに記載された測定条件・値であり、この調査で再測定したものではありません（1635-1638 行）。

## 根拠

- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1635-1646` — GRF256 の既定と環境値変換、static cache。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1648-1685` — Q6_K wide の列数・A2・形状ガードと kernel dispatch。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1961-2004` — Q4_K/Q5_K/IQ4_XS wide 経路での dispatch。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2898, 2981-3034, 3935-3956` — Q6_K packed/planar/通常経路と候補条件。
- `engine/sycl/CMakeLists.txt:43` — 対象ソースが SYCL engine に含まれること。
