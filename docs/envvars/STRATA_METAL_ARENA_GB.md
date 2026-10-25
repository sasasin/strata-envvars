# `STRATA_METAL_ARENA_GB`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の SSD streaming 経路で、ルーティングされる expert を置く arena の目標サイズを GB 単位で指定します。未設定なら GPU の working set、macOS が圧縮・swap せずに渡せるメモリ、プロセスの footprint 上限などから自動計算します。設定値は自動計算の上限を上書きします。

この変数を読む箇所は `metal/src/engine/window.cpp` の `Window::stream_arena()` です。`stream_` が有効で arena がまだ ready でない場合に呼ばれるため、通常の resident model 経路では使われません（`window.cpp:1016, 2021, 2115`）。

## 値と判定

`std::atof()` で値を `double` に変換します。文字列全体の妥当性は検査せず、変換できる数値の後ろにある文字列は無視されます。

| 入力 | arena の目標サイズ |
|---|---|
| unset | 自動計算。最低1 GB |
| 数値が負 | 自動計算。`arena_gb < 0` として扱われる |
| 0、空文字、数値で始まらない文字列 | `atof()` の結果は0。明示値として扱われ、後段で最低1 GBに補正 |
| 0以上の数値 | その数値を10進GB（`1 GB = 1e9 bytes`）に換算 |
| 数値の後ろに文字がある | 数値部分を変換。例: `2junk` は2 GB相当 |

`atof()` が NaN を返す表記は `arena_gb >= 0` の比較を通らず、自動計算になります。正の無限大や、後段の `uint64_t` に収まらない巨大値に対する範囲検査はありません。そのような値の変換結果はこの実装で保証されません。

arena 予算が2 GB未満の場合は stderr に `strata metal stream: only ... GB left for the expert arena ...: expect a low hit rate` を出し、予算を最低1 GBにします。この閾値は警告と下限補正に使われ、2 GB未満の値を一律2 GBにはしません。したがって空文字や `0` は1 GBになります。

## 有効になる条件

- Metal の expert streaming が有効で、`Window::stream_arena()` に到達することが必要です。変数自体に OS/backend の別分岐はありませんが、この実装は Strata の Metal engine に属します。
- 自動計算では、GPU working set・現在利用可能なメモリ・プロセス footprint と macOS 用の空き・PLE（n-gram table）用 reserve を考慮します。基本の footprint cap は `min(working_set, RAM - leave)` で、64 GB以上の Mac では `leave` に RAM の40%などの条件も使います（`arena_budget.h:80-89, 109-117`）。
- 0以上の明示値は自動計算を迂回します。計画 footprint が cap を超える場合も値を維持し、stderr の計画ログに `STRATA_METAL_ARENA_GB is above the cap: kept as set (your choice), but a Mac that runs short of memory can freeze ...` を付けます。cap は強制上限ではありません。
- 明示値は、arena を作る直前のメモリ再確認による縮小も受けず、段階的な fill の空きメモリ判定も通過します。未設定または負値の自動計算時だけ、再確認で小さくなり、段階 fill が macOS に残すメモリを下回りそうなら fill を止めます（`arena_budget.h:144-157`, `window.cpp:1197-1201`）。
- 計画サイズが大きすぎて4個を超える Metal buffer を必要とする場合、arena 作成は `metal stream: the arena needs more than 4 buffers (lower STRATA_METAL_ARENA_GB)` で失敗します。匿名メモリの map に失敗した場合も作成に失敗します（`stream.cpp:417-427, 433-457`）。

## 実行時の詳細

`Window::stream_arena()` は関数に入るたび `getenv()` を評価し、読み取り結果を static cache しません。値は `ArenaMem::arena_gb` に入ります。arena サイズ決定では0以上ならその値を bytes に換算し、それ以外なら GPU、RAM、footprint の各予算の最小値を使います。自動計算の式は最低1 GBを保証します（`window.cpp:1164-1169`, `arena_budget.h:111-117`）。

計画時には arena、既存 Metal allocation とプロセス footprint の大きい方、PLE reserve の合計を計算し、`planned resident footprint ...; cap ...` として stderr に出します。PLE table が mmap モードなら table の行数から予約量を見積もり、それ以外は0.5 GBを予約します（`window.cpp:1154-1189`, `arena_budget.h:99-132`）。

続いて arena は expert profile の順位を使ってスロットを配置し、最大4 bufferに分けて作成します。明示値があっても、プロファイル内でそのサイズに収まるexpertだけを arena に置きます。fill 後には実際の arena サイズ・slot 数をログに出します。未設定時にメモリ不足で fill が止まると、未使用slotは残し、停止したサイズを stderr に記録します（`stream.cpp:368-444, 479-541`）。

`docs/MAC.md` は `STRATA_METAL_ARENA_GB=N` を streaming arena のサイズ指定として一覧に挙げ、上限超過時は指定値を維持して警告する旨を記載しています。測定値をこの変数の一般的な性能効果として示す資料は確認していません。関連する MAC のメモリ上限説明は `docs/MAC.md:108`、環境変数一覧は `docs/MAC.md:196` です。

## 根拠

- 読み取り、単位換算前の取り込み、警告、計画ログ、arena 呼び出し: `metal/src/engine/window.cpp:1123-1127, 1164-1207`。
- 自動予算、明示値時の縮小・fill 判定、footprint 計算: `metal/src/engine/arena_budget.h:80-117, 120-132, 144-157`。
- slot 配置、最大4 buffer制限、メモリ確保、fill 結果: `metal/src/engine/stream.cpp:368-457, 479-541`。
- streaming 経路での呼び出し: `metal/src/engine/window.cpp:1016, 2021, 2115`。
- 文書との照合: `docs/MAC.md:108, 196`。
