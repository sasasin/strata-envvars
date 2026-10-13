# `STRATA_DOWN_LANES`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリやドライバーが読む同名変数の意味は含めない。

## 役割

SYCL backend の grouped expert kernels において、down projection の1行を計算する際に協調する lane 数を選びます。ゲート/アップ projection 用の `STRATA_GU_LANES` とは別設定です。1 work-group は256 work-itemで、選択した lane 数に応じて一度に処理する down の行数が `256 / lanes` になります。

## 値と判定

値は `std::atoi` で整数に変換し、その結果が `4`、`8`、`16`、`32` のどれかなら採用します。その他はコンパイル時既定値 `kExpertLanes` に戻ります。このソースでは `STRATA_EXPERT_LANES` が別途定義されない場合に `kExpertLanes` は8です。

| 環境変数の状態・値 | 採用される lane 数（通常の既定ビルド） |
|---|---:|
| 未設定 | 8（`kExpertLanes`） |
| `4` / `8` / `16` / `32` | それぞれ4 / 8 / 16 / 32 |
| 空文字、`0`、負数、その他の整数 | 8（変換結果が許可値でないため） |
| `16junk`、` 16tail` など | `atoi` が読み取る先頭の整数が許可値なら採用（例では16） |
| 数字で始まらない文字列 | `atoi` の結果0となり、8に戻る |

文字列全体の妥当性や後続文字は検査しません。大文字小文字の比較もありません。数値変換後の値だけを許可リストと照合します。

## 有効になる条件

- 対象は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` にある SYCL grouped expert の down lane kernel です。CUDA/HIP の実装をこの変数が制御する根拠は見つかりませんでした。
- down kernel が lane-dispatch 経路を使う場合に有効です。`kSplit<TD>` が偽の場合、または分割形式でも `g_old_kernels` が真か `g_split_multi` が偽の場合は `launch_down_lanes()` を使います。
- 分割形式で `g_old_kernels` が偽かつ `g_split_multi` が真の場合は `launch_down_multi()` に進み、この環境変数の lane dispatch は通りません。

## 実行時の詳細

`down_lanes()` は関数内の `static const int` として初回評価時の値を保存します。したがって、値はプロセス内で初めて down lane dispatch に到達したときに読み込まれ、その後プロセス実行中に環境を書き換えても再読込されません。

採用値に応じて `launch_down_port<TD, LN>` の `LN` を4、8、16、32から選び、SYCL kernel `native_down_kernel<TD, LN>` を起動します。kernel は各出力行について lane 数分の work-item で行列積を分担して reduction します。候補値は行あたりの並列度と work-group ごとの処理行数を変える設定であり、ソースだけから特定値が常に高速とはいえません。

## 文書・測定資料との照合

`docs/INTEL.md` は `STRATA_GU_LANES` / `STRATA_DOWN_LANES` の実行時選択肢を4/8/16/32と記載し、Coder の2 prompt・各2 runで、gate/up 8または16と down 4または8の組み合わせが verify round あたり37.7–38.6 msだったと報告しています。同資料では組み合わせ間の tok/s 差に draft acceptance の違いが含まれるとしています。これは資料に記された条件での測定であり、他の構成での性能を示すものではありません。ソース上の lane 選択と既定8/8は資料の記載と一致します。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:794-801` — コンパイル時 lane 数と、未定義時の8という既定値。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4100-4109` — `atoi`、許可値、fallback、初回評価後の static cache。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4134-4156` — lane 数から down kernel のテンプレート引数を選び起動。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:1985` 以降 — `native_down_kernel` の既定 lane 数と処理実装。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4210-4222` — lane dispatch と multi kernel 経路の選択。
- `docs/INTEL.md:545-547` — lane 選択肢、既定設定、測定条件と結果。
