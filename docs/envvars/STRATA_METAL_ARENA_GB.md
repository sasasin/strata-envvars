# `STRATA_METAL_ARENA_GB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

macOS の Metal 実装で expert を SSD から読むストリーミング経路に入ったとき、expert arena の予算を GB 単位で指定する。これは arena の正確な確保量を保証する設定ではなく、予算に収まる範囲で profile 順の expert slot を選ぶための上限として使われる。各サイズ区分の最低 slot 数は別に確保されるため、実際の arena サイズと一致しない場合がある。`Window::stream_arena` が読み取り、`arena_budget` と `ExpertStream::make_arena` に渡す（`engine/metal/src/engine/window.cpp:1726-1768`, `engine/metal/src/engine/stream.cpp:374-415`）。

## 値と判定

値は `std::getenv` で取得し、設定されていれば `std::atof` で `double` に変換する。文字列全体の妥当性検査はなく、`atof` が変換できる先頭部分を使う。未変換文字列、空文字、`true` は 0 になる。たとえば `10junk` は 10、` 2.5 GB` は 2.5 として扱われる。大文字小文字の判定はない（`window.cpp:1763-1765`）。

| 条件 | unset | 設定時に明示予算となる値 | 自動計算へ戻る値 |
|---|---|---|---|
| Metal streaming arena の初期化 | `arena_gb` は -1。GPU working set、利用可能 RAM、footprint cap から計算し、最低 1 GB | 変換結果が 0 以上。値に `1e9` を掛けて byte へ変換 | 変換結果が負数。例: `-1` |

空文字・`abc`・`true`・`0anything` は変換結果が 0 なので明示値として扱われます。計算された予算が 2 GB 未満の場合、stderr に低予算の注意を出し、arena 予算を最低 1 GB に引き上げます。負数は `arena_gb < 0` と判定され、自動計算に戻ります。`nan` も比較が成立せず自動計算側です。数値の上限・下限検査や clamp はなく、正の値はそのまま予算にします。ただし最低 slot 数や Metal buffer 数の制約で指定値どおりに確保できないことがあります（`engine/metal/src/engine/arena_budget.h:111-117`, `engine/metal/src/engine/window.cpp:1763-1773`, `engine/metal/src/engine/stream.cpp:404-415`, `engine/metal/src/engine/stream.cpp:423-450`）。

## 有効になる条件

- Metal の `Window` を使い、expert streaming が有効なときだけ arena 予算に影響する。`STRATA_METAL_STREAM=1` は streaming を強制し、`=0` は無効化する。それ以外または未設定では、`ExpertStream::wanted` が model tensor の合計と Metal working set などから自動判定する（`engine/metal/src/engine/stream.cpp:34-49`; `engine/metal/src/engine/window.cpp:736-744`）。
- `STRATA_METAL_STREAM=0`、または自動判定で resident 経路になった場合は arena を作らず、この変数は読まれない（`engine/metal/src/engine/window.cpp:738-745`, `engine/metal/src/engine/window.cpp:1726-1729`）。
- `STRATA_METAL_KEEP_FREE_GB` と `STRATA_METAL_LEAVE_SHARE` は自動予算と表示用 footprint cap に使われる。明示予算は `arena_budget` の自動計算を置き換えるが、cap 自体を変更しない。指定値が cap を超える場合も切り詰めず、そのまま使う（`engine/metal/src/engine/window.cpp:1763-1768`, `engine/metal/src/engine/arena_budget.h:80-89`, `engine/metal/src/engine/arena_budget.h:111-117`）。
- この変数より優先する CLI 引数や設定ファイルの上書きは、調査対象コードでは確認できない。streaming を選ぶ別条件は `STRATA_METAL_STREAM` である。

## 実行時の詳細

