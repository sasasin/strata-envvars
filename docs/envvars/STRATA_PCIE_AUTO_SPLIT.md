# `STRATA_PCIE_AUTO_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata serve` の GPU 層分割で、probe したリンク帯域と CPU pool の実測速度から PCIe share を更新する PcieAuto を許可するか決めます。層分割でこの更新経路が設定されるのは native pack の probe 成功時です。許可されると CUDA0 の share に加えて、link probe が成功した後段 stage の share もその stage の probe 値を使って更新します。無効の場合、起動時 probe から決めた固定 share を使います。対象は層分割の自動調整の可否であり、PCIe share 自体や PCIe 転送を単独で有効化する変数ではありません（`engine/src/program/generate.cpp:2833-2844,5566-5576,6711-6719,15003-15010,15032-15040`）。

## 値と判定

`pcie_auto_split_ok()` は `std::getenv` の結果を helper に渡し、helper は非 null かつ空文字でない場合だけ `std::atoi(env) != 0` を返します。したがって数値文字列全体の検証はなく、`atoi` が先頭から変換した値が 0 かどうかで決まります。空白だけ、`true`、`0anything` は 0 となり無効、`1anything` や `-1` は非 0 となり有効です。大文字小文字の比較はありません。空文字は明示値として扱わず、unset と同じ既定判定に進みます（`engine/include/strata/core/pcie_share_rule.hpp:34-40`）。

| build / 条件 | unset または空文字 | 非空で `atoi` が非 0 | 非空で `atoi` が 0 |
|---|---|---|---|
| CUDA（`STRATA_USE_HIP` 未定義）、離散 GPU、`STRATA_DEFAULTS=026` ではない | 有効 | 有効 | 無効 |
| HIP build、統合 GPU、または `STRATA_DEFAULTS=026` | 無効 | 有効 | 無効 |

非空の明示値は build・GPU 種別・`STRATA_DEFAULTS=026` による既定値を上書きします。ただし、後述の backend、GPU 世代、CLI、モデル状態などの PcieAuto 条件までは上書きしません（`engine/include/strata/core/pcie_share_rule.hpp:34-40`; `engine/src/program/generate.cpp:2835-2844`）。

## 有効になる条件

- `--layer-split` によるサーバーの層分割経路であること。parser は `--layer-split` を `--serve` 専用として検証します（`engine/src/program/generate.cpp:4065,4803-4805,4848-4853`）。
- `--pcie-frac` が指定されていないこと。指定値があると `o.pcie_frac < 0.0` の自動既定値・PcieAuto 設定ブロックを通らず、明示 share が優先されます（`engine/src/program/generate.cpp:4057,5535-5536`）。
- native pack で PCIe probe が成功し、pack / backend に応じた PcieAuto の開始条件も満たすこと。`STRATA_PCIE_FRAC_DEFAULT=old` では PcieAuto を無効にします。non-native/canonical pack の分岐では `pcie_frac_auto` が `o.layer_split.empty()` に設定されるため、層分割では PcieAuto になりません。HIP では gfx12 の既定経路か、許可された HIP architecture の経路が必要です（`engine/src/program/generate.cpp:5535-5555,5566-5579`; HIP architecture 判定は同 `:2847-2857,2880-2912`）。
- モデルに GPU 非 resident expert があり、`--batch` が 0、`--peer-device` が未指定であること。これらを満たさない場合 `PcieAuto` は作られず、share 更新はありません（`engine/src/program/generate.cpp:15003-15010`）。
- 層分割が最終的に複数 stage として残ること。`--split-skip-if-fits` などで分割が解消される場合は後段 stage の個別 share 更新はありません（分割後の `multi_gpu` 判定: `engine/src/program/generate.cpp:4856,5908,6479`）。

未設定時の既定は `STRATA_USE_HIP` の build macro、`spill_discrete_gpu()` が得る GPU の統合属性、`qwen_defaults_026()` の結果で決まります。`STRATA_DEFAULTS=026` は既定を無効にしますが、非空の `STRATA_PCIE_AUTO_SPLIT` は helper 内で先に評価されるため明示値が優先します（`engine/src/program/generate.cpp:327-338,2835-2844`; `engine/include/strata/core/defaults_026.hpp:15-29`）。

## 実行時の詳細

値は `pcie_auto_split_ok()` 内の function-local `static const bool` 初回評価時に読み取られ、以後そのプロセス内で cache されます。実行中に環境値を変更しても再評価されません（`engine/src/program/generate.cpp:2835-2845`）。

層分割で自動 share の条件が成立すると、native pack では CUDA0 と後段 stage のリンクを probe します。PcieAuto が on の場合、decode window の pool 時間と missed expert 数を集計し、最初の判定は 12 window 後、その後は 48 window ごとです。300 件未満の miss では測定を先送りし、測定可能な更新は最大 3 回です。更新時は CUDA0 の share と、link probe が正の後段 stage の share をそれぞれの link 値と pool rate から算出し、`pcie_num` に反映します。pipelined decode では verdict ごとにも更新関数を呼びます（`engine/src/program/generate.cpp:3127-3149,5566-5576,6711-6719,15012-15042,22465,23151`）。

serve の request 引数 `pcie_frac` は 0〜1 に clamp されます。その request の share が起動時 share と異なる間は、自動更新関数は測定値を mark するだけで、その request の share を上書きしません（`engine/src/program/generate.cpp:18859-18870,18922,15015-15027`）。

この share は各 layer-window の distinct miss のうち PCIe lane へ割り当てる割合です。常駐 expert は対象外で、残りの miss は CPU 側に残ります。対象 layer が PCIe source を使えない場合も PCIe share は適用されません（`engine/src/core/expert_source.cpp:5475-5485,5491-5500,5543-5545`）。

## ログと測定値

この変数自体の on/off を報告する専用ログや、無効値への専用警告・終了経路はありません。probe 成功時は `strata generate: layer split: CUDA%d PCIe probe %.1f GB/s (best of %s) -> pcie_frac %.2f` が出ます。PcieAuto の開始 share を変更する条件では `strata serve: PCIe share: start ...`、測定による変更時には `strata serve: PCIe share: the CPU pool takes ...` と stage ごとの `strata serve: PCIe share: stage ...` が stderr に出ます（`engine/src/program/generate.cpp:5566-5576,6712-6719,14913-14929,15021-15040`）。

`docs/DETAILS.md:1206` は RTX PRO 6000 の 2 枚・各 12 GB の層分割で decode +12% と記載しています。これは同資料に記された測定値であり、この調査で再測定した結果ではありません。

## 根拠

- `engine/include/strata/core/pcie_share_rule.hpp:34-40` — 値の変換と unset 時の既定規則。
- `engine/src/program/generate.cpp:2833-2845` — HIP/CUDA build 判定、環境値の読み取りと static cache。
- `engine/src/program/generate.cpp:5535-5579` — CLI share 優先、probe、backend 等による PcieAuto 設定。
- `engine/src/program/generate.cpp:15003-15042` — 実行条件、pool の測定と各 stage share の更新。
- `engine/src/core/expert_source.cpp:5475-5500,5543-5545` — miss への share 適用条件。
- `docs/DETAILS.md:1206` — 資料記載の測定値。
