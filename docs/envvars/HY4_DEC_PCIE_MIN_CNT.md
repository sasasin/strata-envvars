# `HY4_DEC_PCIE_MIN_CNT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4-Flash の hybrid decode/verify で、CPU 側にある missed experts のうち PCIe 経由で GPU に転送して実行する候補に必要な最小出現回数を指定する。`dec_pcie_min_cnt` の初期値は 1 で、部分的な GPU 分担を選ぶとき、出現回数の多い順に候補を並べ、この値未満の候補に達すると選定を打ち切る。閾値を上げると出現回数の少ない候補は GPU 転送対象から外れ、CPU 側に残る。候補の出現回数は同じ expert がその decode/verify 窓で選ばれた回数である（`engine/src/hy4flash/run/hy4_graph.hip.h:2194-2225, 2286-2301`）。

これは GPU と CPU の間で missed experts の処理先を分ける基準であり、router が選んだ expert 自体やその候補順位をこの変数が変更する処理はない。値が使われるのは `Runner::run_hybrid_miss_layer` の PCIe miss 分担経路である（`engine/src/hy4flash/run/hy4_graph.hip.h:2189-2192, 2291-2301`）。

## 値と判定

`pf_init()` が `getenv` で設定有無を見て、設定があれば `atoi` の結果を `std::max(1, ...)` で下限 1 に丸めて `dec_pcie_min_cnt` に保存する。未設定ならメンバー初期値 1 のまま。空文字も「設定あり」だが `atoi` は 0 を返すため、結果は 1 になる（`engine/src/hy4flash/run/hy4_graph.hip.h:400, 643-645`）。

| ビルド・状態 | unset | 設定時に有効になる値 | 下限 1 になる値の例 |
|---|---:|---|---|
| HY4-Flash の共有 GPU 実装（HIP または CUDA）で `pf_init()` が最後まで進む | 1 | `atoi` が正の整数を返す値。例: `2`, `+3`, ` 4`, `5tail` はそれぞれ 2, 3, 4, 5 | 空文字、`0`, `-2`, `true`, `0anything` は 1（`2.9` は 2）（`atoi` は先頭の整数部分を変換し、数値として読めない入力は 0。後続文字列は検査しない） |

数値全体の妥当性検査、エラー通知、大文字小文字の判定はない。負値・0・整数に変換できない文字列は 1 に丸められる。正の整数部分の後ろに文字が続く入力も受理される。`atoi` の整数範囲を超える入力の結果は保証されないため、使用可能な値としては扱えない（`engine/src/hy4flash/run/hy4_graph.hip.h:644`）。

## 有効になる条件

