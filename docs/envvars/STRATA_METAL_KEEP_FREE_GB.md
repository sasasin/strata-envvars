# `STRATA_METAL_KEEP_FREE_GB`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

macOS Metal エンジンで SSD から expert を読むストリーミング経路を使うとき、expert arena の自動サイズ計算や段階的な確保で macOS に残す RAM の量を GB 単位で指定する。これはストリーミングを選択するスイッチではない。ストリーミング経路は別途 `STRATA_METAL_STREAM` またはモデルと GPU working set の判定で決まり、その後に arena の初期化時点でこの変数が読まれる（`metal/src/engine/window.cpp:425-431,1016,1127-1128`、`metal/src/engine/stream.cpp:33-48`）。

## 値と判定

| 環境変数の状態・値 | `atof` の結果と処理 |
|---|---|
| 未設定 | `keep_gb` は初期値 `-1` のまま。`max(7 GB, RAM の 15%)` を macOS 用に残す。 |
| 数値が 0 以上 | 指定値を GB として使用する。明示的な 0 は 0 GB を残す指定。 |
| 数値が負 | `arena_keep()` の `keep_gb >= 0` を満たさず、既定値 `max(7 GB, RAM の 15%)` に戻る。 |
| 空文字または数値に変換できない文字列 | `std::atof` は 0 を返すため、0 GB 指定として扱う。 |
| 数値に続く余分な文字 | 文字列全体の妥当性検査はなく、`atof` が数値として読めた先頭部分を使う。 |

空白、大文字小文字、整数範囲などを独自に検査するコードはありません。値の読み取り箇所は `Window::stream_arena()` のみで、`static` キャッシュではありません。arena の初期化が完了して `st_->ready()` になった後は同関数を再度呼ばないため、通常は初期化時の値がその arena に使われます。初期化に失敗して再試行する経路では、再度環境から読み取ります（`metal/src/engine/window.cpp:1016,1164`）。

## 有効になる条件

- Metal エンジンのストリーミング経路に入る必要がある。`STRATA_METAL_STREAM=1` なら明示的にストリーミングし、`=0` ならしない。それ以外（未設定を含む）は、モデル全体と付随メモリが resident footprint 上限に収まるかを `ExpertStream::wanted()` が判定する。この判定は `STRATA_METAL_KEEP_FREE_GB` を読み込まず、既定の keep 値で行う（`metal/src/engine/stream.cpp:33-48`）。
- 値は `stream_arena()` が arena 用 `ArenaMem` に読み込むので、モデルが resident 経路なら効果はない（`metal/src/engine/window.cpp:1127-1128,1150-1169`）。
- 自動 arena 予算では指定値が、現在利用可能な RAM から差し引く keep 分、RAM から得る footprint 上限、および各確保ステップ後に残す RAM に使われる。GPU working set と、すでにプロセスが保持するメモリも別の上限として予算に作用する（`metal/src/engine/arena_budget.h:80-89,99-117,144-158`）。
- `STRATA_METAL_ARENA_GB` に 0 以上の数値が設定されていると、自動予算計算を迂回してその arena サイズを使う。keep 値は footprint cap と計画ログには引き続き使われるが、明示 arena の shrink / grow 判定は arena サイズを維持する（`metal/src/engine/window.cpp:1164-1169,1182-1192`、`metal/src/engine/arena_budget.h:112-117,144-158`）。

## 実行時の詳細

`Window::stream_arena()` は物理 RAM、GPU の recommended working set、既存の Metal allocation、プロセス全体の footprint、macOS が圧縮や swap なしで供給できるページ量を取得し、`ArenaMem` を作ります。環境変数から得た keep 値を使って `arena_budget()` が GPU、利用可能 RAM、プロセス footprint の各上限を計算し、既定では少なくとも 1 GB の arena 予算を返します。予算が 2 GB 未満なら低い hit rate が予想される旨を stderr に出し、予算を最低 1 GB にします（`metal/src/engine/window.cpp:1127-1175`、`metal/src/engine/arena_budget.h:109-117`）。

arena を実際に確保する直前にも利用可能 RAM を再確認し、明示的 arena サイズでない場合は予定サイズを縮めます。段階的な確保では、各段階の後も `arena_keep()` と n-gram 表の予約分を残せるかを検査します。使用中メモリが減って予算を縮めた場合は `strata metal stream: less memory is free than when the arena was planned: ...` を stderr に出します（`metal/src/engine/window.cpp:1197-1207`、`metal/src/engine/arena_budget.h:144-158`）。

初期化時の stderr ログには、available RAM と `macOS` 用に計算した keep 量、および footprint cap が出ます。明示した arena が cap を超えても値はそのまま使われ、ログに `STRATA_METAL_ARENA_GB is above the cap` の説明が付く場合があります（`metal/src/engine/window.cpp:1179-1192`）。

## 根拠

- `metal/src/engine/window.cpp:1123-1127,1150-1169`: ストリーミング arena 初期化、環境変数の読み取り、予算計算。
- `metal/src/engine/window.cpp:1197-1219`: arena の再確認・縮小・確保とログ。
- `metal/src/engine/arena_budget.h:36-47,80-89,99-117,144-158`: keep の既定値、footprint cap、自動予算、確保時の縮小・段階判定。
- `metal/src/engine/stream.cpp:33-48`: ストリーミング経路を選ぶ別の判定と `STRATA_METAL_STREAM`。
- `docs/MAC.md:183-200`: `STRATA_METAL_KEEP_FREE_GB` をストリーミング時の arena / macOS 向け残余メモリ設定として列挙。具体的な値の意味は上記実装に従って記載。
