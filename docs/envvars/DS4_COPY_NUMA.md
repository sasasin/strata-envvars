# `DS4_COPY_NUMA`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek-V4.1 エンジンが CPU lane 用の MXFP4 experts をファイルから RAM にコピーする場合、expert の行列を何個の NUMA part に分けるかを指定します。part 数はコピー時の行列レイアウトと、CPU lane の worker pool の数に使われます。これは Strata の `strata-dsv41` / `maya-ds4` 経路に固有の設定です。

## 値と判定

`copy_experts()` は `std::getenv("DS4_COPY_NUMA")` で設定有無を調べ、設定されている場合は `std::atoi()` の結果を使います。文字列全体の検証はありません。

| 環境変数 | part 数の候補 |
|---|---:|
| 未設定 | `min(2, max(1, 検出した NUMA node 数))` |
| 設定値の `atoi()` が 2 以上 | 2 |
| 設定値の `atoi()` が 2 未満 | 1 |

したがって `2`, `3`, `2tail` は2 part、`1`, `0`, `-1`, 空文字、数値に変換できない文字列は1 partになります。空白や符号などの扱いも `atoi()` に従います。候補数を決めた後、モデルの `g.ff` または `g.dim` が候補 part 数で割り切れなければ、実際の `NH` は1に戻ります。

## 有効になる条件

- `strata-dsv41` の DeepSeek-V4.1 実装を使用すること。通常の Strata エンジンには適用されません。
- `STRATA_BUILD_DSV41` を有効にして `strata-dsv41` ターゲットをビルドすること。この CMake option は既定で OFF です。
- `load_experts()` が MXFP4 経路を選び、`load_experts_mx()` から `copy_experts()` が呼ばれること。
- `copy_experts()` が早期終了しないこと。`--mmap-experts on`（`o.mmap_experts > 0`）、コピー候補が空、またはコピー予算が0以下の場合は、この変数による分割は行われません。コピー予算は通常 `--mmap-experts off` / auto の条件で決まり、`DS4_COPY_GB` でも上書きされます。
- RAM tier (`ram_tier`) が有効な経路では `copy_experts()` を呼ばないため、この変数はコピーに作用しません。

未設定時の node 数は `node_cores()` が検出した node 配列の数です。検出できない場合は同関数が一つの node として fallback します。明示値 `2` 以上は node 数に関係なく候補を2にしますが、行列次元の割り切れ条件は引き続き適用されます。

## 実行時の詳細

コピーが実行されると `NH` を part 数として保存します。各 part の領域は `node_map(bytes, X, NH)` で確保され、各 expert の3行列について行を `NH` 等分した単位でファイルから読み込みます。`NH > 1` のとき、コピー完了ログには `... (%d NUMA parts) ...` と実際の part 数が表示されます。

CPU lane の pool 作成では `NH` 個の pool を作ります。検出 node 数より `NH` の方が多い場合（例えば単一 node 上で明示的に2を指定した場合）は、検出された node の core list を2つに分配して使います。実行時に環境変数を変更して再評価するコードはなく、値は `copy_experts()` の呼び出し時に読み取られます。

## 根拠

- `src/dsv41/ds4_model.cu:4096-4099,4177-4181` — MXFP4 expert load 経路で、RAM tier でないとき `copy_experts()` を呼ぶ。
- `src/dsv41/ds4_model.cu:4251-4260,4278-4302` — コピーの目的、早期終了、候補 part 数、`atoi()` による判定と行列次元による fallback。
- `src/dsv41/ds4_model.cu:4312-4350,4373-4384` — RAM part の確保と expert 行列の part ごとの読み込み。
- `src/dsv41/ds4_model.cu:4396-4403` — コピー後の状態と stderr ログ。
- `src/dsv41/ds4_model.cu:117-145` — NUMA node/core の検出と fallback。
- `src/dsv41/ds4_model.cu:4827-4863` — `NH` に応じた CPU pool 数と、単一 node の core 分割。
- `CMakeLists.txt:797-810` — `strata-dsv41` が独立した DeepSeek-V4.1 実行ターゲットとして定義される。
- `docs/DETAILS.md` — `DS4_COPY_NUMA` 固有の説明や測定値は確認できませんでした。上記の挙動はソースコードから確認したものです。
