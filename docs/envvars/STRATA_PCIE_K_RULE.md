# `STRATA_PCIE_K_RULE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

PCIe 経由で GPU に渡す expert miss の割合を自動調整する `PcieAuto` の式にある、CPU pool 速度 `R` の係数 `k` のルールを選ぶ。ルールが有効なとき、pool が遅いほど `k` を 1.85 から 0.8 へ下げる。無効時は常に 1.85。自動調整率は `link / (link + k * R)` を 0.05 刻みに丸め、下限 0.10 と上限の間に収めるため、他の条件が同じなら小さい `k` は PCIe 側の割合を増やす。これは GPU と CPU のどちらに miss を割り当てるかを変える。`docs/DETAILS.md:1206` はこの分担変更に伴い出力の最下位 bit が変わると報告している（同資料の測定値で、この調査では再測定していない）（`engine/src/program/generate.cpp:3105-3107, 3145-3149`; `engine/include/strata/core/pcie_share_rule.hpp:20-31`）。

自動分担が有効な CUDA / HIP の serve 経路で使われる。`--pcie-frac` により自動分担が設定されない経路、または後述の適用条件を満たさない経路では、この係数による更新はない（`engine/src/program/generate.cpp:5535-5579, 15003-15010`）。

## 値と判定

`generate.cpp` が `std::getenv` で値を読み、`pcie_k_rule_default()` に渡す。関数は未設定または空文字なら機器状態に応じた既定値を返し、それ以外は `std::atoi(env) != 0` で判定する。文字列全体の妥当性検査はなく、整数として読める先頭部分だけが `atoi` の判定に使われる（`engine/src/program/generate.cpp:3105-3107`; `engine/include/strata/core/pcie_share_rule.hpp:42-47`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| 離散 GPU、`STRATA_DEFAULTS` が `026` でない | ON（可変 `k`） | `1`, `-1`, `1tail`（`atoi` が非ゼロ） | `0`, `0tail`, `true`, 空文字ではない非数値文字列（`atoi` が 0） |
| 統合 GPU、または `STRATA_DEFAULTS=026` | OFF（`k=1.85`） | `1`, `-1`, `1tail` など（明示値が既定に優先） | `0`, `0tail`, `true` など（`atoi` が 0） |

空文字は「設定あり」としては扱われず、unset と同じ既定値になる。先頭の空白や符号は `atoi` に従い、数値の後ろの文字列は値の判定に影響しない。たとえば ` 1x` は非ゼロ、` 0x` はゼロとして扱われる。小数文字列 `0.5` は `atoi` が `0` を返すため無効、`-0` も無効。範囲 clamp はなく、値は 0 / 非ゼロに二値化される（`engine/include/strata/core/pcie_share_rule.hpp:44-46`）。

既定では `spill_discrete_gpu()` の結果が離散 GPU で、かつ `qwen_defaults_026()` が false の場合だけ ON。`STRATA_DEFAULTS=026`（または同関数が受け付ける `0.2.6`, `v0.2.6`）は既定を OFF にするが、この環境変数に非空の明示値があれば先に評価されるため、`STRATA_PCIE_K_RULE=1 STRATA_DEFAULTS=026` ではルールが ON になる（`engine/src/program/generate.cpp:327-338, 3105-3107`; `engine/include/strata/core/pcie_share_rule.hpp:44-46`; `engine/include/strata/core/defaults_026.hpp:21-29`）。

## 有効になる条件

- `PcieAuto` が使われるため、起動時に自動 PCIe share が有効で、PCIe 帯域の probe が成功していること。`--pcie-frac` は `atof` で変換され、変換後の値が 0 以上なら自動設定分岐を外すため、環境変数による係数も使われない（負値ならこの条件だけでは分岐を外さない）（`engine/src/program/generate.cpp:4057, 5535-5579`）。
- PCIe share の更新対象となる expert miss があること。全 expert が GPU cache に常駐している場合、batch 実行、peer-device 経路などでは `PcieAuto` の有効化条件から外れる（`engine/src/program/generate.cpp:14932-14933, 15003-15010`）。
- layer split で各 stage の share も更新する場合、`STRATA_PCIE_AUTO_SPLIT` の判定が ON であること。未設定時は離散 CUDA GPU かつ `STRATA_DEFAULTS=026` でない場合に ON、HIP は OFF。明示値は空でなければ `atoi != 0` で判定される（`engine/src/program/generate.cpp:2833-2844`; `engine/include/strata/core/pcie_share_rule.hpp:34-40, 44-46`）。
- HIP の単一 GPU 自動 share は gfx12 既定、または `STRATA_PCIE_FRAC_DEFAULT=auto` 等で `pcie_auto_fork_arch_ok()` が有効になる対象であること。通常の未対応 HIP 部品ではこの変数を設定しただけでは自動分担が始まらない。`STRATA_PCIE_FRAC_DEFAULT=old` は測定後の自動更新を無効にする（`engine/src/program/generate.cpp:2893-2912, 5570-5576`）。
- `STRATA_PCIE_START` は初期 share の式を使うかどうかを決めるが、後続の pool 測定による `PcieAuto` 更新の可否とは別。CUDA は未設定または `old` 以外で初期式を使い、HIP は `new` のときだけ使う（`engine/src/program/generate.cpp:14913-14928`）。

