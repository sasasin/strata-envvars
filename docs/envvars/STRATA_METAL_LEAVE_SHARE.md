# `STRATA_METAL_LEAVE_SHARE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal engine の SSD expert streaming で、RAM が 64 GB 以上の Mac における匿名メモリの footprint 上限を計算するとき、macOS 側に残す RAM の割合を指定する。既定値は `0.40`。この上限は GPU working set と比較され、小さい方が cap になる。上限から expert arena の自動予算を算出するが、環境変数自体は streaming を有効化しない。streaming の選択は `STRATA_METAL_STREAM` または常駐モデルの適合判定による（`engine/metal/src/engine/window.cpp:738-743,1726-1727,1765-1768`; `engine/metal/src/engine/arena_budget.h:72-89`; `engine/metal/src/engine/stream.cpp:34-49`）。

この割合は `STRATA_METAL_KEEP_FREE_GB` などが決める最低確保量と併せて `max` で適用される。64 GB 未満では値を読んでも cap 計算に使われない。常駐モデル用の cap は別の `kResidentLeaveShare` を使い、この変数では変わらない（`engine/metal/src/engine/arena_budget.h:44-47,75-96`）。

## 値と判定

`Window::stream_arena` が `std::getenv` で設定有無を確認し、設定されていれば `std::atof` で変換する。未設定時は `ArenaMem::leave_share = -1` のままで、cap 計算時に既定の `kLeaveShare = 0.40` が使われる。空文字や数値として読めない文字列は `atof` により `0` となるため、明示的なゼロとして扱われる。先頭の空白と数値部分の後ろに続く文字は `atof` の変換規則に従い、Strata 側で全体一致やエラー検査、範囲 clamp はしない。負の変換結果は cap 計算側の `leave_share >= 0` 判定を満たさず、既定値に戻る（`engine/metal/src/engine/window.cpp:1765`; `engine/metal/src/engine/arena_budget.h:44-47,75-89`）。

| 条件 | unset | 有効になる値（例） | 無効値・既定値になる値（例） |
| --- | --- | --- | --- |
| RAM 64 GB 以上、streaming の arena cap | `0.40` | `0.30`, `1`, `0`（それぞれ RAM の30%、100%、0%を leave-share 候補にする） | `-0.1` は既定の `0.40`。`abc`、空文字、`true` は `atof` の結果 `0`。`0.3junk` は数値部分 `0.3` に変換 |
| RAM 64 GB 未満 | `leave_share` は cap に影響しない | 変換値は保存されるが cap では未使用 | 設定値にかかわらず `arena_keep` の最低量が使われる |

値の範囲制限はありません。0以上ならその数値がそのまま割合として計算に入ります（1超も clamp されません）。`NaN` のように比較 `>= 0` が偽となる変換結果は既定値にフォールバックします。負値も同様です（`engine/metal/src/engine/arena_budget.h:85-89`）。

## 有効になる条件

- Metal engine の streaming 経路に入り、`Window::stream_arena` が arena を作ること。`STRATA_METAL_STREAM=1` は streaming を強制し、`=0` は止める。未設定または他の値では `ExpertStream::wanted` がモデル重量と resident cap を使って自動判定する。自動判定にはこの変数ではなく resident 用の 30% ルールが使われる（`engine/metal/src/engine/stream.cpp:34-49`; `engine/metal/src/engine/window.cpp:738-743,1560`）。
- RAM が 64 GB 以上であること。これ未満では `leave_share` を設定しても footprint cap に反映されない（`engine/metal/src/engine/arena_budget.h:77-89`）。
- `STRATA_METAL_KEEP_FREE_GB` が指定されている場合、その値と `share * phys`、取得できれば `filecache_min + 12 GB` の最大値が macOS に残す量となる。従って share を小さくしても他の下限が勝つ場合がある（`engine/metal/src/engine/window.cpp:1755-1765`; `engine/metal/src/engine/arena_budget.h:78-89`）。
- `STRATA_METAL_ARENA_GB` が0以上に変換される場合、arena 予算は明示値で固定され、`arena_budget`、事前縮小、段階的な増加チェックはこの cap によって制限されない。ただし計画ログと充填後の cap 表示・超過判定には引き続きこの値が使われる（`engine/metal/src/engine/window.cpp:1763-1768,1781-1791,1796-1806,1810-1815`; `engine/metal/src/engine/arena_budget.h:112-117,144-158`）。