Metal window 初期化時に `ExpertStream::wanted` が streaming の要否を決め、streaming なら SSD stream を開く。環境変数自体は `Window::stream_arena` の実行時、GPU/RAM の状態を収集した後に読み込まれ、arena 予算と footprint 計画を計算する。この関数は最初の decode window または prompt GEMM 初期化から呼ばれるため、プロセス起動直後ではなく arena 初期化時の値が使われる。確保成功後は stream が ready となり、以降この arena に対して再読込しない。初期化が失敗して後で再試行される場合は再度読み込まれる（`engine/metal/src/engine/window.cpp:736-744`, `engine/metal/src/engine/window.cpp:1726-1768`, `engine/metal/src/engine/window.cpp:1795-1807`, `engine/metal/src/engine/window.cpp:3037-3040`, `engine/metal/src/engine/window.cpp:1558-1560`）。

明示予算が 0 以上なら `arena_shrink` は空きメモリ再確認の結果で予定量を減らさず、`arena_grow` も段階ごとの空きメモリ条件で充填を止めない。負値や未設定なら自動予算が適用され、メモリが計画後に減った場合は縮小を再試行し、充填中に macOS の予約分を保てなくなれば未使用 slot を残して停止する（`engine/metal/src/engine/arena_budget.h:144-158`, `engine/metal/src/engine/window.cpp:1797-1806`, `engine/metal/src/engine/stream.cpp:451-458`, `engine/metal/src/engine/stream.cpp:520-539`）。

arena は profile 順に expert slot を埋め、残りの expert は必要時に SSD から読み込まれる。大きな明示予算でも 4 個を超える Metal buffer が必要になると初期化に失敗する。arena 確保や prompt 領域の用意に失敗した場合はエラー文字列を呼び出し元へ返し、推論処理は失敗する（`engine/metal/src/engine/stream.cpp:404-415`, `engine/metal/src/engine/stream.cpp:423-463`, `engine/metal/src/engine/window.cpp:1799-1808`, `engine/metal/src/engine/window.cpp:3037-3040`, `engine/metal/src/engine/window.cpp:3120-3123`）。小さい arena では expert slot 不足時に `strata metal stream: no free slot (layer %d)` を stderr に出して終了コード 6 で終了する経路もある（`engine/metal/src/engine/stream.cpp:676`）。

## ログと測定値

- 予算が 2 GB 未満なら stderr に `strata metal stream: only %.1f GB left for the expert arena (the GPU working set %.1f GB, RAM %.1f GB, %.1f GB allocated): expect a low hit rate` を出す（`engine/metal/src/engine/window.cpp:1769-1774`）。
- 計画 arena が footprint cap を超えており、かつ変換値が 0 以上なら、計画 footprint の行に `STRATA_METAL_ARENA_GB is above the cap: kept as set (your choice), but a Mac that runs short of memory can freeze (watchdog panics seen at 90+ GB resident of 128)` を追記する。値を cap に丸める処理はない（`engine/metal/src/engine/window.cpp:1781-1791`）。
- 成功時は計画 footprint、実際に埋まった arena サイズ、充填停止の有無などを stderr に出す（`engine/metal/src/engine/window.cpp:1778-1815`, `engine/metal/src/engine/stream.cpp:536-547`）。
- `docs/MAC.md:60-67, 276` も streaming 時の arena 指定と cap 超過警告を説明しており、現行コードと整合する。ここに新しい性能測定値は加えていない。

## 根拠

- 直接の読み取り・予算計算・ログ: `engine/metal/src/engine/window.cpp:1726-1806`
- 予算の明示値と自動計算、cap・縮小・充填の違い: `engine/metal/src/engine/arena_budget.h:80-117`, `engine/metal/src/engine/arena_budget.h:144-158`
- streaming の選択条件: `engine/metal/src/engine/stream.cpp:34-49`
- arena の slot 選択、buffer 制限、失敗と成功ログ: `engine/metal/src/engine/stream.cpp:374-475`, `engine/metal/src/engine/stream.cpp:520-574`
- 初期化と最初の実行からの呼び出し: `engine/metal/src/engine/window.cpp:714-744`, `engine/metal/src/engine/window.cpp:1558-1560`, `engine/metal/src/engine/window.cpp:3037-3040`
