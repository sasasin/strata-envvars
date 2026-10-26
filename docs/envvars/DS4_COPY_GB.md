# `DS4_COPY_GB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DS4 のモデル読み込み時、CPU lane に残る expert のうち、使用プロファイルで熱いものから指定量までを RAM にコピーする予算（GB）を指定します。残りの expert はモデルファイル上に置かれます。値が使われるのはロード時の初期コピー選択です。その後の expert cache による GPU との入れ替えは別の処理で、この値を継続的な RAM 容量上限としては使いません。

## 値と判定

`copy_experts()` で環境変数が設定されていると、`std::atof(v) * 1e9` がコピー予算の既定計算を上書きします。単位は 10 億 byte（十進 GB）です。文字列全体の検証や範囲 clamp はありません。

| 値 | コピー予算への結果 |
|---|---|
| 未設定 | `--mmap-experts off` なら使用可能な RAM 等を考慮した量、`auto` なら自動全件コピー条件を満たしたときだけ全量、それ以外は 0。 |
| `0`、空文字、数値に変換できない文字列 | `atof` の結果は 0 となり、コピーしない。 |
| 正の数値 | その GB 数を byte に換算した予算。hot 順の expert を、予算内に収まる範囲で選ぶ。数値の後ろに変換できない文字があっても、`atof` が読める先頭部分が使われる。 |
| 負の数値 | 負の予算となり、`budget <= 0` の分岐でコピーしない。 |

値を設定したこと自体はコピーを強制しません。空または非数値の値も「環境変数が存在する」ため、自動全件コピーの RAM 適合判定には影響します（下記）。

## 有効になる条件

- DS4 の `load_experts()` が通常の expert 読み込み経路を通り、`!ram_tier && !warm.empty()` で `copy_experts()` が呼ばれる必要があります。`warm` は CPU lane に残った expert からプロファイルの使用率が高い順に作られます。
- `--mmap-experts on`（内部値 `o.mmap_experts > 0`）では `copy_experts()` が最初に戻るため、この変数のコピー予算は使われません。`--mmap-experts off` は内部値 0、`auto` および他の値は内部値 -1 です。
- 先頭 layer の format が `gg::kFmtMXFP4` の場合、`load_experts()` は `load_experts_mx()` に分岐するため、この `copy_experts()` の読み取りには到達しません。
- `--mmap-experts off` では通常、CPU lane の全 expert が対象候補になりますが、明示した予算が全件より小さければ hot 順に予算内の分だけ選びます。自動モードでは `auto_copy_all` が成立していなくても予算を上書きできます。
- RAM 上の領域を layer ごとに確保できなければ、その layer のコピーは取りやめられ、stderr に `ds4: no RAM for layer ...: they stay in place` と出ます。値に応じてメモリ確保可能量を clamp する処理はありません。

## 実行時の詳細

`load_experts()` はプロファイルに基づき CPU lane の expert を並べ、`copy_experts()` はその順に予算へ収まる候補を選びます。各候補の費用は expert の blob サイズで、expert cache 用の spare VRAM slot がある layer ではその layer の最初のコピーに spare 分も加算します。各 layer の領域を確保後、expert のデータをモデルファイルから読み込み、成功した expert に RAM slot を割り当てます。読み込み失敗は `copying the CPU lane's experts from the model's files failed` としてロード失敗になります。

読み取りは `copy_experts()` の呼び出し時で、`std::getenv` の値をその都度参照します。この関数はモデルロード中に呼ばれます。値が設定されていると `cpu_lane_fits_ram()` も false を返し、自動 store 判定で「CPU lane 全体が RAM に収まるなら全件をコピーして demand store を使わない」という分岐を選ばなくなります。代わりに通常の自動 store 容量計算へ進みます。`DS4_STORE_GB` が設定されている場合なども同関数は false です。

コピーが成立すると stderr に `ds4: N of the CPU lane's M experts copied into RAM ...` が出ます。全候補に満たないときは末尾に `; the others read in place` が付きます。コピー予算が 0 以下の場合の説明ログは `o.verbose` 時のみです。

## 根拠

- 値による予算の上書き、既定予算、非正予算の扱い、NUMA 設定: `src/dsv41/ds4_model.cu:4251-4301`。
- profile 順の候補作成と `copy_experts()` 呼び出し条件: `src/dsv41/ds4_model.cu:4156-4187`。
- 候補選択、RAM 確保、コピーとログ: `src/dsv41/ds4_model.cu:4312-4404`。
- `--mmap-experts` の値変換: `src/dsv41/ds4_main.cpp:1239-1241`。
- 自動全件コピーの適合条件における環境変数の有無判定と自動 store の分岐: `src/dsv41/ds4_model.cu:4578-4611`。
- MXFP4 の別経路: `src/dsv41/ds4_model.cu:4407-4409`。
- `docs/DETAILS.md` にこの環境変数の専用説明や測定値は見つかりませんでした。ソースコメントは `--mmap-experts off` の全量コピーについて測定所見を述べていますが、`DS4_COPY_GB` を用いたコピー量ごとの測定条件・結果は記載されていないため、本書では性能値を示しません。
