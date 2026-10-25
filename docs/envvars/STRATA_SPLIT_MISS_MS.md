# `STRATA_SPLIT_MISS_MS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`--layer-split auto` が複数 GPU に層を割り当てる候補を評価するとき、GPU の expert cache に入らないと予測した routed mass のコスト（ミリ秒）を指定します。設定値は実測の遅延を直接変更するものではなく、起動時の候補選択に使う予測値です。未設定時の基準値は `190.0` ms です。

## 値と判定

CUDA 系と SYCL 系の実装は、環境変数が未設定なら `190.0`、設定されていれば `std::atof(getenv(...))` の結果を使います。文字列全体の妥当性検査、値域チェック、clamp はありません。

| 環境の値 | コード上の扱い |
|---|---|
| 未設定 | `190.0` |
| 空文字 | `atof("")` の結果 `0.0` |
| 数値として読める値 | 先頭から `atof` が変換できる数値を使う。符号・小数を含められ、数値の後ろに変換対象外の文字があっても、その部分は判定されない（例: `12.5ms` は `12.5`）。 |
| 数値に変換できない文字列 | `atof` の結果 `0.0` |
| 負値 | そのまま使われる。負値を拒否したり 0 に丸めたりしない。 |

従って、`STRATA_SPLIT_MISS_MS=0`、空文字、または数値でない文字列は、予測上の cache miss コストを 0 にします。負値も受理され、候補の miss penalty を負にします。値の再読み込み用 static cache はありませんが、分割探索は起動時に一度行われるため、探索後にプロセス環境を書き換えても選択済みの分割は変わりません。

## 有効になる条件

- `--layer-split auto` が指定され、`--serve` が有効であること。明示的な `--layer-split K[,K2...]` ではこの値を読みません。
- 自動分割に複数 GPU が選ばれていること。可視 GPU が1台なら `auto` は分割なしに戻ります。
- `--split-skip-if-fits` が指定され、CUDA 0 だけで profile 全体を保持できる場合は split 自体を取り消すため、この値を使う探索に入りません。
- profile が空なら、予測される missed mass は実質 0 です。この値を変えても候補間の差にはなりません。profile の読み込みは `--expert-profile` が指定された場合に行われます。
- `--layer-split auto` の予測は候補の層境界、各段の VRAM 残量、profile の順位、他のコスト値も使います。したがって、この値だけで最終境界が決まるわけではありません。

## 実行時の詳細

CUDA 系実装は `src/program/generate.cpp`、SYCL 実装は `sycl/src/program/generate.cpp` に同じ環境変数の読み取りがあります。どちらも探索処理の中で `getenv` と `atof` を行い、デフォルト値は `190.0` です。

予測時間には「cache に保持できなかった routed mass × miss cost」と、段ごとの層数に応じた GPU 処理時間を加算します。CUDA 系の2段・3段分割では、miss cost に各段の PCIe link 推定による係数も掛けます（20 GB/s を基準に、コード上は係数を 1〜64 に制限）。4段分割の専用探索では全段の missed mass を集約した式を使い、段別 link 係数は掛けません。5段以上では比例配分の候補だけを評価するため、miss cost はその候補の予測値には入りますが、比較対象がなく、境界選択には影響しません。SYCL の予測式には CUDA 系の段別 link 係数はありません。

値は探索結果を通じて選ばれる層境界に反映されます。stderr には選択した `K`、予測 ms、cache が保持すると見積もった profile 数・routed mass、および評価した候補数が `layer split auto` の行として出ます。環境変数の値そのものを表示するログは、この読み取り周辺にはありません。

## 根拠

- `src/program/generate.cpp:2298-2348` — `--layer-split auto`、serve 条件、GPU 数、複数 GPU 分割の判定。
- `src/program/generate.cpp:3344-3388` — `--split-skip-if-fits` が split を取り消す経路。
- `src/program/generate.cpp:3534-3576` — `--expert-profile` による profile の読み込み。
- `src/program/generate.cpp:3715-3729` — CUDA 系の link 係数準備と環境変数の読み取り、既定値。
- `src/program/generate.cpp:3795-3820` — 段ごとの missed mass と予測コストの計算。
- `src/program/generate.cpp:3959-3978,3995-4065` — 候補評価、2〜4段の探索と4段用の集約式。
- `src/program/generate.cpp:4162-4167` — 選択した分割と予測値の stderr 出力。
- `sycl/src/program/generate.cpp:3563-3564,3609-3639,3665-3735` — SYCL 側の読み取り、予測式、2〜4段探索。
- `bench/results/2026-09-29-layer-split/README.md:70-78` — 190 ms が sweep の最良 K に合わせた値であり、環境変数で上書きできるという測定資料上の説明。ここに記載された測定値は同資料の rig・モデル条件に限られます。
