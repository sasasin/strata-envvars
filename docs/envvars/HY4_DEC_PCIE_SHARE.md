# `HY4_DEC_PCIE_SHARE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 HIP 実装のハイブリッド実行で、CPU 常駐 expert のうち decode / verify 時に VRAM にない expert を、CPU pool で計算するか、ホストから PCIe で GPU に転送して計算するかの固定割合を指定する。設定値は `Runner::pf_init()` が初期化する `dec_pcie_share` に入り、`run_hybrid_miss_layer()` が PCIe 側へ送る候補数を決める。ルーターが選んだ expert や miss の数を変える値ではなく、候補の計算先を分ける値である（`engine/src/hy4flash/run/hy4_graph.hip.h:380-401, 2186-2189, 2210-2225, 2271-2301`）。

この読み取りは `hy4_graph.hip.h` の HIP 実装にある。Runner が hybrid 状態で、さらに `HY4_PF_STREAM` が未設定または `atoi` の結果が 0 以外の場合に `pf_init()` を呼ぶ（同 `:1704-1708`）。したがって、すべての Strata backend や通常の GPU 常駐経路に共通する設定ではない。

## 値と判定

`pf_init()` 内で `getenv()` が null でないときだけ `atof()` で変換し、`std::max(0.0, std::min(1.0, ...))` で `[0, 1]` に clamp する。文字列全体の妥当性検査はなく、`atof` が読める先頭の数値部分が使われる。空文字や数値に変換できない文字列は `atof` の結果が 0 となる。先頭・末尾の空白も独自には検査しない（同 `:381, 643`）。

| 条件 | unset | 有効になる値（例） | 変換後・無効値の例 |
| --- | --- | --- | --- |
| `pf_init()` まで到達 | `-1.0` のまま自動選択 | `0` は PCIe miss 分担を停止、`0.5` は候補数の約半分、`1` は全候補を目標にする | `-1` は `0`、`2` は `1` に clamp。空文字、`true`、`abc` は `0`。`0.5junk` は `0.5` として変換 |
| `HY4_PF_STREAM=0`、または `pf_init()` が初期化途中で return | 本変数を読まない | 適用されない | `pf_init()` が呼ばれないか、読み取り行より前に return するため |

既定の `-1.0` は固定割合ではなく自動選択を表す。`0` 以上なら自動較正・小規模 miss 用の自動全量分担を使わず、指定割合を採用する（同 `:381, 643, 2275-2281, 2321`）。

目標候補数は割合に `nc`（CPU 常駐 tier-2 miss expert 数）を掛け `lround` した値で、割合が `0.999` 以上なら全候補を目標にする。それ未満では目標を最低 1 件とし、さらに `HY4_DEC_PCIE_MIN_CNT` の閾値以上の token multiplicity を持つ候補だけを選ぶ。同変数の既定値は 1、設定時は `atoi` 後に最低 1 へ clamp される。割合が `0.001` 以下なら PCIe への割当て処理自体に入らないため、範囲内のごく小さい値でも候補が選ばれない（同 `:400, 643-644, 2283-2301`）。

## 有効になる条件

- HY4 HIP Runner が hybrid 状態であること。hybrid 初期化時に CPU 常駐 expert を設定し `hyb = true` にする（`engine/src/hy4flash/run/hy4_graph.hip.h:1568-1583`）。
- `HY4_PF_STREAM` が未設定または `atoi` の結果が 0 以外であること。`HY4_PF_STREAM` が空文字、`0`、数値変換不能文字列の場合は `pf_init()` を呼ばない（同 `:1706-1708`）。
- `pf_init()` が expert arena の確認、scratch 容量の確保を通過して `HY4_DEC_PCIE_SHARE` の読み取りまで進むこと。arena に対象 expert がなく `maxb` が 0 の場合、scratch が 64 MiB 未満の場合、bounce ring の確保に失敗した場合は、その前に return する（同 `:545-560, 596-619`）。
- 実際に効果が出るのは `run_hybrid_miss_layer()` で PCIe 条件 `pcie_ok` が成立するときに限る。具体的には vcache が凍結されておらず、prefill streaming が初期化済みで、`T <= 8`、CPU 常駐 tier-2 の候補があり、scratch・動的 expert table と必要な bounce buffer が使えること（同 `:2217-2225, 2271-2286`）。
- `HY4_DEC_PCIE_MIN_CNT` は割合が `0.999` 未満のとき候補の最小出現数を制限する。候補数・buffer 容量によっては指定割合の目標数より実際に PCIe へ送る数が少なくなる（同 `:400, 2291-2301`）。
- cold miss がある場合は自動時の特別な全量分担を適用しない。明示割合は通常の CPU 常駐候補の選択に使われるが、cold expert 自体は `cands` に入らない（同 `:2210-2225, 2275-2281`）。

