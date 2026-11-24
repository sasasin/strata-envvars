# `STRATA_INK_TIER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA Ink engine の expert 配置で、GPU resident expert の容量を固定配置ではなく、実行中に使用頻度に応じて入れ替える adaptive tier にするかを制御する。未設定時は有効で、`0` で始まる値を指定すると無効になる。無効時は元の静的配置に戻り、余剰 VRAM が条件を満たせば従来の promotion ring が使われる。変数を読むのは `InkHybridEngine::tier_enabled_env()` で、ロード時の2つの配置経路から呼ばれる（`engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2188`、`engine/src/inkling2/cuda/ink_runner.cuh:470-494`、`engine/src/inkling2/cuda/ink_runner.cuh:1342-1369`）。

有効な場合、expert 本体をホスト RAM に保持し、GPU 上のサイズ別 slot pool の所有 expert を routing 使用数に応じて交換する。router の選択や生成結果そのものをこの変数が直接変更する処理はない。tier を開始できない場合は、通常の静的配置と promotion の経路へ戻る（`engine/src/inkling2/cuda/ink_hybrid.cuh:2147-2153`、`engine/src/inkling2/cuda/ink_hybrid.cuh:2361-2370`）。

## 値と判定

`std::getenv` で値を取得し、設定されていて先頭文字が ASCII `0` の場合だけ `false`。文字列全体の parse や真偽値比較はしない（`engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2188`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA Ink の配置計画で判定 helper が呼ばれる場合 | 有効 | 空文字、`1`、`true`、`false`、` 0`、`00` 以外の `0` 以外で始まる任意の文字列 | `0`、`0anything`、`00` |

空文字は `getenv` が非 null を返しますが `e[0] == '0'` は偽なので有効です。大文字小文字・数値形式・末尾文字・空白の検査はありません。`false` も `f` で始まるため有効です。CLI 引数や別設定値でこの判定を上書きするコードは見つかりませんでした。VRAM 上限などの設定は配置可能な容量を変え、tier に入れる条件には影響しますが、環境変数の値判定自体は変えません（同 `ink_runner.cuh:440-479`、`ink_runner.cuh:1296-1352`）。

## 有効になる条件

- 対象は CUDA の Ink engine の expert loader。確認した実装箇所は `engine/src/inkling2/cuda/ink_runner.cuh` と `engine/src/inkling2/cuda/ink_hybrid.cuh` で、他 backend にこの環境変数を読む箇所はありません。
- 対象 loader の通常配置計画に到達し、環境変数が無効値でないこと。
- ホスト側に expert が少なくとも1つあり、GPU に割り当てる expert 容量も正であること。すべて VRAM に収まる場合は判定箇所に来ず、ホスト expert がない場合も tier は計画されない（`engine/src/inkling2/cuda/ink_runner.cuh:406-424`、`engine/src/inkling2/cuda/ink_runner.cuh:470-479`、`engine/src/inkling2/cuda/ink_runner.cuh:1300-1317`）。
- SSD expert モードではないこと。別の容量計画経路ではさらに layer split (`ls_active`) と peer GPU (`ep2_active`) のいずれも使わないこと（`engine/src/inkling2/cuda/ink_runner.cuh:452-479`、`engine/src/inkling2/cuda/ink_runner.cuh:1342-1352`）。
- tier 用の全 expert のホストコピー分を追加できる RAM があること。利用可能 RAM が 0 と報告された場合は条件を通し、それ以外では `avail_ram > (host_used + add) + 5 GiB`（別経路では `uh + add`）が必要。満たさない場合は tier を無効にして静的配置を続ける（`engine/src/inkling2/cuda/ink_runner.cuh:475-480`、`engine/src/inkling2/cuda/ink_runner.cuh:1348-1352`）。
- tier slot pool の CUDA allocation と bookkeeping の前提が満たされること。pool が空、サイズ 0、worker 非稼働、または使用数カウンタ未確保なら `tier_alloc()` は失敗する。pool の `cudaMalloc` 失敗も `false` を返し、呼び出し側は tier を無効にして静的配置へ戻る（`engine/src/inkling2/cuda/ink_hybrid.cuh:2268-2272`、`engine/src/inkling2/cuda/ink_runner.cuh:504-522`、`engine/src/inkling2/cuda/ink_runner.cuh:1383-1401`）。

