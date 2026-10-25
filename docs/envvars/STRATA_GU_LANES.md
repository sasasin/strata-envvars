# `STRATA_GU_LANES`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL ポートの grouped expert kernel において、gate/up 行の計算を1行あたり何 lane で分担するかを選びます。kernel の work-group は256 work-itemで、1グループあたりの行数は `256 / lanes` です。この値は数値計算の分割と reduction の分割に使われます。

## 値と判定

`lanes_env()` は `getenv()` で設定値を読み、`atoi()` で整数変換します。受け付ける値は `4`, `8`, `16`, `32` のみです。それ以外の変換結果はコンパイル時定数 `STRATA_EXPERT_LANES` に戻ります。同定数はビルド時に指定がなければソース内で `8` です。

| 環境変数の状態・値 | lane 数 |
|---|---:|
| 未設定 | `STRATA_EXPERT_LANES`（通常 8） |
| `4`, `8`, `16`, `32` と `atoi()` が変換する文字列 | 変換された値 |
| 空文字、数値に変換できない文字列、許可値以外 | `STRATA_EXPERT_LANES` |

文字列全体の検証はありません。したがって `atoi()` が先頭の数値として4/8/16/32を返す文字列（例: `16junk`, `+16`）も受け付けられます。空白や負号も `atoi()` の変換規則に従いますが、結果が4/8/16/32以外なら既定値です。

## 有効になる条件

- 対象は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の `native_expert_grouped()` が選ぶ grouped expert の gate/up lane kernel です。Strata の全 backend や通常の dense kernel の lane 数を変える設定ではありません。
- gate/up の対象型について `launch_gu_lanes()` が呼ばれる必要があります。`STRATA_EXPERT_SPLIT` 等で multi-entry の `launch_gu_multi()` 経路が選ばれる場合、この値はその呼び出しには使われません。
- K-quant/Q8_0 など `KqSplit<TG>::has` が真の型では、`STRATA_KQ_GU_LANES` が設定されているとそちらの lane 値が使われ、`STRATA_GU_LANES` は選択に使われません。未設定なら `STRATA_GU_LANES` にフォールバックします。
- `STRATA_EXPERT_LANES` をビルド時に別値で定義した場合、その値が未設定時および不正値時の既定値です。実行時値として有効なのは4/8/16/32だけです。

## 実行時の詳細

`gu_lanes()` は `static const int` に値を保存するため、最初の参照時に一度だけ環境を読みます。起動後の環境変更は再評価されません。選択した値に応じて `launch_gu_lanes()` がテンプレート kernel の lane 分割（4/8/16/32）を選び、256 work-item の work-group 内の行数を `256 / lanes` として計算します。設定値のログや無効値の警告はこのコードからは出ません。

`docs/INTEL.md` は lane split の比較として、Coder の2 prompt・各2 runにおける gate/up 8または16 × down 4または8 の verify round が37.7–38.6 msで、既定の8/8を維持したと記載しています。これはその資料に記された条件の測定値であり、他の機器やモデルでの性能を示すものではありません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:886-893` — `STRATA_EXPERT_LANES` の compile-time default と lane 数から work-group 行数を定義。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4486-4495` — 環境変数の `atoi()` 変換、許容値、fallback、static cache。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4496-4499,4526-4534` — `STRATA_KQ_GU_LANES` による優先と lane kernel 選択。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4501-4511,4588-4604` — lane 数に応じた行数と GU kernel launch、multi-entry 経路への分岐。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5608-5613,5686-5695` — grouped expert 実装から gate/up kernel を呼ぶ経路。
- `docs/INTEL.md:570-572` — lane split の測定記録と既定値に関する記述。