## 実行時の詳細

`Window::stream_arena` の呼び出しごとに、arena 状態・メモリ統計を集めた後に環境変数を読み、ローカルの `ArenaMem` に値を設定する。`static` cache はないが、値はその arena 計画・縮小再試行・充填後検査に使われる。通常、arena が `ready()` になると後続の decode/prompt 経路では再作成されない。プロセス中に環境を変更しても、すでに作成済みの arena の計算結果は更新されない（`engine/metal/src/engine/window.cpp:1726-1727,1749-1768,1795-1815`; `engine/metal/src/engine/window.cpp:1560,3037-3039,3137-3139`）。

自動予算では `footprint_cap - footprint_base - PLE reserve` も候補にして arena を制限する。予算が2 GB未満なら低 hit rate を示す stderr 行を出し、予算を最低1 GBに引き上げて続行する。空きメモリが計画時より減ると縮小を試し、`make_arena` が失敗し再試行上限に達するなどすると呼び出し元へ失敗を返す。明示的な `STRATA_METAL_ARENA_GB` は cap を超えても保持され、ログで警告材料として示される（`engine/metal/src/engine/arena_budget.h:99-117,144-158`; `engine/metal/src/engine/window.cpp:1769-1774,1781-1806`; `engine/metal/src/engine/stream.cpp:450-455`）。

この変数に対応する CLI 引数や設定ファイル上書きは確認できない。`STRATA_METAL_ARENA_GB` は arena サイズを指定する別の環境変数で、組み合わせると上記のとおり明示 arena が cap 制約を迂回する（`engine/metal/src/engine/window.cpp:1763-1768`; `engine/metal/src/engine/arena_budget.h:112-117`）。

## ログと測定値

変数の値そのものを表示する専用ログや無効値の警告はない。streaming の arena 計画時に stderr へ次の format string を出す（`%.1f` 等は実数値で置換される）。`STRATA_METAL_ARENA_GB` が cap を超える計画の場合、末尾の `%s` に ` - STRATA_METAL_ARENA_GB is above the cap: kept as set (your choice), but a Mac that runs short of memory can freeze (watchdog panics seen at 90+ GB resident of 128)` が入る。

```text
strata metal stream: planned resident footprint %.1f GB = arena %.1f + %.1f held before it + %.1f reserved for the n-gram table; cap %.1f GB = the lesser of the GPU working set %.1f GB and the RAM %.1f GB less %.1f GB left to macOS and its file cache%s
```

充填後のログは `strata metal stream: resident footprint after the fill: the process holds %.1f GB (%.1f GB resident), planned %.1f GB, cap %.1f GB%s` で、超過時の末尾は ` - OVER THE CAP`。低予算時は `strata metal stream: only %.1f GB left for the expert arena (the GPU working set %.1f GB, RAM %.1f GB, %.1f GB allocated): expect a low hit rate` を出す（`engine/metal/src/engine/window.cpp:1769-1774,1781-1791,1809-1815`）。

## 根拠

- `engine/metal/src/engine/window.cpp:1726-1727,1749-1768` — streaming arena 計画時の環境読み取り。
- `engine/metal/src/engine/arena_budget.h:44-47,72-96,99-117,144-158` — 既定値、RAM 閾値、footprint cap、arena 予算と明示値の扱い。
- `engine/metal/src/engine/stream.cpp:34-49,450-455` — streaming 選択条件と arena 作成失敗経路。
- `engine/metal/src/engine/window.cpp:738-743,1560,1781-1819,3037-3039,3137-3139` — streaming 呼び出し、ログ、arena の初回作成。
- `docs/MAC.md:261-280`; `docs/SETTINGS.md:162-170` — 文書上の設定説明。`MAC.md` は64 GB以上の streaming 用と記載し、ソースの閾値と一致する。
