# `HY4_EMBED_VRAM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の GPU ローダーで、通常は小さめの GPU で pinned mapped host RAM に分ける `model.embed_tokens.weight` を、trunk の通常配置経路へ戻すための環境変数。`plan_memory` は未設定かつ報告 VRAM が 48 GiB 未満なら trunk の見積りから最大 0.38 GB を差し引き、計画ログに host embed を表示する。`load_gpu_model` も同じ未設定・48 GiB 未満条件に加えて UMA mapped ではなく、manifest に embedding tensor がある場合にのみ分離ロードを試みる。設定するとこの特別な分離を抑止するが、trunk 全体が必ず VRAM に載る指定ではない。通常の trunk 配置で VRAM が足りなければ既存の mapped host RAM fallback が使われる。実装は `engine/src/hy4flash/run/hy4_gpu_model.hip.h` の `plan_memory` と `load_gpu_model`。

## 値と判定

どちらの読み取りも `getenv("HY4_EMBED_VRAM")` の null 判定だけで、文字列変換・比較はしない。従って未設定だけが「指定なし」で、空文字を含むどんな設定値でも特別な host embed 経路を無効にする。`0`、`1`、`true`、`false`、`0anything` の意味に差はない。CLI 引数による上書きはなく、同じ設定有無判定を計画時とロード時にそれぞれ行う（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:450,1295`）。

| 条件 | unset | 設定あり（例） | 適用上の注意 |
|---|---|---|---|
| `plan_memory` の見積り | `total < 48 GiB` なら host embed 扱い。`trunk > 0.5 GB` のとき見積りから 0.38 GB を差し引く | 空文字、`0`、`1` など全て host embed 扱いにしない | モデル manifest に embedding tensor があるか、UMA mapped かはこの見積り条件に含まれない（同 `:449-451`） |
| `load_gpu_model` の実ロード | `HY4_UMA_MAPPED` による UMA mapped が無効、`tot0 < 48 GiB`、embedding tensor が存在すると分離を試行 | どの文字列でも分離を試行しない | 失敗時や条件外では通常の trunk 配置へ進む（同 `:1280-1295,1336-1394`） |

48 GiB はコード上 `(48ull << 30)` バイトとの厳密な未満比較であり、同値以上は対象外。環境変数値自体に数値境界はない。

## 有効になる条件

- `strata-hy4` を含む Hy4-Flash GPU build が必要。CMake は `STRATA_BUILD_HY4` に CUDA または HIP を要求し、`hy4_gpu_model.hip.h` を GPU 実装から取り込む（`engine/CMakeLists.txt:850-890`）。
- `plan_memory` では `total < 48 GiB` のときだけ未設定が host embed 見積りに影響する。これはモデル状態や UMA を確認しないため、実ロードで分離されない場合にも見積りログへ反映される（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:449-451,564-565`）。
- 実ロードではさらに `HY4_UMA_MAPPED` が有効な UMA 機でないこと、`tot0 < 48 GiB`、manifest 内に `model.embed_tokens.weight` があることが必要。`HY4_UMA_MAPPED` は UMA 機で設定され、`atoi` が 0 以外なら mapped 扱い（同 `:1280,1295`）。
- `--serve` と通常の CLI のどちらも `plan_memory` の後に `load_gpu_model` を呼ぶ（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-295`）。別の CLI 引数による `HY4_EMBED_VRAM` の上書きは見つからない。

## 実行時の詳細

環境はキャッシュされない。各 `plan_memory` 呼び出しと各 `load_gpu_model` 呼び出しで `getenv` を評価する。前者は VRAM/モデル trunk の見積りを調整し、後者はロード経路を決める（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-451,1267-1296`）。

未設定時の分離ロードでは、embedding tensor 用に `hipHostMalloc(..., hipHostMallocMapped)` を試し、ファイルから tensor を読み込む。続いて embedding を除いた trunk のサイズを計算し、free VRAM がそのサイズ・VRAM floor・256 MiB の合計を超える場合に trunk を GPU buffer へ読み込む。成功時は tensor offset を調整して `loaded_host_embed` とし、他の trunk 重みは VRAM、embedding 重みは pinned mapped host RAM に置く（同 `:1297-1321`）。

host allocation、ファイル読み込み、または trunk の VRAM 条件に失敗すると、確保した host buffer を解放して `loaded_host_embed` を false のままにし、通常の trunk 読み込みへ進む。通常経路は UMA では UMA allocator、discrete GPU では VRAM allocation を試す。discrete GPU で trunk が収まらない場合は trunk 全体を pinned mapped host RAM に置き、失敗なら `trunk alloc failed ...` を stderr に出して `false` を返す（同 `:1322-1335,1336-1394`）。この低 VRAM fallback は `HY4_EMBED_VRAM` が設定済みでも起こり得る。

環境をプロセス実行中に外部から変更すれば、後続の `getenv` 呼び出しがその時点の値を読む構造だが、プロセス内からこの変数を変更するコードは確認できなかった。通常の単一ロードでは計画とロードの間で同じ環境値が使われる。

## ログと測定値

`plan_memory` は stderr の `[plan] ... trunk ... (embed in RAM) ...` 表示で計画上の host embed を示す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-565`）。これは manifest の tensor 有無や実際の割当成功を示すログではない。分離ロードまで成功すると stderr に `[load] embed_tokens (%.2f GB) in pinned mapped host RAM -> trunk VRAM %.2f GB` が出る（同 `:1319-1321`）。分離を抑止したこと自体を示すログはない。関連資料にこの変数の測定値は見つからなかった。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-451` — 計画時の設定有無判定と trunk 見積り調整。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-565` — 計画ログ。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1321` — 実ロード条件、分離処理と成功ログ。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1322-1394` — 分離失敗後の通常配置と trunk allocation failure。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-295` — CLI と server の計画・ロード呼び出し。
- `engine/CMakeLists.txt:850-890` — HY4 build 条件と CUDA/HIP 実装の選択。