## 実行時の詳細

環境変数は `pf_init()` の初期化時に読み、Runner の `dec_pcie_share` メンバーに保持する。リクエストごとに再読込するコードはない。プロセス実行中に環境値を変更しても、既に初期化された Runner の値は更新されない（`engine/src/hy4flash/run/hy4_graph.hip.h:381, 545-546, 639-645`）。

実行時には各 layer の routed expert index を集計し、CPU 常駐の tier-2 miss を候補化する。PCIe 条件が有効で割合が `0.001` より大きいとき、候補を token multiplicity の降順に並べ、割合に応じた件数を上限として選ぶ。選択された expert の重みを pinned arena から直接、または bounce buffer 経由で scratch へ転送し、GPU で `moe_experts(..., accum=1)` を実行する。選ばれなかった miss は CPU pool 側の計算 mask に残る（同 `:2210-2225, 2286-2301, 2303-2324, 2348-2416`）。

環境変数未設定時は、`T == 1` と `T >= 2` の較正状態を分ける。最初は bounce / arena-pinned の別に応じた既定割合を使い、GPU と CPU の処理速度を測定して割合を更新する。さらに `nc <= 8`、cold miss なし、PCIe 条件成立なら、較正前でも小規模 miss 全体を GPU に送る特例がある。明示値が設定されるとこの自動分岐は使われず、較正も要求されない（同 `:382-400, 2227-2254, 2275-2281, 2321-2322`）。

## ログと測定値

この変数の値を表示する専用ログや、無効値を知らせる警告はない。自動設定時に較正が成立し、各 bucket で GPU / CPU がそれぞれ 32 expert 以上、サンプルが 24 回以上になると、stderr に `[hybrid] calibrated PCIe/CPU miss split (...)` と GPU / CPU の expert 毎ミリ秒および `pcie_share` が出る。明示割合では `want_cal` が false になるため、この較正ログは本変数を使った割合について出ない（`engine/src/hy4flash/run/hy4_graph.hip.h:2240-2251, 2321`）。

prefill streaming 初期化で scratch buffer または bounce ring を用意できないときは stderr に `[hybrid] prefill streaming disabled: ...` が出て return する。この場合、本変数を読み取る行まで進まず、PCIe miss 分担は動かない（同 `:597-600, 617-619, 643-645`）。HIP API の失敗が `HCK` 経由で発生した場合は `HIP error %d (%s) at %s:%d` を stderr に出して終了コード 3 で終了する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。

この変数を指定した構成の Strata 資料上の測定値は確認できない。`docs/DETAILS.md` の `--pcie-frac` 説明は一般設定の概要であり、本変数やこの HY4 経路の測定値を示すものではない（`docs/DETAILS.md:142-148, 283-287`）。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:380-401, 545-646` — メンバー既定値、初期化と環境変数の読み取り。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1568-1583, 1704-1708` — hybrid 状態と streaming 初期化条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2186-2225, 2271-2324` — miss 候補、適用条件、割合・閾値による分岐。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2333-2445` — expert 重み転送、GPU / CPU 計算と自動較正。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — HIP エラー時の出力と終了。
