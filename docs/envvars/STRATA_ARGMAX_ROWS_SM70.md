# `STRATA_ARGMAX_ROWS_SM70`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

compute capability major 7 の NVIDIA GPU で、検証 window と MTP draft が使う greedy argmax を、通常の1ブロック sampler から複数ブロックの `argmax_rows` に切り替える opt-in です。コードは major 7 を条件にしているため、名前に `SM70` とありますが、判定自体は 7.x 全体です。資料にある性能値は V100（sm_70）での contributor 測定とされています。

## 値と判定

CUDA 実装は `std::getenv()` で設定有無を調べ、`std::atoi(e) != 0` で値を判定します。文字列全体の数値検証はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | `atoi` が 0 を返すため無効 |
| 数値変換結果が 0 | 無効。例: `0`, `-0`, 数字で始まらない文字列 |
| 数値変換結果が 0 以外 | 有効。例: `1`, `2`, `-1`, `1tail` |

`atoi` の通常の規則により、先頭の空白と符号は数値変換に含まれ、数値の後ろにある文字は判定されません。大文字小文字は関係しません。

この変数が有効でも、`STRATA_MULTI_BLOCK_ARGMAX` が `0` 相当なら最終判定は無効です。同変数は未設定なら有効、設定時は `atoi(value) != 0` です。従って、たとえば `STRATA_ARGMAX_ROWS_SM70=1` と `STRATA_MULTI_BLOCK_ARGMAX=0` の組み合わせでは従来経路を使います。

## 有効になる条件

- CUDA 実装であること。HIP コンパイルでは `argmax_rows_wanted()` は常に false を返します。
- 現在の CUDA device の compute capability major が 7 であること。device 取得または major 属性取得に失敗した場合も false です。
- この変数の `atoi` 結果が非ゼロであること。
- `STRATA_MULTI_BLOCK_ARGMAX` が有効であること。

major 8 は別の既定経路で `argmax_rows_wanted()` が true になりますが、この変数は参照されません。SYCL 側の同名関数は major 8 のみを条件とし、この変数を読みません。そのため SYCL の major 7 ではこの変数による切り替えはありません。Metal の stub は関数呼び出し時に未実装エラー経路へ進みます。

## 実行時の詳細

`argmax_rows_wanted()` の GPU 判定とこの変数の値は、関数内 `static const bool` として初回評価時にキャッシュされます。`STRATA_MULTI_BLOCK_ARGMAX` も別の関数内 static にキャッシュされます。初回評価後にプロセス環境を変更しても、これらの判定は再評価されません。ログ出力はありません。

切り替えが選ばれると、`argmax_rows()` は語彙方向を最大128ブロックに分割して各行の最大値と token ID を求めます。tie は小さい token ID を採るよう `arg_block()` で比較し、全値が `-inf` の場合は one-block kernel と同様に ID 0 を出力します。これは greedy pick の経路であり、ユーザーが sampling や penalty を指定したリクエストの最終サンプリング全般を置き換えるものではありません。Verifier は window 内の既定 greedy pick を記録し、sampling / penalty が必要な場合は replay 後にリクエスト設定で改めてサンプリングします。

呼び出し箇所は、MTP の draft logits に対する pick と、Verifier の window logits に対する pick です。coupled draft sampling の分岐はこの判定より前に専用 sampler を呼んで戻るため、この変数による `argmax_rows` への切り替えを通りません。

## 根拠

- `src/kernels/cuda/verify_kernels.cu:946-975`: 依存する `STRATA_MULTI_BLOCK_ARGMAX` の既定値と変換、CUDA/HIP 分岐、major 7 の環境変数判定、major 8 の既定判定、static cache。
- `src/kernels/cuda/verify_kernels.cu:808-854,890-898`: 複数ブロック argmax の実装、tie / 全 `-inf` の出力、最大ブロック数を使う launch。
- `src/core/mtp.cpp:1198-1219`: coupled sampling の早期 return、MTP draft pick の切り替え、および multi-block head ops による top-probability 経路。
- `src/core/verify.cpp:2247-2259`: Verifier の greedy pick 切り替えと、後段で request sampling / penalty を扱う説明。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:1573-1599`: SYCL の同名判定が major 8 のみで、`STRATA_ARGMAX_ROWS_SM70` を読まないこと。
- `metal/src/engine/stubs.cpp:135`: Metal stub の関数実装。
- `docs/NVIDIA_V100.md:93-103`: contributor の V100 測定として、sm_7x の複数ブロック greedy pick と「+0.7-0.8% decode」を記載。モデル、測定手順、実行条件の詳細はこの表にないため、数値は一般化できない。