- ソースは HIP/CUDA 共通の `hy4_graph.hip.h` にあり、`hy4_gpu.h` は同じ GPU 実装を HIP と CUDA のどちらでもビルドすると記載している。環境変数の判定自体に backend 別の分岐はない（`engine/src/hy4flash/run/hy4_gpu.h:1-9`; `engine/src/hy4flash/run/hy4_graph.hip.h:643-645`）。
- `Runner` が hybrid 状態である必要がある。CPU expert mask があり、`cpu.init(...)` が成功すると `hyb = true` になる（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583`）。
- さらに `HY4_PF_STREAM` が未設定、または `atoi(HY4_PF_STREAM) != 0` でなければ `pf_init()` は呼ばれない。`HY4_PF_STREAM=0` は抑止する一方、空文字や数値で始まらない値は `atoi` が 0 なので同じく抑止する（`engine/src/hy4flash/run/hy4_graph.hip.h:1706-1708`）。
- `pf_init()` 内で CPU expert の最大レイヤーサイズ `maxb` が 0 の場合は、値を読む前に戻る。また scratch / buffer の確保条件を満たさず prefill streaming の初期化が途中終了する場合も、後段の環境変数読み取りと `pf_stream = true` には到達しない（`engine/src/hy4flash/run/hy4_graph.hip.h:545-562, 593-600, 617-646`）。
- decode/verify で実際の PCIe 候補判定には、`!vcache_frozen`、`pf_stream`、`T <= 8`、tier-2 miss が 1 件以上、必要な device/host scratch と動的 expert table が存在することが必要。bounce 使用時は bounce buffer も必要（`engine/src/hy4flash/run/hy4_graph.hip.h:2271-2272`）。条件に合わなければ、この閾値を使う PCIe streaming 候補選定は行われない。
- `dec_pcie_share` は別に `HY4_DEC_PCIE_SHARE` から設定される。分担率が 0.001 以下なら PCIe 候補選定に入らず、0.999 以上なら全候補数を目標とし、この最小出現回数条件を迂回する。自動分担でも、cold miss がなく `nc <= 8` の経路では分担率を 1.0 にするため閾値を迂回する（`engine/src/hy4flash/run/hy4_graph.hip.h:643-645, 2274-2286, 2291-2295`）。

## 実行時の詳細

値は Runner 初期化中の `pf_init()` で読み、通常の member 変数 `dec_pcie_min_cnt` に保持する。static cache ではなく、同じ Runner では初期化後に環境を変更しても再読込されない。別 Runner が初期化されれば、その呼び出し時の環境から別途設定される（`engine/src/hy4flash/run/hy4_graph.hip.h:400, 545-646, 1706-1708`）。

各 hybrid miss layer で、decode/verify 窓内の router 結果から expert ごとの回数を集計し、host-resident tier-2 experts のうち CPU resident な miss を候補化する。GPU 分担率に応じた目標件数に達するまで候補を出現回数の降順で見て、部分分担（`share_frac < 0.999`）では `cnt < dec_pcie_min_cnt` となった時点で以降の候補を打ち切る。残った候補は GPU 側 scratch へコピーして GPU expert 計算に渡し、選ばれなかった miss は CPU 側へ残る（`engine/src/hy4flash/run/hy4_graph.hip.h:2194-2225, 2286-2301, 2303-2324, 2333-2416`）。

候補数が 0（cold miss もない）ならゼロ miss の早期 return があり、閾値判定には進まない。cold miss を含む場合はその cold miss 自体はこの PCIe 候補リストには入らず、tier-2 の候補分担に対してだけ本変数が働く（`engine/src/hy4flash/run/hy4_graph.hip.h:2211-2225, 2256-2264`）。

## ログと測定値

この変数の値や閾値判定を表示するログはない。自動分担の校正が完了したときは `[hybrid] calibrated PCIe/CPU miss split (%s, %s): gpu=%.1f exp/ms vs cpu=%.1f exp/ms -> pcie_share=%.2f` が stderr に出るが、これは分担率の校正ログであり、本変数の値は含まれない。明示的な `HY4_DEC_PCIE_SHARE` を使う場合は校正を要求する条件から外れる（`engine/src/hy4flash/run/hy4_graph.hip.h:2247-2251, 2321`）。

値の parse エラーや無効値の警告・終了経路はない。`pf_init()` の資源不足では `prefill streaming disabled` の stderr ログを出して return する経路があるが、これは閾値の値に関係するエラーではない（`engine/src/hy4flash/run/hy4_graph.hip.h:597-600, 617-620`）。資料に本変数固有の測定値は見当たらない。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:400, 643-646` — 初期値、環境変数の読み取り、変換、下限 clamp。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583, 1706-1708` — hybrid 状態の設定と `HY4_PF_STREAM` による初期化条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2194-2225, 2256-2286, 2291-2301` — miss 候補の作成、PCIe 有効条件、分担率と閾値の適用。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2303-2324, 2333-2416` — CPU/GPU への振り分けと GPU 側コピー・実行。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2247-2251, 597-600, 617-620` — 校正ログと prefill 初期化失敗ログ。
- `engine/src/hy4flash/run/hy4_gpu.h:1-9` — HIP/CUDA 共通実装およびビルド記載。
