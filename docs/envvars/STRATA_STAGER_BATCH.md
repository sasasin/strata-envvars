# `STRATA_STAGER_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 系の prompt prefill に使う stager worker が、一度に claim する連続 expert copy job 数を調整する。file-backed source の unpinned expert を扱う場合は、worker が複数 blob を `ExpertSource::copy_blobs` にまとめて渡せる。値は job の grouping を変えるもので、ルーティングが選んだ expert や job の並びをこの分岐自体が変えるわけではない（`engine/src/prefill/prefill.cpp:1207-1211,1233-1247,1253-1261,2547-2555`）。

## 値と判定

`Prefill::init` が stager を初めて作るときに `std::getenv` で読み、設定されていれば `std::atoi` の結果を 1〜32 に clamp する。文字列全体の数値検証はせず、`atoi` が読める先頭の整数部分を使う。したがって空文字、数値に変換できない先頭、`0`、負数は 1 になり、`1anything` は 1、`8tail` は 8、` 4` は 4 になる。`32` 以上は 32、`true` は 1 になる（`atoi` が 0 を返すため）。大文字小文字は意味を持たず、値を真偽値として比較しない。数値範囲外の文字列に対する `atoi` の結果は C/C++ の変換仕様上保証できないため、文書化できる範囲外である（`engine/src/prefill/prefill.cpp:2550-2552`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| file-backed expert source がない（`files == false`） | 1 | `atoi` 結果を 1〜32 に clamp。例: `2`, `8tail`, `32`, `99`（32） | 個別の無効値はなく、空文字・`true`・`0`・`-4` はいずれも 1 に clamp |
| file-backed expert source がある（`files == true`） | 8 | 同じく `atoi` 結果を 1〜32 に clamp。例: `1`, `8`, `32` | 個別の無効値はなく、空文字・`true`・`0`・`-4` はいずれも 1 に clamp |

設定が存在すれば、file-backed かどうかにかかわらずその値が未設定時の既定値に優先する。実際の batch は clamp 後に ring 深さ `kRing` 以下へさらに制限されるため、最終値は `min(clamp(atoi(value), 1, 32), kRing)`。`kRing` は既定 16 で、`STRATA_STAGER_RING` の設定があれば `atoi` 値を 2〜256 に clamp する。file-backed の場合は `STRATA_STAGER_RING` が未設定なら `4 * threads` が ring 深さになり、`STRATA_STAGER_THREADS` が未設定の既定 32 thread と組み合わさる場合でも batch 上限は 32 のままである（`engine/src/prefill/prefill.cpp:1127-1132,1156-1158,2545-2555`）。

## 有効になる条件

- `Prefill::init` の Metal build 分岐は Metal window setup を呼んで先に return するため、この stager setting path には到達しない。対象コードは CUDA/HIP 系実装内の prompt prefill path である（`engine/src/prefill/prefill.cpp:2443-2455,2518-2555`）。
- stager が作成されるには `Prefill::init` が実行される必要がある。source の expert が unpinned で staging 対象になった場合に job が作られ、batch 設定が copy work に関係する。pinned または host cache 上の resident expert は job から外される経路がある（`engine/src/prefill/prefill.cpp:2523-2555,4692-4717,7020-7033`）。
- file-backed の自動判定は source が `transient(l,e)` を一つでも返すかで決まる。`STRATA_STAGER_THREADS` が設定済みなら `STRATA_STAGER_SSD` による profile 選択分岐を通らない。これらは batch の明示設定を無効にしないが、unset 時の既定値 8/1 と ring 深さに影響する（`engine/src/prefill/prefill.cpp:2526-2546`）。
- `STRATA_STAGER_RING` で ring が batch より浅くなれば、batch は ring 深さまで下がる。`STRATA_STAGER_BATCH` の値で ring 自体は変更されない（`engine/src/prefill/prefill.cpp:1156-1158,2550-2555`）。

## 実行時の詳細

読み取りは `m.stager` がまだないときだけ行われ、作られた stager に `batch` を保存する。既存 stager が再利用される `Prefill::init` では再読込されないため、読み取り後の環境変更はその stager に反映されない（`engine/src/prefill/prefill.cpp:2523-2555`）。

worker は `claim(seen, batch, k)` で最大 `batch` 件の隣接 job をまとめて claim し、各 job の ring buffer 利用可否を待つ。source 指定の job は `copy_blobs` にまとめて渡す。通常の `ExpertSource` 実装は各 blob を順に `copy_blob` する。file source でも direct-read が有効でない場合、または batch が 1 件以下なら同じ逐次 fallback を使う。`FileExpertSource` の direct-read が有効な場合は一括 read 経路があり、batch 件数はまとめられる要求数に関係する。source を介さない job は buffer へ blob を個別に `memcpy` するため、複数 claim しても複数 read 要求にはならない（`engine/src/prefill/prefill.cpp:1207-1248,1253-1261`; `engine/src/core/expert_source.cpp:1793-1797,3885-3915`）。

## ログと測定値

この変数を読んだり batch 値を選んだりする際に専用のログは出ない。source の一括コピーが失敗した場合は stderr に `prefill: the expert source could not copy experts %d.. of layer %d` を出して `std::abort()` する（`engine/src/prefill/prefill.cpp:1244-1246`）。Strata の設計資料 `docs/DETAILS.md` にこの変数の記載はなく、batch の性能測定値もこの変数について確認できないため、効果の大きさは記載しない。

## 根拠

- `engine/src/prefill/prefill.cpp:1126-1132,1156-1158` — stager の ring / batch 上限と ring 設定。
- `engine/src/prefill/prefill.cpp:1207-1248,1253-1261` — claim 単位、copy grouping、copy failure。
- `engine/src/prefill/prefill.cpp:2443-2455,2518-2555` — backend 分岐、source 判定、thread/ring/batch 初期化。
- `engine/src/prefill/prefill.cpp:4692-4717,7020-7033,8583-8602` — streamed / staged / layer-major での job 登録。
- `engine/src/core/expert_source.cpp:1793-1797,3885-3915` — 基本の `copy_blobs` と file source の一括処理。
