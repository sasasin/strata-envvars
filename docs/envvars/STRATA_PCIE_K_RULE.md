# `STRATA_PCIE_K_RULE`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

CPU pool と PCIe link が分担する expert miss share の計算に使う係数 `k` の規則を選びます。`k` は `link / (link + k × R)` の分母に入り、`R` は CPU pool の expert byte rate です。変数を有効にすると、弱い CPU pool では `k` が 1.85 から 0.8 へ下がり、計算される link share が大きくなります。無効なら `k` は常に 1.85 です。これは share 計算用の設定であり、単独で PCIe share の自動計測・更新を有効にするものではありません（`include/strata/core/pcie_share_rule.hpp:16-27,38-43`）。

## 値と判定

読み取り値は `std::getenv("STRATA_PCIE_K_RULE")` から helper に渡されます。変数が設定されていても空文字列なら既定値の分岐に進みます。空でない文字列は `std::atoi` で変換し、結果が 0 以外なら有効、0 なら無効です。文字列全体の検証や範囲制限はありません。従って `1`, `-1`, `2tail` は有効、`0`, `0tail`, `true`, `n/a` は無効です。`atoi` が数値変換できない文字列は 0 になります。

| 値 | 判定 |
|---|---|
| 未設定、空文字 | discrete GPU かつ `STRATA_DEFAULTS=026` でない場合に有効。それ以外は無効 |
| 空でない文字列で `atoi(value) != 0` | 有効。既定値と `STRATA_DEFAULTS` に優先 |
| 空でない文字列で `atoi(value) == 0` | 無効。既定値に優先 |

係数の具体値は有効時、`R >= 30 GB/s` で 1.85、`R <= 12 GB/s` で 0.8、その間は線形補間です。無効時は `R` にかかわらず 1.85 です（`include/strata/core/pcie_share_rule.hpp:16-21,40-43`）。

## 有効になる条件

明示値は helper の既定条件に優先し、integrated GPU や `STRATA_DEFAULTS=026` の場合も `atoi` の結果で係数規則を選びます。ただし、係数が有効でも PCIe share 自動調整が実行されるとは限りません。実際に `pcie_pool_k()` が使われるのは、probe 等を経て `o.pcie_frac_auto` が有効になり、PCIe share の開始値または decode window 後の更新値を計算するときです。

- `--pcie-frac` を指定すると `o.pcie_frac` が既定値の負数ではなくなり、初期 probe/auto 設定の分岐を通りません。要求ごとの `pcie_frac` 指定は共有値の自動更新を適用しません（`src/program/generate.cpp:879-880,3574,4024-4026,4711-4755,15560,18986`）。
- 自動更新の起動には `o.pcie_frac_auto` と有効な link probe が必要です。全 expert が GPU resident、batch slots 使用、peer device 使用の場合は `PcieAuto` が起動しません（`src/program/generate.cpp:12609-12616`）。
- layer split は `STRATA_PCIE_AUTO_SPLIT` の判定も受けます。HIP の既定は opt-in、discrete CUDA は既定で有効、integrated GPU と `STRATA_DEFAULTS=026` では既定で無効です（`include/strata/core/pcie_share_rule.hpp:30-36`; `src/program/generate.cpp:2445-2456,4746-4751,12610`）。HIP の arch gate や `STRATA_PCIE_FRAC_DEFAULT` によって `o.pcie_frac_auto` が設定されない経路もあります（`src/program/generate.cpp:2490-2509,4746-4751`）。
- 初期 share の係数計算は CUDA では `STRATA_PCIE_START` の既定動作が新しい start を選ぶ場合に行われます。HIP では `STRATA_PCIE_START=new` の opt-in が必要です（`src/program/generate.cpp:12538-12554`）。decode 後の更新は最大 3 回で、miss が少なすぎる状態が続くと自動調整を止めます（`src/program/generate.cpp:2724-2747`）。

## 実行時の詳細

`pcie_pool_k()` 内の `static const bool on` が初回呼び出し時に環境値を読み、プロセス内に保持します。以後 `STRATA_PCIE_K_RULE` を変更しても再評価されません。係数計算の helper 自体は `R` ごとに実行されますが、有効/無効の選択はキャッシュされたままです（`src/program/generate.cpp:2702-2705`）。

この係数は初期 share の計算（CUDA/HIP の `STRATA_PCIE_START` 経路）と、decode window 後の `PcieAuto` 更新で使われます。更新値は `pcie_frac` と GPU dispatch の PCIe expert count に反映され、layer split では各 stage の link bandwidth に基づいて後続 stage の share も計算します（`src/program/generate.cpp:12538-12556,12621-12646,18986`）。更新時には stderr に `strata serve: PCIe share:` が出ます。係数の有効/無効そのものを示す専用ログ、無効値の警告、環境変数を理由とする終了経路はありません。probe に失敗した場合は初期 share の既定値を使い、自動調整値を設定しません（`src/program/generate.cpp:4731-4754`）。

## 根拠

- 読取とキャッシュ、係数 helper 呼出し: `src/program/generate.cpp:2693-2705`。
- 値変換、既定条件、係数式: `include/strata/core/pcie_share_rule.hpp:16-27,38-43`。
- `STRATA_DEFAULTS=026` は一度読み取られ、明示的な機能設定に優先されるマスタースイッチ: `include/strata/core/defaults_026.hpp:10-12,21-29`。
- 初期 share と CLI/probe 条件: `src/program/generate.cpp:3574,4024-4026,4711-4755,12538-12556`。
- 自動更新の起動条件、適用、ログ: `src/program/generate.cpp:12609-12646,18986`。
- 更新回数と miss 数条件: `src/program/generate.cpp:2724-2747`。
- 概要資料も CPU pool の速度に応じた係数と `STRATA_PCIE_K_RULE` の制御を記載しています: `docs/DETAILS.md:1050`。
