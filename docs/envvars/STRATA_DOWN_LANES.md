# `STRATA_DOWN_LANES`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

SYCL ポートの grouped expert down カーネルで、1行の計算に参加する lane 数を選びます。SYCL カーネルの work-group は256 work-itemで、lane 数に応じて1 work-group あたりの行数を `256 / lanes` として計算します。既定はコンパイル時定数 `STRATA_EXPERT_LANES` で、ソース内の既定値は8です。gate/up 用の `STRATA_GU_LANES` とは別に down 側だけを指定できます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:886-893,4486-4495,4536-4547`）。

通常の実行経路では、SYCL native expert layout を使う場合に verify 側と remote expert 側から `native_expert_grouped()` が呼ばれます。その関数は down format ごとにカーネルを選び、lane カーネルに入る経路でこの値を参照します（`sycl/src/core/verify.cpp:1450-1464`、`sycl/src/core/remote_experts.cpp:431-442`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5608-5615,5788-5794`）。

## 値と判定

値は `lanes_env()` が `std::getenv()` で読み、`std::atoi()` の結果が4、8、16、32のいずれかなら採用し、それ以外は `kExpertLanes` に戻します。文字列全体の検証はせず、`atoi` が読む先頭の数値部分で判定します。

| 環境変数の値 | 結果 |
|---|---|
| 未設定 | コンパイル時定数 `STRATA_EXPERT_LANES`（このソースの既定は8） |
| `4`, `8`, `16`, `32` | その lane 数 |
| `08`, `+16`, `32tail` | `atoi` の結果が許可値になるため、それぞれ8、16、32 |
| 空文字、数値に変換できない文字列、`0`、`-4`、`5` など | `atoi` の結果が許可値でないため既定値 |

先頭空白や符号は `atoi` の変換規則に従い、変換後の値だけを許可リストと照合します。大文字小文字の比較はありません。未設定と明示的な無効値はいずれも既定値になります。根拠: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4489-4495`。

## 有効になる条件

- SYCL ポートの `native_expert_grouped()` が down 計算を実行し、down format の分岐が `launch_down<T>()` を通る必要があります。
- down format が `kSplit<TD>` の形式で、`STRATA_EXPERT_SPLIT` が有効かつ `STRATA_OLD_IQ_MMVQ` が無効の場合、実装は lane カーネルでなく `launch_down_multi()` を選ぶため、この変数はその呼び出しには使われません。`STRATA_EXPERT_SPLIT` の設定有無は先頭文字が空でなく `0` でもないかで判定されます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3199-3209,4621-4633`）。
- `STRATA_HIP_GFX906` ビルドには専用 down カーネルへ早期 return する分岐があり、該当する実行モードと format（mode 7/8 かつ type 20/42、または mode 1/2/4 かつ type 20/23/42）では lane 選択に到達しません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5764-5785`）。
- `native_expert_grouped()` が down phase を省略する `g_exp_phase == 1` の場合、down カーネルを起動しません（同ファイル `:5758-5763`）。

## 実行時の詳細

`down_lanes()` は関数内 `static const int` として値を保持します。したがって環境変数を読むのは down lane 経路で最初に評価されたときで、その後プロセス内で環境を変更しても再読み込みしません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4489-4495`）。

選ばれた値は `launch_down_lanes()` の switch でテンプレート引数になり、4、16、32の場合は対応する `down_port_km<TD, LN>()`、それ以外（既定の8を含む）は8 lane 版を起動します。`launch_down_port()` は `256 / LN` 行単位で grid を作り、down カーネルを実行します（同ファイル `:4536-4567`）。不正値を理由にする警告やエラー出力はありません。

## 資料との照合

`docs/INTEL.md:570-572` は gate/up と down の lane 組み合わせを比較した記録として、down 4または8を含む設定の verify round 時間を載せ、既定を8/8としています。これは記載された Coder と2つの prompt、各2 runs の実測であり、他の機種やモデルでの速度を保証するものではありません。実装では4/8/16/32を受け付けるため、資料の測定対象は実装が許可する値の一部です。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:886-893` — compile-time の既定 lane 数。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4486-4495` — 値の変換、許可値、static cache。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4536-4567,4621-4633` — lane 別カーネル起動と multi 経路への分岐。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5758-5794` — down 計算、backend 固有経路、down format による dispatch。
- `sycl/src/core/verify.cpp:1450-1464`、`sycl/src/core/remote_experts.cpp:431-442` — native expert grouped 実装の呼び出し元。
- `docs/INTEL.md:570-572` — lane 設定の測定記録。
