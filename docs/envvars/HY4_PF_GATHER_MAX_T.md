# `HY4_PF_GATHER_MAX_T`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 の hybrid prefill streaming で、CPU 層の expert を使用中の expert だけ集めて転送する方式と、層全体を分割して先読み転送する方式との切替上限を指定する。`pf_gather_max_T` の既定値は 4096。prefill chunk の token 数 `T` がこの値未満なら（他の条件も満たす場合）active-expert gather、値以上なら full-layer streaming になる。これは転送方式の境界であり、streaming 自体を有効にする設定ではない。実装は `Runner::pf_init`、`Runner::pf_use_gather`、`Runner::moe_hybrid_tail` にある。[`engine/src/hy4flash/run/hy4_graph.hip.h:372-406`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:2473-2477`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)

## 値と判定

`pf_init()` で `getenv` が null でなければ `atoi` の結果をそのまま格納する。値の全体検査、範囲検査、clamp、無効値時の fallback はない。したがって空文字列や数字で始まらない文字列は `atoi` により 0、`"2048tail"` は 2048、先頭空白と符号は `atoi` の規則で扱われ、負数もそのまま格納される。数値として表現できる範囲外の入力に対する結果は実装で保証されない。大文字小文字の規則は該当しない。

| ビルド／実行経路 | unset | 設定時の値と効果 |
|---|---|---|
| HY4 CUDA または HIP runner で `pf_init()` が実行される | 4096。`T < 4096` が gather 候補、`T >= 4096` が full-layer streaming | `atoi` の整数結果を境界に使う。例: `2048` は T=2048 で gather 候補、T=2048 以上で条件を満たすと full-layer。`4096` は既定と同じ。`0`、空文字、`abc`、`-1` は T が 0 以上なら gather 条件を満たさず full-layer 側。`2048tail` は境界 2048。 |

判定式は `pf_stream && T >= pf_min_T && T < pf_gather_max_T && h_bounce[0] != nullptr`。`pf_min_T` の既定値は 128 で、別変数 `HY4_PF_MIN_T` が設定されていればそちらも `atoi` で上書きされる。境界値と等しい T は gather ではなく full-layer 側に入る。[`engine/src/hy4flash/run/hy4_graph.hip.h:372-406`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:639-646`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)

## 有効になる条件

- `strata-hy4` が `STRATA_BUILD_HY4` 有効でビルドされ、CUDA または HIP backend が選ばれていること。この変数を読むコードは `engine/src/hy4flash/run/hy4_graph.hip.h` にあり、CMake は HY4 target を CUDA/HIP のいずれかに限定している。[`engine/CMakeLists.txt:846-851`](../../../../Niko1221/Strata/engine/CMakeLists.txt) [`engine/CMakeLists.txt:884-891`](../../../../Niko1221/Strata/engine/CMakeLists.txt)
- `Runner::init()` 中に `hyb` が真、かつ `HY4_PF_STREAM` が未設定または `atoi` 結果が 0 以外であり、`pf_init()` が呼ばれること。`hyb` は `g.cpu_mask` が空でない場合に CPU expert 初期化後に真になる。`HY4_PF_STREAM=0`、空文字、数字で始まらない値では `pf_init()` は呼ばれない。[`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:1706-1708`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)
- streaming 初期化が scratch buffer や pinned bounce buffer の確保に成功し、`pf_init()` が `pf_stream = true` まで到達すること。CPU 層 expert のデータ量が 0 なら `pf_init()` はログなしで戻る。空き GPU memory 不足、または bounce ring 確保失敗では streaming が無効化され、対象変数による切替も使われない。[`engine/src/hy4flash/run/hy4_graph.hip.h:549-563`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:593-645`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)
- 実際の chunk で `T >= pf_min_T` であること。これを満たさないと prefill streaming 分岐自体に入らない。`T < pf_gather_max_T` でも pinned bounce buffer が存在しない場合は gather 条件が偽になり、full-layer 側の処理が選ばれる。[`engine/src/hy4flash/run/hy4_graph.hip.h:405-406`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:2473-2491`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)

この環境変数より優先する CLI 引数や設定ファイルは読み取り箇所にない。CLI 等が決める chunk の T は判定への入力だが、境界値自体は `HY4_PF_GATHER_MAX_T` が設定されていればその値で置き換わる。[`engine/src/hy4flash/run/hy4_graph.hip.h:639-640`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:3384-3404`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)

## 実行時の詳細

値は `Runner::init()` から呼ばれる `pf_init()` で初期化時に一度だけ読み込む。`static` cache ではなく `Runner` のメンバー `pf_gather_max_T` に保存され、その後の chunk ごとの判定で参照される。プロセス実行中に環境を変更しても、このメンバーは再読込されない。別の CLI 値との再合成や子プロセスへの転送はこの実装にない。[`engine/src/hy4flash/run/hy4_graph.hip.h:372-373`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:639-646`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)

`T >= pf_min_T` で gather 条件を満たす場合、`moe_hybrid_tail()` は routing index を host に取り、該当層のうち実際に選択され、VRAM/vcache にない CPU 層 experts のみを集めて bounce buffer に詰め、複数 batch で転送・実行する。それ以外の streaming 経路は事前構築された層 group を DMA しながら expert 計算を進める。したがってこの変数が変えるのはこの二方式の選択境界であり、routing 結果や対象 expert の選択そのものではない。[`engine/src/hy4flash/run/hy4_graph.hip.h:2490-2511`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:2533-2571`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:2573-2603`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)

## ログと測定値

初期化が最後まで成功し `pf_build_groups(true)` が呼ばれると stderr に `[hybrid] prefill streaming on (...) ... active for T >= %d (gather < %d)` が出て、後半の `%d` に `pf_gather_max_T` が表示される。これは選択境界のログで、個々の chunk がどちらの経路を通ったかを知らせるログではない。CPU 層 expert のデータ量が 0 の場合は `pf_init()` が先に戻るため、このログは出ない。GPU memory 不足では `[hybrid] prefill streaming disabled: no room for a scratch buffer ...`、pinned bounce ring の割当失敗では `[hybrid] prefill streaming disabled: cannot allocate ... pinned bounce ring (WDDM/commit limit)` が stderr に出る。これらの失敗経路ではこの値による切替は行われない。対象変数について条件付き測定値を記載した Strata 資料は見つからなかった。[`engine/src/hy4flash/run/hy4_graph.hip.h:541-543`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:549-563`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h) [`engine/src/hy4flash/run/hy4_graph.hip.h:597-619`](../../../../Niko1221/Strata/engine/src/hy4flash/run/hy4_graph.hip.h)

## 根拠

- 読み取りと既定値・範囲制限なし: `engine/src/hy4flash/run/hy4_graph.hip.h:372-373,639-646`
- 有効条件と切替式: `engine/src/hy4flash/run/hy4_graph.hip.h:405-406,1706-1708,2473-2491`
- 経路ごとの処理: `engine/src/hy4flash/run/hy4_graph.hip.h:2490-2571,2573-2603`
- ログと streaming の初期化失敗: `engine/src/hy4flash/run/hy4_graph.hip.h:541-543,549-563,597-619`
- HY4 の build 条件: `engine/CMakeLists.txt:846-851,884-891`
