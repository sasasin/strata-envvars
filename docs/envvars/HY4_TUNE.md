# `HY4_TUNE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の HY4 `Runner` における decode / verify 用の最適化を、整数ビットマスクで選択する変数。通常のモデル・ルーティング結果を変える設定としてではなく、投影の融合、router top-16、MoE の中間変換省略などの実装経路を切り替える。ソースコメントは各変更を「same numbers bit for bit」と説明している。読み取りは `engine/src/hy4flash/run/hy4_graph.hip.h` の `Runner::tune_init` にあり、同じ `Runner` は CLI と serve の両方から初期化される（`engine/src/hy4flash/run/hy4_main.hip.cpp:11,692-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:307-317`）。

## 値と判定

`getenv("HY4_TUNE")` の結果を `atoi` に渡し、未設定なら `TUNE_DEFAULT` を使う。ソース内の既定値は `834`（`#ifndef TUNE_DEFAULT` のためビルド時に別定義される可能性はある）。数値文字列全体の検証、範囲検査、clamp、無効値警告はない。`atoi` が読む先頭の数値部分で決まり、空文字・数値で始まらない文字列は `0`、数値の後ろの文字は無視される。空白や符号は `atoi` の変換規則に従う。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---:|---|---|
| HIP HY4 Runner、`TUNE_DEFAULT` を別定義しない場合 | `834`（`2+64+256+512`） | 対応ビットを含む整数。`834` は4機能すべて、`2` は TOPK のみ、`0anything` は `0` として全ビット無効 | `0`、空文字、`true`、`false`、`garbage` は `atoi` 結果が `0`。未知ビットだけの `1` は個別機能を有効にしないが、後述の非ゼロ初期化は行う |

ビットの意味は次のとおり（`engine/src/hy4flash/run/hy4_graph.hip.h:1350-1355`）。

| ビット | 効果 |
|---:|---|
| `2` (`TN_TOPK`) | router の top-16 選択を `k_router_topk_w32` に切り替える。通常 MoE、HYB、graph emit のルーター経路で参照される。 |
| `64` (`TN_NOF2H`) | 条件を満たす MoE で fp32 latent の fp16 変換前後のパスを省き、expert kernels が fp32 を読み reduce が fp16 結果を書く経路を選ぶ。 |
| `256` (`TN_ROUTE`) | 条件を満たす1 token decode で router が選択 expert の record をコピーし、one-token expert kernels を使う経路を選ぶ。 |
| `512` (`TN_ENG`) | 条件を満たす Engram の1 token 経路で5個の projection を1 launch にまとめる。 |

## 有効になる条件

- この読み取りは `engine/src/hy4flash/run/hy4_graph.hip.h` の HIP `Runner` にある。調査した参照全体では、SYCL・Metal 実装、setup、別の helper による同名環境変数の読み取りは見つからなかった。
- `tune == 0` なら `tune_init` は直ちに戻り、下記の個別最適化に加えて、同関数が構築する `lm_attn` / `lm_sh` / `lm_mlp0` の融合 projection も使われない。非ゼロなら、認識されないビットだけでも初期化・構築・ログ出力を行う（`hy4_graph.hip.h:1370-1375,1396-1432`）。
- `TN_TOPK` は該当するルーター経路でビットを検査する。未設定時の既定 `834` には含まれる。router の経路は各実行モードで呼ばれる箇所が異なる（`hy4_graph.hip.h:2712-2717,2966-2968,3026-3028`）。
- `TN_NOF2H` は通常 MoE で `T <= 4` かつ expert peer がない場合だけ選択される。hybrid の分岐や peer 利用時はこの条件を満たさず、従来の変換・expert 経路になる（`hy4_graph.hip.h:2721-2734`）。Graph capture のキーにも `T <= 4`、非 hybrid、非 split-experts 条件が入る（`hy4_graph.hip.h:3083-3085`）。
- `TN_ROUTE` は `T == 1`、非 hybrid、expert peer なしの場合だけ `route_now` となり、Graph capture でも同じ条件がキーに反映される（`hy4_graph.hip.h:2710-2715,3083-3085`）。
- `TN_ENG` は `T == 1` に加え `lm_eng[mo].d_jobs` が存在する必要がある。`lm_eng` の構築には Engram が ready でメタデータに4層以上あり、各モジュール内の5 weight が同じ format / 列数で、format が `FMT_Q8ROW` でない条件がある。満たさなければ5つを個別に実行する（`hy4_graph.hip.h:1376-1394,1944-1955`）。
- 非ゼロ時に構築する `lm_attn` / `lm_sh` / `lm_mlp0` は対象 weight の format と列数が一致し、`FMT_Q8ROW` でない必要がある。実行時は `lm_ok_m(T)` が `T <= 8`、`skd::lin_gemv_max_m()` 以下を要求し、CUDA+MMA かつ `lin_dp4a()` の場合も使わない。これらの融合 projection は個別ビットでなく `tune != 0` による構築有無で切り替わる（`hy4_graph.hip.h:1363-1369,1400-1432,2088-2100,2655-2662,2683-2691`）。
- CLI 引数や別環境変数による `HY4_TUNE` の上書きは、対象ソース内で確認できなかった。