## 実行時の詳細

環境変数は expert 配置を決めるロード時に `tier_enabled_env()` が呼ばれた時点で読み取られる。関数内 static cache やリクエストごとの再読込はなく、ロード後にプロセス環境を変更しても既に選択した tier mode は再判定されない（`engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2188`、呼び出し箇所 `engine/src/inkling2/cuda/ink_runner.cuh:473`、`engine/src/inkling2/cuda/ink_runner.cuh:1346`）。

有効時は expert body サイズ別に pool を分け、配置予算を load order と層の重みで slot に配分する。開始時点では load order の先頭側から GPU slots を割り当て、残りの expert は host copy を使う。decode/バッチ処理で得た使用数の snapshot をもとに、既定では4 token分ごとに round を進め、最大16 swap/roundを policy に渡す。round の snapshot は非同期コピーで取得し、イベントを後続 step で待ってから swap を行う（`engine/src/inkling2/cuda/ink_hybrid.cuh:2190-2265`、`engine/src/inkling2/cuda/ink_hybrid.cuh:2288-2295`、`engine/src/inkling2/cuda/ink_hybrid.cuh:2313-2358`、`engine/src/inkling2/cuda/ink_hybrid.cuh:2361-2385`）。

`STRATA_INK_TIER=0` または先頭が `0` の値なら `tier_on` はセットされず、`step_after()` は単一 row のとき従来の `step_promote()` を呼びます。余剰 VRAM が 320 MiB を超え、slot サイズが正なら最大256 MiBの promotion ring を確保する経路があります（`engine/src/inkling2/cuda/ink_hybrid.cuh:2031-2047`、`engine/src/inkling2/cuda/ink_hybrid.cuh:2364-2370`）。

## ログと測定値

tier が確保されると stderr に `[InkTier] adaptive expert tier on: ...` と pool / slots / round 間隔の行を出す。RAM 条件または slot pool 確保を満たせない場合は、それぞれ `[InkTier] off: the host copy ...` または `[InkTier] off: the card has no room for the slot pool ...` を出す。tier が有効な場合、終了時には round 数と swap 数を stderr に出す（`engine/src/inkling2/cuda/ink_hybrid.cuh:2291-2295`、`engine/src/ink_runner.cuh:478-480`、`engine/src/ink_runner.cuh:520-522`、`engine/src/ink_runner.cuh:1398-1401`、`engine/src/ink_hybrid.cuh:2389-2395`）。

追加の round ごとのログは別変数 `STRATA_INK_TIER_LOG` が設定されている場合に限り、round 1, 65, 129, ... で出る。この判定は値の内容でなく設定有無（空文字も含む）を見る（`engine/src/ink_hybrid.cuh:2290`、`engine/src/ink_hybrid.cuh:2357-2358`）。

ソースコメントには routing trace のシミュレーション条件付き hit rate 比較（SQ-20、9 requests、2.4K tokens、4 GB expert VRAM: static fill 0.39、256 MiB ring 0.50、tier 0.81）があるが、実行時測定ではないため、ここでは性能保証として扱わない（`engine/src/inkling2/cuda/ink_hybrid.cuh:2154-2155`）。

## 根拠

- 環境変数の直接読み取りと判定: `engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2188`
- 通常配置計画経路と RAM 条件: `engine/src/inkling2/cuda/ink_runner.cuh:470-494`
- 別容量計画経路と layer split / peer GPU 条件: `engine/src/inkling2/cuda/ink_runner.cuh:1342-1372`
- pool 確保と開始時ログ: `engine/src/inkling2/cuda/ink_hybrid.cuh:2268-2296`
- 有効時の round と swap: `engine/src/inkling2/cuda/ink_hybrid.cuh:2313-2385`
- 無効時の従来 promotion 経路: `engine/src/inkling2/cuda/ink_hybrid.cuh:2031-2047`、`engine/src/inkling2/cuda/ink_hybrid.cuh:2364-2370`
