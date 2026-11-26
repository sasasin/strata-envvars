# `STRATA_METAL_KEEP_FREE_GB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

macOS 上の Metal SSD expert streaming が作る arena の自動容量計算で、macOS に残すメモリ量（GB）を指定する。arena が未指定の場合、空きメモリ計算と大容量 Mac の footprint 上限の双方に使われる。生成 token や expert の選択を変える設定ではなく、streaming arena の大きさと埋められる量に影響する。読み取りは `engine/metal/src/engine/window.cpp:1726-1768`、計算は `engine/metal/src/engine/arena_budget.h:80-117`。

## 値と判定

`Window::stream_arena()` が `std::getenv` で設定有無を調べ、設定されていれば文字列を `std::atof` で `double` に変換する。値の全体検証や clamp はない。数値として変換できない先頭なら `atof` は 0 になり、数値の後ろにある文字は parse の妨げにならない。空文字も 0。したがって非負値は指定値として採用され、負値は未設定時と同じ既定計算に戻る（`arena_keep()` の条件は `keep_gb >= 0`）。単位換算は 1 GB = 1,000,000,000 bytes。

| Metal streaming の状態 | unset | 設定時に有効になる値 | fallback / 特記事項 |
|---|---|---|---|
| `STRATA_METAL_ARENA_GB` が未設定、負値、または数値変換で負値 | `max(7 GB, RAM の 15%)` を残す | `0` 以上の数値。例: `0`、`1`、`7.5`、`1.5GB`（先頭の数値 `1.5` を変換） | 空文字、`abc`、`0anything` は `atof` で 0 となり、0 GB を指定した扱い。空白と符号は `atof` の数値変換に従う。数値変換後が負なら既定値へ戻る。大文字小文字の比較はしない。 |
| `STRATA_METAL_ARENA_GB` が非負値 | 同じ既定計算。ただし arena 容量自体は `STRATA_METAL_ARENA_GB` の値 | keep 値は footprint cap とログ表示に使われる | 明示 arena は `arena_budget()` の自動容量計算を置き換え、arena の shrink / grow 時にも keep 値による制限を適用しない。 |

`NaN` や負数は `keep_gb >= 0` を満たさず既定計算へ戻る。非有限値を含め入力の妥当性検査はなく、非負の無限大などは指定値として扱われるため、通常の有限 GB 値を使うこと。根拠: `engine/metal/src/engine/window.cpp:1763-1768`、`engine/metal/src/engine/arena_budget.h:44-46,80-89,111-117,144-157`。

## 有効になる条件

- macOS の Metal backend で、`ExpertStream::wanted()` がモデルを streaming 対象と判定した場合にだけ arena 構築へ進む。`STRATA_METAL_STREAM=1` は streaming を強制し、`=0` は抑止する。それ以外はモデル重みと約 12 GiB の付随メモリが resident footprint 上限に収まるかで自動判定される。`STRATA_METAL_KEEP_FREE_GB` 自体はこの streaming 判定には使われない。`engine/metal/src/engine/stream.cpp:34-49`、`engine/metal/src/engine/window.cpp:736-744`。
- streaming が選ばれても、arena がまだ ready でない状態で `Window::stream_arena()` が呼ばれる場合にだけ読み取られる。常駐モデル経路では読み取り・効果ともにない。呼び出し箇所: `engine/metal/src/engine/window.cpp:1560,3037-3039,3137-3139`。
- `STRATA_METAL_ARENA_GB` が非負値なら arena 容量はその値が優先される。`STRATA_METAL_KEEP_FREE_GB` は footprint cap と計画ログには残るが、明示 arena 値を cap で縮めない（超過時は警告文を付加）。`engine/metal/src/engine/arena_budget.h:84-117,144-157`、`engine/metal/src/engine/window.cpp:1781-1791`。
- CLI 引数や設定ファイルからこの値を上書きする処理は、Strata 所有ソース内の名前参照では確認できない。

## 実行時の詳細