## 実行時の詳細

CLI / serve の `Runner::init` 中に `tune_init` が1回呼ばれ、そこで値を読み `tune` に保存する。リクエストや decode step ごとの再読み込みはないため、実行中にプロセス環境を変更しても既存 Runner の値は変わらない（`engine/src/hy4flash/run/hy4_graph.hip.h:1370-1434,1705-1709`）。

非ゼロ値では `slot_rec` の device memory を確保し、MoE workspace を初期化してから、format / shape 条件を満たす投影群を `linear_multi_build` で準備する。通常の attention / shared expert / layer-0 MLP では `T <= 8` 等の条件が揃えば融合 projection を呼び、それ以外は個別 projection に戻る（`hy4_graph.hip.h:1373-1432,2088-2100,2655-2662,2683-2691`）。Engram・MoE の各ビットはそれぞれ追加条件を満たす実行時だけ作用する（`hy4_graph.hip.h:1944-1955,2710-2734`）。

## ログと測定値

`tune == 0` では初期化関数が早期 return するため、この変数のログは出ない。非ゼロなら初期化後に stderr へ `[tune] HY4_TUNE=%d\n` を出し、`atoi` 後の整数を表示する（`engine/src/hy4flash/run/hy4_graph.hip.h:1370-1375,1434`）。

この変数について条件付き性能測定値を記載した `docs/DETAILS.md` 等の資料は確認できなかった。初期化中の `hipMalloc` / `hipMemset` が失敗すると `HCK` が stderr に `HIP error %d (%s) at %s:%d\n` を出して `exit(3)` する。この失敗は `Runner::init` の `err` 戻り経路ではない（`engine/src/hy4flash/run/hy4_graph.hip.h:1373-1375`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。通常の `init` false 戻りは CLI で `init: %s` と stderr に出して終了コード1、serve で `ERR init: %s` を protocol に返して終了コード1となる（`engine/src/hy4flash/run/hy4_main.hip.cpp:702-705`; `engine/src/hy4flash/run/hy4_serve.hip.h:314-317`）。

## 根拠

- 読み取り・parse・0 の早期 return・ビット定義・ログ: `engine/src/hy4flash/run/hy4_graph.hip.h:30-32,1350-1375,1434`
- 非ゼロ値の初期化、融合投影の構築と適用: `engine/src/hy4flash/run/hy4_graph.hip.h:1373-1432,2088-2100,2655-2662,2683-2691`
- ビットごとの実行条件と分岐: `engine/src/hy4flash/run/hy4_graph.hip.h:1944-1955,2710-2734,2966-2968,3026-3028,3083-3085`
- CLI / serve の呼び出し、HIP error の終了経路: `engine/src/hy4flash/run/hy4_main.hip.cpp:692-705`; `engine/src/hy4flash/run/hy4_serve.hip.h:307-317`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`
