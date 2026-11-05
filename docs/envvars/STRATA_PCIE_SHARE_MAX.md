# `STRATA_PCIE_SHARE_MAX`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

CPU pool の速度から PCIe の expert share (`pcie_frac`) を自動計算するとき、その値の上限を指定します。自動計算の開始値と、その後の decode window による更新、および自動 layer split の後段 GPU 向け share に使われます。`--pcie-frac` で値を固定した場合は自動計算を使わず、この変数も参照されません。

## 値と判定

| 環境変数 | 判定 |
|---|---|
| 未設定 | discrete GPU かつ `STRATA_DEFAULTS=026` でない場合は上限 `0.95`。それ以外は `0.60`。 |
| 空文字 | 未設定と同じ既定値。 |
| 非空文字列 | `std::atof` で数値変換し、`0.10..1.0` に clamp。 |

`atof` のため文字列全体の厳密な検証はありません。数値として読めない文字列は `0` になり、上限は `0.10` です。`0.05` や負数も `0.10`、`0.10` はそのまま、`0.95` はそのまま、`1` やそれ以上は `1.0` になります。数値の後ろに続く文字は変換を止めた後に検査されません。空白・指数表記等は `atof` の変換規則に従います。環境変数を読む箇所で不正値の警告やエラーは出しません。

未設定時の `discrete` 判定は `spill_discrete_gpu()` によります。Metal build では `spill_allowed(true, false)`、その他では現在の GPU の `integrated` 属性を使った `spill_allowed(false, integrated)` の結果です。したがって単に CUDA/HIP build かどうかだけで既定値は決まりません。

## 有効になる条件

- `--pcie-frac` を省略し、自動 share 設定が選ばれた経路でのみ有効です。CLI 値は `std::atof` で読み込まれ、`pcie_frac` の初期値 `-1.0` を非負値で置き換えるため、その場合は後続の環境変数ベース自動計算を通りません。
- 自動設定には PCIe 帯域 probe 成功や pack/backend の条件があります。CUDA の native pack は single GPU で自動化され、layer split では discrete GPU かつ `STRATA_DEFAULTS=026` でない場合に既定で自動化されます。split 自動化は `STRATA_PCIE_AUTO_SPLIT` の非空値で `atoi(value) != 0` に明示設定できます。HIP は gfx1200/gfx1201 が対象 arch の既定経路で、他の HIP arch は `STRATA_PCIE_FRAC_DEFAULT=auto` が必要です。`STRATA_PCIE_FRAC_DEFAULT=old` は自動更新を無効にします。関連条件: `src/program/generate.cpp:2445-2456,2461-2469,2498-2509,4711-4755`。
- Decode serve 側の `PcieAuto` が動くには、`pcie_frac_auto` が有効で、全 expert が VRAM に resident ではなく、`--batch` が 0、peer GPU を使わず、single stage または split 自動化が有効である必要があります。満たさない場合は値が設定されていてもこの自動更新には使われません (`src/program/generate.cpp:12607-12617`)。
- `STRATA_PCIE_START=old` は CUDA の pool-rate を使った開始値の設定を抑えますが、その後の `PcieAuto` 更新は別条件を満たせば行われます。HIP は開始値更新が `STRATA_PCIE_START=new` の opt-in です (`src/program/generate.cpp:12538-12554`)。
- `STRATA_PCIE_SHARE_MAX` は `STRATA_PCIE_K_RULE` が選ぶ pool 係数 `k` や、`STRATA_PCIE_AUTO_SPLIT` が決める自動化の可否を変えません。`STRATA_DEFAULTS=026` は明示されたこの変数を無効化せず、未設定時の既定上限を `0.60` にします。

## 実行時の詳細

`pcie_share_max()` 内の `static const double` が初回呼び出し時に helper を実行し、値をプロセス内で cache します。プロセス起動後に環境を変更しても再評価されません (`src/program/generate.cpp:2693-2701`)。初回呼び出しは自動設定が有効な場合の開始 share 計算、または decode window 後の自動更新で起きます (`src/program/generate.cpp:12538-12554,12621-12646`)。

上限は `link / (link + k * pool_rate)` から得た比率を `0.05` 刻みに丸めた値に適用されます。比率には別途 `0.10` の下限があります。したがって上限を `0.10` 未満には設定できず、上限を `1.0` より大きくもできません。初期の自動 share と後続更新は `drive.d.pcie_num` に反映され、split 後段は各 stage の probe link に基づき個別計算されます (`include/strata/core/pcie_share_rule.hpp:24-28,45-49`; `src/program/generate.cpp:12550-12556,12628-12646`)。

通常の値 parse に対するログや終了・失敗経路はありません。自動 share の開始時には `strata serve: PCIe share: start ...`、decode 後に値が変わった場合は `strata serve: PCIe share: the CPU pool takes ...`、split 後段の更新時は `strata serve: PCIe share: stage ...` が stderr に出ます。後続更新は最初の 48 window、その後 96 window ごとに pool rate を集計し、最大 3 回です。300 未満の missed experts では判断を保留し、2000 window までに十分な missed experts がなければ更新を止めます (`src/program/generate.cpp:2724-2747,12621-12646`)。

## 根拠

- 候補名の全参照は `include/strata/core/pcie_share_rule.hpp:4-5,45-49`、`src/program/generate.cpp:2693-2701,2698-2699` および `docs/DETAILS.md:1050`。実際の環境読み取りは `generate.cpp:2699` だけで、共通 helper や動的な変数名経由の別読み取りはありません。
- clamp と unset fallback: `include/strata/core/pcie_share_rule.hpp:45-49`。既定値に使う discrete GPU / master switch 判定: `src/program/generate.cpp:276-289`, `include/strata/core/defaults_026.hpp:21-29`。
- CLI 優先と自動 share の選択: `src/program/generate.cpp:879-880,3574,4024-4026,4711-4755`。
- 開始 share、更新条件、出力: `src/program/generate.cpp:12538-12556,12607-12646`。share の丸め式: `include/strata/core/pcie_share_rule.hpp:24-28`。
- `docs/DETAILS.md:1050` は自動 PCIe share の概要と RTX PRO 6000 の測定値を記載しています。そこに記載の値は当該環境の資料上の測定であり、この調査で再測定していません。