`Window::stream_arena()` は物理 RAM、Metal recommended working set、すでに割り当てた buffer、プロセス footprint、利用可能メモリ、PLE の reserve を収集し、環境変数を `ArenaMem` に格納する。その後 `arena_keep()` は設定値が 0 以上なら GB を bytes に変換し、そうでなければ `max(7 GB, RAM の 15%)` を返す。自動 arena 容量では RAM 由来の予算と大容量 Mac の footprint cap の計算にこの keep 値が差し引かれる。自動容量の最低値は 1 GB。`engine/metal/src/engine/window.cpp:1726-1768`、`engine/metal/src/engine/arena_budget.h:80-117`。

arena の直前にも空きメモリを再確認し、利用可能量が減っていれば自動容量を縮めて再試行する。fill 中も次の step 後に keep 値と PLE reserve を残せるときだけ進める。`STRATA_METAL_ARENA_GB` が非負の場合はこの再計算と fill 判定を迂回する。`engine/metal/src/engine/window.cpp:1795-1807`、`engine/metal/src/engine/arena_budget.h:144-157`。

環境変数は関数内 static に cache されない。arena を作るたびに読み直すが、一度 `st_->ready()` になった後は通常その arena を再利用するため、プロセス中に環境を変更しても既存 arena には反映されない。初回作成失敗後の再試行では再度読む。読み取りはプロセス内で、子プロセスへの転送処理は見つからない。根拠: `engine/metal/src/engine/window.cpp:1560,1763-1768,1795-1819`。

## ログと測定値

計算した arena 予算が 2 GB 未満なら stderr に次の書式で出し、予算を最低 1 GB にします。割り当て前の状態と計画 footprint も stderr に出ます。

```text
strata metal stream: only %.1f GB left for the expert arena (the GPU working set %.1f GB, RAM %.1f GB, %.1f GB allocated): expect a low hit rate
strata metal stream: %.2f GB allocated before the arena (the process holds %.2f GB, %.2f GB resident); RAM %.1f GB (%.1f GB available, %.1f GB kept for macOS), GPU working set %.1f GB
strata metal stream: planned resident footprint %.1f GB = arena %.1f + %.1f held before it + %.1f reserved for the n-gram table; cap %.1f GB = the lesser of the GPU working set %.1f GB and the RAM %.1f GB less %.1f GB left to macOS and its file cache%s
strata metal stream: resident footprint after the fill: the process holds %.1f GB (%.1f GB resident), planned %.1f GB, cap %.1f GB%s
```

明示 `STRATA_METAL_ARENA_GB` が cap を超える場合、planned footprint の書式末尾 `%s` に ` - STRATA_METAL_ARENA_GB is above the cap: kept as set (your choice), but a Mac that runs short of memory can freeze (watchdog panics seen at 90+ GB resident of 128)` が入ります。`STRATA_METAL_KEEP_FREE_GB` 固有の警告ログはありません。`engine/metal/src/engine/window.cpp:1766-1815`。

arena のレイアウト・割当が失敗すると、たとえば arena が 4 buffer を超える場合は `metal stream: the arena needs more than 4 buffers (lower STRATA_METAL_ARENA_GB)`、匿名メモリの map に失敗した場合は `metal stream: cannot map the arena` をエラーとして返します。これらの文言は変数固有ではなく、どちらも `STRATA_METAL_KEEP_FREE_GB` が原因だとは断定できません。`engine/metal/src/engine/stream.cpp:450-464`。

## 根拠

- `engine/metal/src/engine/window.cpp:1722-1726` — streaming arena の説明と関数。
- `engine/metal/src/engine/window.cpp:1727-1768` — RAM 等の収集、変数の読み取り、予算計算。
- `engine/metal/src/engine/window.cpp:1769-1819` — 低予算警告、計画ログ、arena 作成・再試行。
- `engine/metal/src/engine/stream.cpp:34-49` — streaming 判定と `STRATA_METAL_STREAM` の優先。
- `engine/metal/src/engine/arena_budget.h:80-117,144-157` — 既定値、cap、予算、shrink/grow の算術。
- `engine/metal/src/engine/stream.cpp:450-464` — arena 作成の失敗経路。
