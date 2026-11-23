# `HY4_PF_STREAM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4-Flash の GPU runner が hybrid 配置で動くとき、CPU 側に置かれた expert を prefill 中に GPU の scratch buffer へ流すための初期化 `pf_init()` を抑止するスイッチ。未設定なら初期化を試み、設定値の `atoi` 結果が 0 なら試みない。初期化が成功すると、後続の chunk 処理で `pf_stream` が有効になり、`T >= pf_min_T` の prefill 経路で streaming または active-expert gather が選ばれる。生成内容を変える設定であるとはソースから確認できない。`engine/src/hy4flash/run/hy4_graph.hip.h:371-406, 1706-1708, 3402-3404`。

## 値と判定

`Runner::init()` 内で `getenv("HY4_PF_STREAM")` の有無を調べ、存在すれば `atoi()` の結果が 0 以外かを判定する。未設定は `pf_init()` を許可し、設定ありで `atoi()` が 0 なら抑止する。文字列全体の検証や boolean 文字列の比較はない。`atoi()` は先頭の空白と符号を許し、数値部分の後ろは無視するため、数値で始まらない文字列は 0 になる。

| 条件 | unset | `pf_init()` を呼ぶ値 | 呼ばない値 |
|---|---|---|---|
| HY4 の CUDA または HIP runner で hybrid 状態 | 呼ぶ | `1`, `2`, `-1`, `1tail`, ` 1` など、`atoi()` が 0 以外 | `0`, 空文字, `false`, `true`, `0tail`, `tail1` など、`atoi()` が 0 |
| hybrid 状態でない | 参照箇所の左辺 `hyb` が false のため評価しない | 該当なし | 該当なし |

`true` も `atoi("true") == 0` となり無効側である。値の大小による境界・clamp はなく、0 か非 0 かだけを見る。`atoi()` の数値範囲外入力の結果はこのコードで検査されない。`engine/src/hy4flash/run/hy4_graph.hip.h:1706-1708`。

## 有効になる条件

- このコードが使われる `strata-hy4` runner であること。CMake はこの実装を CUDA または HIP としてコンパイルし、Metal / SYCL 用 runner とは別扱いにしている。`engine/CMakeLists.txt:846-852, 884-889`。
- `Runner::init()` で `g.cpu_mask` が空でなく、CPU expert 初期化が成功して `hyb = true` まで到達すること。そうでなければ環境変数の条件自体を評価しない。`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565, 1580-1583, 1706-1707`。
- `HY4_PF_STREAM` が未設定、または設定時に `atoi()` が非 0 であること。設定時に 0 なら `pf_init()` は呼ばれず、prefill streaming の初期化は行われない。`engine/src/hy4flash/run/hy4_graph.hip.h:1707`。
- `pf_init()` が CPU expert view を走査して少なくとも一層分の対象データを見つけること。`maxb == 0` なら何も設定せず return する。また、GPU scratch の見積り容量が 64 MiB 未満、または bounce buffer の確保に失敗した場合も streaming を無効化して return する。後者の判定・ログは bounce 方式の場合。`engine/src/hy4flash/run/hy4_graph.hip.h:545-562, 593-620`。
- 初期化後も chunk の `T` が `pf_min_T` 以上であること。既定値は 128 で、`HY4_PF_MIN_T` で変更される。さらに `pf_gather_max_T`（既定値 4096、`HY4_PF_GATHER_MAX_T` で変更）と bounce buffer の有無により、通常の pipe と active-expert gather が分岐する。`HY4_PF_STREAM` 自体に CLI 引数の優先順位や上書き処理はない。`engine/src/hy4flash/run/hy4_graph.hip.h:371-406, 639-646, 3402-3404`。
- `pf_init()` が呼ばれた場合に限り、関連設定として `HY4_PF_BOUNCE` が host arena pinning / bounce ring 選択に、`HY4_PF_BUF_MB` が buffer 容量上限に、`HY4_PF_CPU_FRAC` が prefill の CPU/GPU 分割に関係する。`HY4_DEC_PCIE_SHARE` と `HY4_DEC_PCIE_MIN_CNT` も同じ初期化内で読み取られる。これらは `HY4_PF_STREAM` の値を上書きしない。`engine/src/hy4flash/run/hy4_graph.hip.h:566-568, 587-596, 639-646`。

## 実行時の詳細

判定は `Runner::init()` の初期化中に行われる。環境値を保存する static cache や、chunk ごとに `HY4_PF_STREAM` を再読込する処理はない。判定箇所は `getenv()` を2回呼ぶが、その後の有効状態は `pf_stream` で保持される。プロセス起動後に環境を変更しても、初期化済み runner の状態は変わらない。`engine/src/hy4flash/run/hy4_graph.hip.h:371, 1707, 545-646`。

`pf_init()` は CPU expert を走査し、メモリ容量を確認してから GPU scratch / table、stream、event を準備する。最後まで到達した場合に `pf_stream = true` として group を構築する。実行時には `pf_active(T)` が `pf_stream && T >= pf_min_T` を判定し、`forward_chunk()` が `pf_pipe` を決める。`pf_use_gather(T)` が真なら pipe を使わず、active-expert gather 側へ進む。`HY4_PF_STREAM=0` では `pf_init()` が呼ばれないので `pf_stream` は初期値 false のままで、これらの streaming 経路は選択されない。`engine/src/hy4flash/run/hy4_graph.hip.h:371-406, 545-646, 3402-3404`。

通常 CLI と server のどちらも `Runner::init()` を呼び、環境変数に対する CLI 固有の上書きはない。server は初期化失敗時に `ERR init: ...` を返す。`HY4_PF_STREAM` が 0 の場合そのものは初期化エラーにせず、streaming の初期化を飛ばす。`engine/src/hy4flash/run/hy4_main.hip.cpp:703-705`, `engine/src/hy4flash/run/hy4_serve.hip.h:315-317`。

## ログと測定値

`pf_init()` が正常に group 構築まで進むと、stderr に `[hybrid] prefill streaming on (...)` で始まる行を出す。CPU expert が見つからない場合は何も出さず return する。GPU scratch 用の空きが足りない場合は `[hybrid] prefill streaming disabled: no room for a scratch buffer ...`、bounce ring を確保できない場合は `[hybrid] prefill streaming disabled: cannot allocate ... pinned bounce ring (WDDM/commit limit)` を出す。`HY4_PF_STREAM=0` ならこの関数を呼ばないため、これらの初期化ログも出ない。いずれも `engine/src/hy4flash/run/hy4_graph.hip.h:540-543, 562, 597-619`。

`docs/DETAILS.md` にこの変数固有の記述や測定値は見つからなかった。性能差や生成結果への影響はここでは評価していない。

## 根拠

- `engine/CMakeLists.txt:846-852, 884-889` — HY4 runner の CUDA / HIP build 条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:371-406, 545-646, 1706-1708, 3402-3404` — 初期値、値の判定、prefill streaming の初期化と利用条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565, 1580-1583` — hybrid 状態が成立する条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:703-705`, `engine/src/hy4flash/run/hy4_serve.hip.h:315-317` — CLI / server からの初期化と失敗の観測。