## 実行時の詳細

読み取りは `pcie_pool_k()` 内の関数ローカル `static const bool` の初期化時に一度だけ行われ、そのプロセス内ではキャッシュされる。初期化自体も `pcie_pool_k()` が呼ばれたときに限られる。呼び出しは自動 share の初期値計算（条件が揃う場合）または測定後の share 更新から発生するため、該当経路に入らなければ値は読まれない。実行中に環境を変えてもキャッシュ後の判定には反映されない（`engine/src/program/generate.cpp:3105-3107, 14913-14928, 15015-15020, 15035-15036`）。

ルールが ON の場合、測定された pool rate `R` が 30 GB/s 以上なら `k=1.85`、12 GB/s 以下なら `k=0.8`、その間は線形補間する。OFF の場合は `R` によらず `k=1.85`。share は `link / (link + k * R)` を 0.05 刻みに丸め、下限 0.10、上限 `STRATA_PCIE_SHARE_MAX`（設定時 0.10..1.0 に clamp、未設定時は離散 GPU かつ master switch 無効で 0.95、それ以外で 0.60）に制限する（`engine/include/strata/core/pcie_share_rule.hpp:16-31, 59-63`; `engine/src/program/generate.cpp:3101-3107, 3145-3149`）。

自動更新は decode window 後に pool の miss 処理時間を集計する。初回は 12 window、その後は 48 window ごとに評価し、300 miss 未満なら測定を延期（2000 window まで不足なら停止）。正常に評価できた場合は最大 3 回更新し、丸め後の差が 0.025 未満なら share を変更しない。layer split では各後続 stage の link 測定値にも同じ `k` を適用する（`engine/src/program/generate.cpp:3127-3149, 15003-15010, 15015-15040`）。

## ログと測定値

この環境変数だけを示す専用ログはない。条件を満たして初期 share を計算した場合は `strata serve: PCIe share: start ...`、測定後に share が変化した場合は `strata serve: PCIe share: the CPU pool takes ...` が stderr に出る。layer split の後続 stage で計算された場合は `strata serve: PCIe share: stage ...` が出る（`engine/src/program/generate.cpp:14923-14928, 15021-15040`）。

probe 失敗時は `strata generate: PCIe probe failed -> pcie_frac default ...` が出て probe ベースの自動更新は設定されない。測定時に pool rate / blob bytes / link の必要条件を満たさない場合、または share が 0.025 未満しか変わらない場合は更新ログが出ない（`engine/src/program/generate.cpp:5566-5579, 3144-3149`）。

`docs/DETAILS.md:1206` も、離散カードでの `k` の低下、0.95 の上限、`STRATA_PCIE_K_RULE=0` による旧ルール復帰を説明しており、現行の実装と一致する。同表の速度値・品質値は資料に記載された測定値であり、この調査では再測定していない。

## 根拠

- `engine/src/program/generate.cpp:327-338` — 離散 / 統合 GPU の判定元。
- `engine/src/program/generate.cpp:3101-3107` — ceiling と対象環境変数の読み取り・cache。
- `engine/src/program/generate.cpp:5535-5579` — CLI 指定、形式・probe・backend による自動 share の有効化。
- `engine/src/program/generate.cpp:14913-14931, 15003-15040` — 初期 share、測定更新、結果ログと stage 適用。
- `engine/include/strata/core/pcie_share_rule.hpp:20-31, 42-63` — `k` の計算、値判定、既定値、share ceiling。
- `engine/include/strata/core/defaults_026.hpp:21-29` — master switch の値と cache。
- `docs/DETAILS.md:1206` — 実装と照合した設計資料。
