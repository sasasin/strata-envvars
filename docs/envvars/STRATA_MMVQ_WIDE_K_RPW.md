# `STRATA_MMVQ_WIDE_K_RPW`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の Q4_K、Q5_K、IQ4_XS 向け wide MMVQ カーネルで、一つの sub-group が担当する出力行数（rows per sub-group、RPW）を指定する。値を `2` または `4` にすると、それぞれの行数を同時に処理する `native_mmvq_wide_rpw_kernel` を起動する。その他の値では標準の1行 wide kernel（または複数列時の large-GRF variant）を使う。RPW kernel は各列の activation を一度ロードして複数行で使い、各行の積和と butterfly reduction を行う実装である（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1879-1915,1984-2004`）。

対象ソースは SYCL engine に含まれるファイルであり、CUDA/HIP 実装に同じ名前の読み取り箇所はない（`sycl/CMakeLists.txt:39`）。

## 値と判定

`wide_k_rpw()` は初回呼び出し時に環境変数を読み、値が設定されていれば `std::atoi` の結果、未設定なら `1` を関数内 `static const int` に保存する。空文字は設定済みなので `atoi("") == 0`。先頭の空白と符号付き10進整数を読み、整数として読めた部分の後ろは無視する。したがって `2abc` は `2`、`  -2tail` は `-2`、`true` や `false`、`abc` は `0` になる。`0`、`1`、負数、0以外の非対応整数は2/4の専用分岐を選ばない。文字列全体の検証や範囲チェック、値に対する警告はない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1918-1920,1984-1992`）。

| 条件 | unset | 専用 RPW kernel を選ぶ値 | 専用 RPW kernel を選ばない例 |
|---|---|---|---|
| SYCL wide MMVQ に到達し、自動 shape 選択が適用されない | `1` | `2` または `4` | 空文字、`0`、`1`、`3`、`-2`、`true`、`abc`。`2abc` は `atoi` が `2` を返すため有効 |
| Battlemage の対象形状で `STRATA_MMVQ_SHAPE_RPW` が有効 | 環境変数が未設定なら自動で `2` | 明示設定がある場合は、上段の parse 結果 | 設定済みなら値が無効でも自動選択を抑止 |

`atoi` は整数範囲を検証しません。範囲外文字列の変換結果は文書化できる保証がないため、特定値として扱いません。

## 有効になる条件

- Strata の SYCL native MMVQ 実装を使用し、ggml type が Q4_K、Q5_K、IQ4_XS のいずれかであること。native MMVQ の type dispatch は `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4220`、各型から wide 経路へ進む箇所は同ファイルの `3457-3469`（Q5_K）、`3692-3779`（IQ4_XS）、`3859-3872`（Q4_K）にある。
- `STRATA_MMVQ_WIDE_K` が未設定または `atoi` 結果が非0であること、列数が1〜8、入力長が QK（256）で割り切れること。満たさない場合 `try_wide` は false を返し、呼び出し側の後続経路を使う（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2066-2083`）。
- 型ごとの先行分岐を通過して wide kernel に到達すること。IQ4_XS は Battlemage の packed cache、pair reuse、ESIMD/XMX 等の条件により `try_wide` より前に別 kernel を起動して return する場合がある（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3776`）。
- `STRATA_MMVQ_WIDE_K_RPW` が `2` または `4` と解釈されること。いずれも wide 経路を通る全対象型に適用される。値は列数に関係なく同じ RPW 判定を使う（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1961-2004`）。
- 未設定時の自動 `RPW=2` は、別変数 `STRATA_MMVQ_SHAPE_RPW` が有効、デバイスが Battlemage、型が Q4_K または Q5_K、列数が4以下で、かつ指定形状に一致する場合に限る。Q4_K は `(n_in,n_out)` が `(2560,6144/10240/12288)` または `(6144,2560)`、Q5_K は `(2560,12288)` または `(6144,2560)`。明示的にこの変数を設定すると値の妥当性にかかわらず自動選択は抑止される。IQ4_XS はこの自動 shape 切替の対象外（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1965-1982`）。Battlemage 判定の実装は GPU であることを確認し、architecture/device 名から Intel Battlemage を判定する（`sycl/include/strata/sycl_queue.hpp:124-157`）。

## 実行時の詳細

Q4_K/Q5_K/IQ4_XS の native MMVQ 関数が `try_wide` に進むと `launch_wide` が `wide_k_rpw()` の値を読み出す。`2` と `4` では RPW をテンプレート引数にした kernel を選び、その他では標準 wide kernel を起動する。列数が2以上で `mmvq_large_grf(s)` が有効なら、標準側は large-GRF property 付き variant を使う。RPW kernel を選んだ場合はこの large-GRF 分岐を通らない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1961-2004`）。

`wide_k_rpw()` の値はプロセス内で初回呼び出し時にキャッシュされ、以後の環境変更は反映されない。一方、自動 shape 選択の条件にある `getenv(...) == nullptr` は `launch_wide` ごとに確認される。`STRATA_MMVQ_SHAPE_RPW` による on/off 判定は `bm_default_on` 内で初回呼び出し時にキャッシュされ、空文字は未設定同様にデバイス既定へ進む。非空なら先頭文字が `'0'` の場合だけ off、それ以外は on。未設定または空文字の既定は Battlemage で on、その他のデバイスで off（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1965-1968`; `sycl/include/strata/sycl_queue.hpp:159-166`）。

RPW kernel と標準 kernel は、それぞれ各出力列・行の積和を計算して出力バッファへ書き込む。Strata ソースには対象変数の有効/無効値を報告するログや無効値時の fallback 警告はない。

## ログと測定値

明示設定による RPW kernel の選択時に、この変数固有のログは出ない。未設定の Battlemage shape 自動選択が発動した場合のみ、stderr に `strata: shape-guarded Q4_K/Q5_K dense row reuse enabled` を出力する（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1975-1981`）。wide 経路の launch error は `launch_check()` が `native MMVQ launch: <error>` 形式の例外にするが、この失敗経路は RPW 値固有ではない（同ファイル `2320-2333`）。この変数について条件つきで出典を確認できる測定値はない。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1918-1920` — 変数の読み取り、`atoi`、未設定既定値、static cache。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1961-2004` — shape 自動選択、RPW 2/4 kernel と標準 kernel の選択。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2066-2083,3457-3469,3692-3779,3859-3872,4203-4220` — wide 経路の gate、対象型と呼び出し経路。
- `sycl/include/strata/sycl_queue.hpp:124-157,159-166` — Battlemage 判定と `STRATA_MMVQ_SHAPE_RPW` の値判定。
- `sycl/CMakeLists.txt:39` — 対象実装ファイルが SYCL 側の build source であること。
