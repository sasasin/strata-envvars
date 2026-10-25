# `STRATA_PCIE_BALANCE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

単一 GPU の native expert pack で speculative verify を行うとき、各 layer の cache miss expert のうち PCIe 経由で GPU に渡す数を、固定比率ではなく CPU pool と GPU の実測時間モデルから選びます。CPU 側の処理と GPU 側の処理を並行させ、予測される遅い側の時間が小さくなる miss 数を layer ごとに選ぶ仕組みです。

この設定は `--pcie-frac` による明示指定を置き換えません。未設定時は既存の固定 share の動作です。

## 値と判定

`src/program/generate.cpp` の `pcie_balance()` が環境を読み、値全体を `std::strcmp(e, "1") == 0` で比較します。数値変換や前後空白の除去はありません。

| 値 | 要求判定 |
|---|---|
| 未設定 | 無効 |
| `1` | 有効要求 |
| 空文字、`0`、`true`、`01`、`1 ` など | 無効 |

有効要求が実際に使われるのは、`--pcie-frac` が指定されておらず、native pack、単一 GPU、`--batch` が無効（`o.batch <= 0`）の全条件を満たす場合だけです。条件外では同じ固定 share 経路になります。CLI の `--pcie-frac` を指定すると値にかかわらず無効です。

## 有効になる条件

- CUDA の `generate` / `serve` の verify 経路で使われます。`set_pcie_balance()` は `Verifier` にモデルを渡し、GPU 上の verify window が時間計測 stamp を記録する構成です。
- native expert pack が必要です。canonical Q2_0 pack では有効化されません。
- 単一 GPU が必要です。layer split など `multi_gpu` の構成では無効です。
- batch slots は使えません（`o.batch <= 0`）。
- `--pcie-frac` を指定すると無効です。指定時には `pcie_given` が true になり、`pcie_balance()` は false を返します。
- verify が実際に PCIe miss を処理する layer でのみ、モデルの選択が share に影響します。全 expert が resident などで miss がなければ、この仕組みで割り当てるものはありません。

`generate` と `serve` の各 verifier 初期化箇所で条件を確認します。serve では request ごとに `--pcie-frac` の pause 状態が反映されます。明示 share を使う request の間は balance を pause し、測定済みモデルは次の request 用に保持されます。

## 実行時の詳細

1. `Verifier::init()` は balance 用の mapped stamp 領域を確保し、`PcieModel::on` を true にします。GPU 側の wait kernels は各 verify step で GPU 計画到着、PCIe 部分の開始、CPU rows の待機に対応する GPU clock stamp を記録します。
2. CPU pool は layer の処理後に CPU expert 数、PCIe expert 数、pool 処理時間を記録します。window 終了時に有効な stamp のある step を `PcieModel::sample()` に渡し、モデルを更新します。
3. CPU 時間は `a + c*n_cpu + d*n_pcie`、GPU 時間は `g0 + g*n_pcie` の線形モデルとして fit されます。CPU fit は少なくとも8標本、GPU fit は少なくとも8標本かつ PCIe expert を含む標本が4つ以上あると係数が更新されます。係数の fit は忘却係数0.995を用い、CPU係数は非負、PCIeによるCPU増分 `d` は `0..c` に制限されます。
4. fit が利用可能なら、layer の miss 数 `nmiss` について PCIe に回す数 `k=0..nmiss` を比較し、`max(GPU予測時間, CPU予測時間)` が最小となる `k` を選びます。fit がまだ揃っていないときは、既存の固定比率 `pcie_num` から得る数を基準にします（model が on の間は、次項の探索による変更が入る場合があります）。
5. モデルが on で miss がある場合、探索用に64回に1回は、全 miss が片側に寄る選択から1 expert を反対側へ動かします。これにより両側のモデルにデータを与えます。

実際に PCIe に回す候補は、route 順の末尾にある miss から選ばれ、pinned blob が取れた場合に fetch されます。したがってモデルが選んだ数と実際に fetch できた数は常に一致するとは限りません。処理結果を確認するログは、出力末尾の `pcie model`（CPU/GPUの推定係数）です。`pcie experts` 行は PCIe 経由の平均 expert 数と固定比率表示を出します。

環境変数は `pcie_balance()` の呼び出し時に `getenv()` され、静的キャッシュはありません。通常は verifier の初期化時に評価されます。プロセス起動後に環境を書き換える運用や、その反映時期はソース上で保証されていません。

## 文書と測定値

`docs/DETAILS.md` はこの設定を opt-in、CUDA、単一 GPU、batch slots なし、`--pcie-frac` なしと説明しています。同資料の測定では IQ3_XXS の interleaved 5組で、RTX A4000 arena decode は48.45→51.15 tok/s（+5.6%、5/5組で向上）、RTX 3060 resident は59.12→58.15（-1.6%）、Tesla P100 は37.95→37.48（-1.3%）と記載されています。資料は「A4000-class で試す価値がある」ため opt-in としています。これらは同資料記載の測定値であり、他の構成の性能を示すものではありません。

## 根拠

- 値の完全一致判定、native pack / GPU 数 / batch / CLI 条件: `src/program/generate.cpp:3349-3356`。
- `--pcie-frac` 指定状態の判定: `src/program/generate.cpp:2756-2758`。
- serve / generate で verifier にモデルを渡す箇所: `src/program/generate.cpp:8582-8584,15285-15297`。
- serve request の pause と明示 share: `src/program/generate.cpp:13283-13289`。
- expert miss 数のモデル適用、fallback、pinned blob の fetch: `src/core/expert_source.cpp:3873-3919,3935-3957`。
- `PcieModel` の標本条件、fit、予測と探索: `include/strata/core/expert_source.hpp:344-430`。
- GPU stamp 領域と model on の初期化: `src/core/verify.cpp:724-733`。
- GPU 側の stamp / CPU wait 計測データ収集: `src/core/verify.cpp:1984-2022,2831-2836,2987-2998`。
- window ごとの model 更新条件: `src/core/verify.cpp:2913-2920`。
- 出力 `pcie model`: `src/program/generate.cpp:15798-15807`。
- 条件・性能記載: `docs/DETAILS.md:1846-1849`。
