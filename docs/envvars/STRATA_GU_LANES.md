# `STRATA_GU_LANES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや GPU driver の環境変数動作は対象外。

## 役割

SYCL 側の grouped expert gate/up lane kernel で、1 行の dot product を何 lane で分担するかを選びます。選択値は 4 / 8 / 16 / 32 のいずれかで、256 work-item の work-group に含める行数も `256 / lanes` になります。これは起動する kernel のテンプレート引数と行の分割を変える設定です。性能や数値結果の差はこの調査では測定していません。

環境変数を読む実装は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` にあります。この `.dp.cpp` は SYCL 向け実装で、CUDA backend の環境変数設定ではありません。

## 値と判定

`lanes_env()` は `std::getenv(name)` で値を取得し、設定されていれば `std::atoi()` に渡します。変換結果が 4、8、16、32 のときだけ採用し、それ以外は compile-time の `STRATA_EXPERT_LANES` に戻します。同 macro は未定義なら 8 です。文字列全体の検証はなく、`atoi` が認識する先頭の整数部分で判定します。

| `STRATA_GU_LANES` | 判定結果（`STRATA_KQ_GU_LANES` による上書きがない gate/up 経路） |
|---|---|
| unset | compile-time `STRATA_EXPERT_LANES`。macro 未定義時は 8 |
| `4`, `8`, `16`, `32` | それぞれの lane 数 |
| 空文字、`0`、`3`、`-4`、`64`、整数に変換できない文字列 | compile-time `STRATA_EXPERT_LANES` |
| `16xyz`、` 8tail`、`+4rest` | `atoi` の結果が許可値なら採用（例ではそれぞれ 16、8、4） |

無効値に対する警告やエラー出力はありません。`atoi` の戻り値を許可値と比較するだけで、範囲 clamp や数値文字列全体の parse はしません。compile-time macro が独自値に設定されている場合、それが helper の fallback になります（実装上の既定は 8）。ただし dispatcher が明示 case を持つのは 4 / 16 / 32 だけで、その他は 8 を起動します。したがって macro を許可値以外に設定したビルドでは、helper の fallback 値ではなく dispatcher の default である 8 が使われます。

## 有効になる条件

- SYCL の `native_expert_grouped` が grouped expert 処理を行い、その gate/up 計算が `launch_gu_lanes()` に到達する必要があります。通常の SYCL grouped expert 経路で使われます。モデルの format/layout が native expert 経路に入らない場合、この kernel を通らず、変数は効果を持ちません。
- gate/up type が `kSplit` 形式でない場合は lane kernel を使います。`kSplit` 形式でも、旧 kernel 選択 (`g_old_kernels`) または multi-entry split 無効 (`!g_split_multi`) の場合は lane kernel を使います。multi-entry kernel を選ぶ場合は `STRATA_GU_LANES` による lane 選択を通りません。
- `KqSplit<TG>::has` が true の gate/up type では `launch_gu_lanes()` が `STRATA_GU_LANES` ではなく `kq_gu_lanes()` を選びます。`STRATA_KQ_GU_LANES` が設定されていると、その `atoi` 結果（無効なら compile-time fallback）が優先され、`STRATA_GU_LANES` はこの type について読まれません。`STRATA_KQ_GU_LANES` が unset の場合は `STRATA_GU_LANES` に戻ります。該当する `KqSplit` type は Q4_K、Q5_K、Q6_K、Q5_1、Q8_0 および trellis type 144–146 です。
- `STRATA_HIP_GFX906` ビルドでは一部 AMD native type が専用 AMD kernel 分岐を通り、そこではこの lane selector を使いません。AMD type に該当しない format が CUDA-layout 側の grouped kernel に進む場合は lane selector が使われ得ます。

## 実行時の詳細

値は `gu_lanes()` 内の function-local `static const int` として初回評価時に cache されます。したがって、プロセス起動後に環境を書き換えても、初回評価後は再読み取りされません。lane 数の switch は 4、16、32 を明示し、それ以外を 8 に dispatch します。helper の検査で許可されるのは 4 / 8 / 16 / 32 なので、8 はこの default 分岐を通ります。

この値によって gate/up lane kernel の `LN` テンプレート値が決まり、kernel 内の 256 work-item から計算する行数は `ROWS = 256 / LN` です。SYCL launch の grid 幅もこの行数から計算されます。Strata 側にこの変数の設定を知らせる専用ログ、無効値の警告、またはエラー終了経路は見当たりません。launch 自体の失敗は通常の SYCL kernel launch / check 経路に委ねられますが、環境変数の parse 失敗として報告されるものではありません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:887-894` — `STRATA_EXPERT_LANES` の compile-time 既定値と `kExpertLanes`。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4487-4500` — `lanes_env()` の `getenv` / `atoi` / 許可値判定、`gu_lanes()` の cache、`STRATA_KQ_GU_LANES` の fallback。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4502-4512,4527-4535` — `ROWS` による行数・grid 計算と gate/up の lane dispatch。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:1863-1881,1974-2032` — K-quant / Q5_1 / Q8_0 / trellis の `KqSplit` 経路。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4588-4606` — `kSplit` と旧 kernel / multi-entry 選択による lane kernel 到達条件。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5609-5635,5677-5696` — `native_expert_grouped` 内の実行経路、SYCL での AMD-only option 注記、HIP gfx906 の AMD format 分岐と共通 gate/up launch。
- `sycl/src/core/remote_experts.cpp:431-442`、`sycl/src/core/verify.cpp:1513-1523` — native expert layout の grouped kernel 呼び出し元の例。
