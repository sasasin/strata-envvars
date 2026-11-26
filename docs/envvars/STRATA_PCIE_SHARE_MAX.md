# `STRATA_PCIE_SHARE_MAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU pool と GPU 間の expert 転送を分担する PCIe share の自動調整に、上限を与える。`generate.cpp` の `pcie_share_max()` がこの値を一度取得し、初期 share の算出および decode 中の自動更新を clamp する。固定 share を使う経路そのものを有効化する変数ではなく、明示的な `--pcie-frac` の値も変更しない（`engine/src/program/generate.cpp:3101-3104, 3144-3149, 14913-14929, 15004-15040`）。

## 値と判定

`std::getenv` の結果を `pcie_share_ceiling()` に渡す。未設定 (`nullptr`) または空文字 (`env[0] == '\0'`) なら既定値を使う。空でない値は `std::atof` で数値変換し、結果を `[0.10, 1.0]` に clamp する。文字列全体の妥当性検査や parse 成功確認はないため、例として `0.4junk` は `0.4`、`0anything`・`true`・`false`・非数値文字列は変換結果 `0` から下限 `0.10`、`-1` も `0.10`、`0` は `0.10`、`2` は上限 `1.0` になる。`0.7` は `0.7`。大文字小文字比較は行わず、数値の後ろに続く文字列も検査しない（`engine/include/strata/core/pcie_share_rule.hpp:59-63`）。

| 条件 | unset / 空文字 | 設定時に使われる上限 | 備考 |
|---|---:|---:|---|
| discrete GPU かつ `STRATA_DEFAULTS=026` ではない | `0.95` | `atof` の結果を `0.10..1.0` に clamp | discrete 判定は `spill_discrete_gpu()` による（`engine/src/program/generate.cpp:326-338`）。 |
| integrated GPU、または `STRATA_DEFAULTS=026` | `0.60` | 同上 | 明示値は master switch より優先する。`STRATA_DEFAULTS` 自体は `026`, `0.2.6`, `v0.2.6` の完全一致で有効（`engine/include/strata/core/defaults_026.hpp:21-29`）。 |

## 有効になる条件

- 自動 share 算出が走る経路に限り有効。CUDA では `--pcie-frac` の値が負のままで、PCIe probe が成功した native pack の初期 share、および `PcieAuto` の pool rate に基づく更新で使われる（`engine/src/program/generate.cpp:5535-5579, 14913-14929, 15004-15040`）。
- 自動更新は全 expert が GPU resident ではなく、batch が `0`、peer device が未指定 (`< 0`) などの条件を満たす場合に開始する。layer split では `STRATA_PCIE_AUTO_SPLIT` 等により自動調整が有効である必要がある（`engine/src/program/generate.cpp:15004-15014`, `engine/src/program/generate.cpp:2833-2844`）。
- HIP では gfx12 の decode defaults や `STRATA_PCIE_FRAC_DEFAULT=auto` 等で自動調整が有効になる経路がある。`STRATA_PCIE_FRAC_DEFAULT=old` は自動 refinement を止める（`engine/src/program/generate.cpp:2893-2912, 5570-5576`）。
- `--pcie-frac` に非負値を指定すると自動初期化・更新の対象外で、CLI の固定 share が使われる。本変数はその CLI 値を clamp しない。負値は `o.pcie_frac < 0.0` の自動設定経路に入る（`engine/src/program/generate.cpp:4057, 5535, 15004`）。
- `STRATA_PCIE_FRAC_DEFAULT` は自動 refinement を使う経路や初期 share を左右するが、本変数より優先する上限設定ではない。`STRATA_PCIE_START` も自動調整開始時の初期値選択に関わり、その初期値も本変数で clamp される（`engine/src/program/generate.cpp:5538-5576, 14913-14929`）。
- 固定 share を扱うだけの経路、probe 失敗で default share に留まる経路、または PcieAuto が有効化されない経路では、この上限を使った自動調整は行われない（`engine/src/program/generate.cpp:5553-5579, 15004-15008`）。

## 実行時の詳細

値は `pcie_share_max()` 内の関数ローカル `static const double` に保存され、最初の呼び出し時に一度だけ読み取られる。以後プロセス内で環境を変更しても再取得されない（`engine/src/program/generate.cpp:3101-3104`）。`STRATA_DEFAULTS` も `qwen_defaults_026()` の static により初回呼び出し時に一度読む（`engine/include/strata/core/defaults_026.hpp:26-29`）。

PcieAuto は pool の測定値と link probe から share を計算し、`0.05` 刻みに丸めて下限 `0.10` と本変数の上限の間に収める。CPU pool の missed expert 数が不足する間は更新を見送り、十分な測定後の更新は最大 3 回。layer split の後続 stage も各 stage の link rate から同じ上限で share を計算する（`engine/include/strata/core/pcie_share_rule.hpp:28-32`, `engine/src/program/generate.cpp:3127-3149, 15015-15040`）。算出した share は `pcie_num`（最大 256）に変換され、verify の routing 設定へ反映される（`engine/src/program/generate.cpp:14931, 15026-15040`）。

## ログと測定値

自動初期 share が更新されると `strata serve: PCIe share: start ...`、decode 中に share が変わると `strata serve: PCIe share: the CPU pool takes ...` が stderr に出る。後者は更新値が現在値から少なくとも約 `0.025` 離れた場合に限る。layer split では stage ごとの `strata serve: PCIe share: stage ...` も出る。ログに本変数名や採用上限値を直接表示する処理は見当たらない（`engine/src/program/generate.cpp:3144-3149, 14923-14928, 15021-15040`）。

## 根拠

- `engine/include/strata/core/pcie_share_rule.hpp:59-63` — unset 規則、変換、clamp。
- `engine/src/program/generate.cpp:326-338, 3096-3107` — discrete 判定、環境値の static cache。
- `engine/src/program/generate.cpp:5535-5579, 14913-14931, 15004-15040` — 初期値・自動調整の条件、share 反映、ログ。
- `engine/src/program/generate.cpp:4057` — `--pcie-frac` の CLI parse。
- `engine/include/strata/core/defaults_026.hpp:21-29` — `STRATA_DEFAULTS` の認識と cache。
