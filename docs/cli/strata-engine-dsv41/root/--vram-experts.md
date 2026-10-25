# `--vram-experts`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DSV4.1 engine のトップレベル引数） |
| オプション | `--vram-experts` |
| 別名 | なし |
| 値 | `F`。`atof` で `double` に変換される VRAM expert 予算の係数 |

## 役割

GPU ごとに残す VRAM 量を考慮した expert 用予算を調整します。係数は空き VRAM 全体に対する比率ではなく、少なくとも expert 配置の計算では `--reserve-mib` を差し引いた後の予算に掛かります。既定値は `1.0` です。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ids 1 --vram-experts 0.5
```

`--pack` には DSV4.1 pack のディレクトリを指定します。実際の推論には利用する pack に適合した token ID などが必要です。

## 値と既定値

- 値は必須です。値を省略すると parser の共通処理が `--vram-experts needs a value` を stderr に出し、終了コード `2` で終了します。
- `std::atof` の戻り値を `Options::vram_experts` に設定します。ソースには数値形式、有限値、最小値・最大値の検証がありません。したがって、CLI が `0..1` に制限するとはいえません。また、数値でない文字列を明示的に拒否する処理もありません。
- 省略時は `1.0` です。指定を繰り返した場合は parser が順に代入するため、最後の指定値が残ります。
- 係数を下げると expert 配置予算を減らし、上げると増やします。0、負数、1 超の値や不正形式の具体的な結果を CLI が保証する validation はありません。実用上の境界や性能上の推奨値は、このソース調査からは確認できません。

## 実行時の動作

parser は値を `std::atof` で変換し、`Options::vram_experts` に格納します。`Model::load` はこの Options を保持して pack のロードと GPU 構成を進めます。値は少なくとも次の計算に使われます。

- `--mmap-experts` が `auto` の場合、空き VRAM、`--reserve-mib`、prompt buffer の見積りから算出する expert 向け room に係数を掛け、CPU lane の expert をファイルから読むかを決める判定に使います。
- expert がファイルから読む構成の場合、expert 配置用 VRAM room と、それに応じた CPU/RAM 側の読み込み先行量を見積もります。
- 自動 staging ring の大きさを選ぶ際にも、reserve と固定 buffer の見積りを引いた VRAM room に係数を掛けます。
- 最終的な GPU expert 予算では各 GPU の現在の空き VRAM から `--reserve-mib` を引き、その値に係数を掛けます。tensor-parallel group では最も厳しいメンバーの予算が使われます。DSpark の expert を先に予算へ割り当て、その後 trunk の層ごとに配置数を決めます。
- 配置できる expert の数を決めた後、profile があれば hit count の多い expert を先に VRAM slot に割り当てます。

指定値は VRAM 割り当てそのものを予約する命令ではなく、これらの予算計算への係数です。係数を大きくして見積り以上の割り当てを試みれば、後続の CUDA allocation が失敗する可能性があります。

## 適用条件と副作用

- 対象は索引上の `strata-engine-dsv41` です。CMake では `STRATA_BUILD_DSV41=ON` のとき `strata-dsv41` target が追加され、この option はその executable の parser にあります。ソースコメントではこの build option は既定で OFF とされています。
- 実際の VRAM 予算は GPU の実行時空き容量、`--reserve-mib`、選択 GPU、tensor parallel の grouping、prompt buffer、DSpark の状態などに依存します。係数だけから固定の VRAM 容量や slot 数は決まりません。
- `--no-expert-cache` を併用すると、expert cache の動的差し替え用に VRAM slot を一つ空ける処理が無効になります。ただし `--vram-experts` の配置予算への反映自体は別の処理なので引き続き行われます。
- GPU に置かれない expert は CPU lane に回り、設定や pack に応じてモデルファイルから読み込まれたり、RAM tier が使われたりします。係数はこの負荷分担・読み込み先行量にも間接的に影響します。
- 設定ファイルや環境変数との優先順位を定める CLI 側の処理は確認できませんでした。DSV4.1 の `Options` ではこの値は CLI parser から直接セットされます。

## 出力とエラー

- 値の欠落は stderr に説明を出して終了コード `2` です。未知のオプションも stderr に `unknown option ...` と usage を出して終了コード `2` です。
- モデル読み込みが失敗すると `maya-ds4: <理由>` を stderr に出し、終了コード `1` で終了します。GPU expert slot の `cudaMalloc` が失敗した場合は層番号・slot 数・CUDA device ID を含むエラーが読み込み失敗理由になります。
- 有効値範囲を検証する option 固有のエラー・警告は確認できませんでした。係数によって最終的な割り当てがどうなるかは実行時の GPU 状態に左右されます。

## 根拠

- Strata `src/dsv41/ds4_main.cpp:85-94,1200-1217` — usage、値の必須処理、`atof` による parser 代入。
- Strata `src/dsv41/ds4_main.cpp:1266-1295` — help・未知 option の出力と終了コード、`Model::load` のエラー出力。
- Strata `src/dsv41/ds4_model.hpp:25-40` — Options の既定値 `vram_experts = 1.0`、reserve と expert cache の既定値。
- Strata `src/dsv41/ds4_model.cu:1853-1891` — Options の受け取り、pack 検査、GPU の選択と空き VRAM の取得。
- Strata `src/dsv41/ds4_model.cu:1946-1975` — mmap 自動判定用 room と係数、prompt chunk の決定。
- Strata `src/dsv41/ds4_model.cu:2597-2618,2796-2814` — CPU lane の warm 見積りと staging ring 選択への係数適用。
- Strata `src/dsv41/ds4_model.cu:3798-3862` — GPU ごとの配置 budget、DSpark/trunk の expert slot 数決定。
- Strata `src/dsv41/ds4_model.cu:3880-3910` — profile 順の slot 配置と CUDA allocation、その失敗経路。
- Strata `CMakeLists.txt:797-810` — DSV4.1 target が `STRATA_BUILD_DSV41` で追加される条件。
- Strata `src/dsv41/ds4_model.hpp:30-33` — `vram_experts` の説明と expert cache の役割。

調査時点で checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。既存 build 済み CLI の help は実行していません。数値境界、各 OS/backend での allocation 結果、配布 Release の実体はこの調査では検証していません。
