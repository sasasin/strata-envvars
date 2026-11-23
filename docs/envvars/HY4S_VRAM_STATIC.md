# `HY4S_VRAM_STATIC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Intel Arc 向け HY4 SYCL runner の VRAM expert cache について、初期配置後の adaptive promotion を止める。cache の初期化時に `adaptive_` を設定し、無効の場合は token commit による cache 更新を行わず、Runner 側の adaptive 更新経路も呼ばれない。VRAM cache 自体の有効・無効や容量を決める変数ではない（`engine/src/hy4flash/sycl/sy_vram_cache.h:690-698, 723-750, 795-797, 956-960`; `engine/src/hy4flash/sycl/sy_graph.h:372-389`）。

この環境変数を読むのは `engine/src/hy4flash/sycl/sy_vram_cache.h` の `SyVramExpertCache::init` だけ。SYCL runner 専用の実装で、標準の CUDA/HIP 経路にはこの読み取りはない。SYCL は別 backend として構成される（`engine/CMakeLists.txt:23-32`; `engine/src/hy4flash/sycl/build_hy4_sycl.sh:62-68`）。

## 値と判定

`std::getenv` で存在を確認し、値の先頭 1 byte が文字 `'1'` かを判定する。先頭が `'1'` なら `adaptive_ = false`、それ以外は `true`。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしない（`engine/src/hy4flash/sycl/sy_vram_cache.h:795`）。

| 条件 | 未設定 | adaptive promotion を止める値 | adaptive promotion を止めない値 |
|---|---|---|---|
| SYCL cache の初期化が VRAM cache 有効化まで進む場合 | adaptive 有効 | `1`, `10`, `1anything`, `1 ` | 空文字、`0`, `01`, `true`, `false`, ` 1`, `anything` |

`getenv` が非 null でも空文字なら先頭文字は `'1'` ではないため adaptive 有効。`1anything` のように先頭が `'1'` なら残りの内容にかかわらず無効となる。cache の VRAM 予算が不足して初期化が早期 return する場合や、割当て slot がない場合には、この環境変数を読む行に到達せず、cache 自体も inactive のままになる（`engine/src/hy4flash/sycl/sy_vram_cache.h:723-750, 795`）。

## 有効になる条件

- `strata-hy4-sycl` の SYCL 実行経路で `SyVramExpertCache::init` が cache 有効化まで進む必要がある。通常の CUDA/HIP/Metal 実行にはこの読み取り経路がない（`engine/CMakeLists.txt:23-32`; `engine/src/hy4flash/sycl/sy_graph.h:141`）。
- cache の初期配置は環境変数とは独立して行われる。モデルに有効な expert directory があり、VRAM 予算が最低 slot 条件を満たして slot が割り当てられた場合に cache が active になる（`engine/src/hy4flash/sycl/sy_vram_cache.h:694-750`）。
- `--vram-experts-gb` が指定されると、その CLI 値が cache 予算に使われる。未指定なら `HY4S_VRAM_EXPERTS_GB` があればその値を予算として評価し、なければ空き VRAM から予算を見積もる。これらは cache の容量・active 状態に関わり、`HY4S_VRAM_STATIC` の `'1'` 判定を上書きしない（`engine/src/hy4flash/sycl/sy_graph.h:127-141`）。
- `--spec-check`、`--wincheck N`（`N > 0`）、`--detcheck N`（`N > 0`）のいずれかを使う非 serve 実行では、cache 初期化より前にプログラムが `HY4S_VRAM_STATIC=1` を上書き設定する。このため、起動環境で `HY4S_VRAM_STATIC` が `0` などでも診断実行では adaptive 更新が止まる（`engine/src/hy4flash/sycl/sy_main.cpp:170-184, 298-304`; helper の overwrite 動作は `engine/src/hy4flash/sycl/sy_common.h:33-40`）。
- `--serve` は非 serve 用 cache 設定箇所より前に serve handler へ分岐するため、この CLI 上書きは行わない。serve ではプロセス環境に元からある値が cache 初期化時に使われる（`engine/src/hy4flash/sycl/sy_main.cpp:215-249, 298-304`; `engine/src/hy4flash/sycl/sy_serve.h:280-287`）。

## 実行時の詳細

`SyVramExpertCache::init` は開始時に以前の cache を解放し、モデルの expert directory を調べ、VRAM 予算に応じて slab と slot を割り当てて初期 expert を読み込んだ後に環境変数を読み、`adaptive_` を設定する。したがって読み取りは cache 初期化ごとに 1 回であり、関数 static cache ではない。初期化後にプロセス環境を書き換えても、既に設定された当該 cache の `adaptive_` には反映されない（`engine/src/hy4flash/sycl/sy_vram_cache.h:690-750, 769-797`）。

adaptive が有効な場合、commit 済み token の expert 使用状況で score を更新し、32-token bucket 境界を越えたときに slot を promotion する処理が行われる。無効なら `commit_tokens` は `adaptive_` の検査で直ちに戻るため、この score 更新・promotion は起きない（`engine/src/hy4flash/sycl/sy_vram_cache.h:956-1010`）。Runner の通常 commit、path commit、step 更新も `vcache->adaptive()` が false なら処理を呼び出さない（`engine/src/hy4flash/sycl/sy_graph.h:372-389`）。`step_adapt` 自体は counter を増やしてから `commit_tokens` を呼ぶが、promotion は同じ `adaptive_` ガードにより行われない（`engine/src/hy4flash/sycl/sy_vram_cache.h:1013-1017`）。

設定の読み取り時に他プロセスへの転送やリクエストごとの再評価をするコードはない。serve は同じプロセス内で cache を初期化するため、起動時の環境値が反映される。非 serve の診断 CLI は前述のとおり自プロセスの環境値を書き換えてから初期化する（`engine/src/hy4flash/sycl/sy_main.cpp:298-304`; `engine/src/hy4flash/sycl/sy_serve.h:280-287`）。

## ログと測定値

cache が slot を確保して初期化を終えると stderr に `[vram-cache] ... adaptive=%d ...` を出し、判定結果を `adaptive=0` または `adaptive=1` として観測できる。設定値が `'1'` 以外でも警告や parse error はなく、初期化ログ以外にこの変数専用のメッセージはない（`engine/src/hy4flash/sycl/sy_vram_cache.h:795-798`）。この調査では build・GPU 実行・測定は行っておらず、測定値は記載しない。

## 根拠

- `engine/src/hy4flash/sycl/sy_vram_cache.h:690-750, 795-798, 956-1017` — 初期化、値判定、起動ログ、adaptive 更新ガード。
- `engine/src/hy4flash/sycl/sy_graph.h:123-150, 372-389` — cache 予算と Runner の更新呼び出し。
- `engine/src/hy4flash/sycl/sy_main.cpp:170-184, 215-249, 298-304` — CLI 判定、serve 分岐、診断時の環境値上書き。
- `engine/src/hy4flash/sycl/sy_serve.h:280-287` — serve の cache 初期化。
- `engine/src/hy4flash/sycl/sy_common.h:33-40` — `hy4s_setenv` の上書き規則。
- `engine/CMakeLists.txt:23-32`, `engine/src/hy4flash/sycl/build_hy4_sycl.sh:62-68` — SYCL backend の分離と runner のビルド範囲。
