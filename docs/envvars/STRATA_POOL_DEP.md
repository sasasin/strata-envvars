# `STRATA_POOL_DEP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU `ExpertPool` の native multi-expert layer 処理で、gate/up と down の row task を一つの batch として発行する方式を選ぶ。ON の場合、worker は gate/up の作業が終わった expert から中間値を量子化して down rows に進める。OFF の場合は gate/up batch、ホスト側の量子化、down batch の 2 段階に戻る。分岐は `ExpertPool::run_split_multi_native` にあり、pool constructor が変数を読み取る（`engine/src/kernels/cpu/pool.cpp:803-804, 921-923, 1559-1604`）。

これは CPU `ExpertPool` の実行方式を選ぶもので、CUDA/HIP/SYCL の GPU kernel 自体を選択する変数ではない。コード上の全参照では、実読み取りは constructor の `std::getenv` 1 箇所だけで、ほかはコメント、CPU CMake のテスト設定、設計資料、設定名一覧だった。索引 `docs/envvars/000_envvers.md:1731` に候補として載り、実装上の読み取りも確認できた。

## 値と判定

constructor で `std::getenv` を一度呼び、値の先頭文字が `'0'` かだけを確認する。文字列全体の比較・数値変換・空白除去・妥当性検査はしない（`engine/src/kernels/cpu/pool.cpp:921-923`）。

| ビルド／実行経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `ExpertPool` を含む CPU kernels build | ON | 空文字、`1`、`true`、`false`、` 0`、その他 `'0'` 以外で始まる文字列 | `0`、`00`、`0anything` など `'0'` で始まる文字列 |

大文字小文字・空白・数値としての妥当性は調べないため、`true` と `false` はどちらも ON、先頭に空白がある ` 0` も ON になる。設定値が `'0'` で始まれば後続文字にかかわらず OFF になる。未設定は `nullptr` 判定により ON。無効値を知らせる警告や fallback はない（`engine/src/kernels/cpu/pool.cpp:922-923`）。

## 有効になる条件

ON の値は `dep_on_` に記録されるが、次の条件をすべて満たす `run_split_multi_native` の batch に限り、一括方式へ進む（`engine/src/kernels/cpu/pool.cpp:1559-1579`）。

- native multi-expert 処理であること。呼び出し元は CPU expert pool の native row 処理（例: `engine/src/program/generate.cpp:3064`、`engine/src/qwen35/q36_engine.cu:3353`、`engine/src/core/expert_source.cpp:5890,5935`）。
- 静的 row slice が OFF（`static_slices_ == false`）。生成経路では `STRATA_POOL_STATIC` が `atoi` で非 0、または `STRATA_L3_PF` による prefetch が選ばれると static slices を要求する。L3 prefetch の選択条件は `l3_pf_auto_default` に委ねられる。pool が複数 worker で NUMA split 中なら `set_static_slices` 自体が OFF にする（`engine/src/program/generate.cpp:10410-10425`、`engine/include/strata/kernels/cpu/pool.hpp:258`）。
- NUMA split が OFF（`numa_n_ == 0`）。`STRATA_NUMA_SPLIT` / `STRATA_NUMA_POOL` と topology による constructor の判断結果が split ON なら適用外（`engine/src/kernels/cpu/pool.cpp:810-820, 924-979`）。
- pool worker 数が 2 以上（`n_ > 1`）。
- gate/up と down のどちらの native kernel format も Q2 native kernel ではない。

いずれかを満たさない場合は、環境変数の値に関係なく、同じ関数内の mode 5 gate/up batch、間の量子化、mode 6 down batch の経路に進む（`engine/src/kernels/cpu/pool.cpp:1584-1597`）。`--no-pool` が設定される生成経路では drive に pool 関数を渡さず、expert-pool workers を unused として扱う（`engine/src/program/generate.cpp:10401-10409`）。この変数自体を上書きする CLI 引数や別環境変数の読み取りはない。

## 実行時の詳細

読み取りは `ExpertPool` constructor 内の一回だけで、値を `dep_on_` に保存する。したがって同じ pool の存続中にプロセス環境が変わっても、その pool には反映されない。pool を作り直した場合は、その新しい constructor が環境を読み直す（`engine/src/kernels/cpu/pool.cpp:803-804, 921-923`）。

一括方式では、batch ごとに expert ごとの gate/up task 数と down task 数を計算し、依存カウンターを初期化して mode 7 を publish する。down task は自身の expert の gate/up task 完了を待ち、最初の down worker が中間値を一度量子化してから down rows を処理する（`engine/src/kernels/cpu/pool.cpp:1568-1583, 1414-1453`）。OFF または適用条件外では gate/up rows を実行し、ホストスレッドが中間値を量子化した後に down rows を別 batch で実行する（`engine/src/kernels/cpu/pool.cpp:1584-1601`）。

## ログと測定値

`STRATA_POOL_DEP` の値や ON/OFF を直接表示するログ、無効値エラー、終了経路は見つからなかった。pool の診断計測が有効な場合は一般的な batch / phase 統計が出るが、この変数の状態を表示するものではない（`engine/src/kernels/cpu/pool.cpp:1016-1032, 1602-1617`）。`docs/DETAILS.md` には関連する性能測定の記録があるものの、この文書ではコードで確認できた制御動作のみを記載し、性能値は一般化しない。

## 根拠

- `engine/src/kernels/cpu/pool.cpp:803-804, 921-923` — constructor と読み取り・値判定。
- `engine/src/kernels/cpu/pool.cpp:1414-1453, 1559-1601` — mode 7 の依存処理、適用条件、二段階 fallback。
- `engine/include/strata/kernels/cpu/pool.hpp:441-454` — mode 7 / `DepExpert` の役割と constructor 読み取りの宣言。
- `engine/src/program/generate.cpp:10401-10425` — `--no-pool` と static slices の設定。
- `engine/cmake/backends/cpu.cmake:237-243` — CPU x86 / portable のどちらのライブラリ構成にも `pool.cpp` が含まれること。
