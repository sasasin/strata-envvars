# `STRATA_INK_EXACT_GRAPH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2 CUDA backend の hybrid engine で、exact cold-expert lane 用の GPU staging buffer と対応する device-side key/state を準備するかを制御する。準備が成功し、実行時に exact lane が選ばれると、M=1 decode の cold experts を graph 内で GPU にコピーして計算する。先頭が `0` の値では準備を飛ばし、exact lane を使う場合も eager 経路に残す。router の選択や expert の配置自体をこの変数が変更する処理はない。読み取りは `InkHybridEngine::exact_prepare()` にある。CUDA 専用 plugin の実装であり、HIP backend にこの名前の読み取りは見つからなかった（`engine/src/inkling2/cuda/CMakeLists.txt:1-7`、`engine/src/inkling2/cuda/ink_hybrid.cuh:1380-1398`）。

## 値と判定

`std::getenv` の null 判定後、文字列の先頭 1 文字だけを `'0'` と比較する。数値変換、文字列全体の比較、空白除去、大文字小文字変換は行わない。準備を抑止する分岐は `exact_prepare()` の前提条件を通過した後に評価される。

| 条件 | unset | 設定時に準備を試みる値 | 設定時に準備を抑止する値 |
|---|---|---|---|
| Inkling CUDA hybrid engine の staging 準備 | 準備を試みる | `1`、`true`、`false`、空文字、` 0`、`x` など先頭が `0` でない値 | `0`、`0anything` など先頭文字が `0` の値 |

したがって空文字は「設定あり」ですが、`e[0]` は文字列終端の `\0` であり `'0'` ではないため、準備を抑止しない。`false` も先頭が `'0'` でないため準備を試みる。値の妥当性検査はない。根拠: `engine/src/inkling2/cuda/ink_hybrid.cuh:1381-1384`。

## 有効になる条件

- `strata-inkling` の NVIDIA CUDA backend が使われること。実装は CUDA runtime API を使う CUDA plugin 内にあり、HIP backend からこの helper を呼ぶ経路はない（`engine/src/inkling2/cuda/CMakeLists.txt:1-7,56-66`）。
- `exact_prepare()` 呼び出し時に `lane_pref != 2`、engine が `active`、`ssd_only` でない、pinned host arena とそのポインターがあり、`host_meta` が空でなく、まだ `stage_ready` でないこと。どれかを満たさない場合、環境変数を読む前に戻る（`engine/src/inkling2/cuda/ink_hybrid.cuh:1381-1383`）。
- `host_meta` に resident host expert body が少なくとも 1 つあり、その最大サイズ `mx` が 0 より大きいこと。SSD の cold expert はこの `mx` の計算に含まれない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1385-1389`）。
- staging の device allocation が成功すること。`cudaMalloc` が失敗するとエラー状態を消費して戻り、`stage_ready` は立たない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1390-1397`）。
- 実際に graph 内 exact lane を使うには、さらに `exact_mode` が true であること。`STRATA_INK_EXACT` が先頭 `0` なら `lane_pref == 2` となり準備自体を行わない。未設定時は launch probe の結果で lane が選択され、exact が選ばれた場合に `exact_graph` が有効になる（`engine/src/inkling2/cuda/ink_hybrid.cuh:1360-1373,1789-1793`; `engine/src/inkling2/cuda/ink_runner.cuh:3711-3718,3742-3748`）。
- `exact_graph` staging を使う分岐は M=1 decode に限られる。その他の batch はこの変数による graph staging 分岐に入らない（`engine/src/inkling2/cuda/ink_hybrid.cuh:2503-2524`）。

## 実行時の詳細

runner は host expert のロード後、`start_workers()` と `alloc_staging()` の後に `exact_prepare()` を呼ぶ（`engine/src/inkling2/cuda/ink_runner.cuh:622-628,1588-1595`）。`STRATA_INK_EXACT_GRAPH` はこの準備関数の呼び出し時に読み、値を static cache せず、変数の値そのものもメンバーへ保存しない。CLI 引数からこの環境変数を設定・上書きする実装は見つからなかった。通常の runner 初期化では同じ engine に対して呼び出しは一度であり、初期化後の環境変更を再評価するコードはない。

準備を許可すると、host expert ごとの body byte 数を device に渡す表にまとめ、最大 body サイズを 256-byte 境界に切り上げた slot を `kInkTopK` 個確保する。その後 device key table と `InkStageState` を初期化し `stage_ready` を立てる。準備を抑止した場合や条件・allocation を満たさない場合は `stage_ready` が false のままになる（`engine/src/inkling2/cuda/ink_hybrid.cuh:1385-1397`）。

`set_lane()` は `exact_graph = exact && stage_ready` とする。したがって exact lane が選ばれても staging が準備されていないと `needs_eager()` が true になり、runner は M=1 CUDA graph の捕捉を避ける（`engine/src/inkling2/cuda/ink_hybrid.cuh:1368-1373`; `engine/src/inkling2/cuda/ink_runner.cuh:3663-3684`）。staging が準備済みで exact lane の M=1 decode に入ると、top-k の後に stage plan、GPU への cold expert copy、expert dispatch、expert table restore を順に stream へ投入する（`engine/src/inkling2/cuda/ink_hybrid.cuh:2503-2511`）。

## ログと測定値

この変数専用の有効・無効ログ、警告、終了メッセージは実装にない。通常経路では staging の成否を示す専用ログもない。allocation 失敗時は `cudaGetLastError()` を呼んでから戻るため、この箇所が出す文字列ログはない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1381-1397`）。性能値について、この変数の効果を条件付きで示す Strata 資料は確認できなかった。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:1360-1398` — lane / staging 状態、変数の値判定、準備と allocation fallback。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1789-1793` — `STRATA_INK_EXACT` による lane preference の設定とログ。
- `engine/src/inkling2/cuda/ink_runner.cuh:622-628,1588-1595` — runner 初期化中の読み取り呼び出し時期。
- `engine/src/inkling2/cuda/ink_runner.cuh:3663-3684,3711-3718,3742-3748` — eager 経路の条件と自動 lane 選択。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:2503-2524` — M=1 exact graph staging と他の dispatch 分岐。
- `engine/src/inkling2/cuda/CMakeLists.txt:1-7,56-66` — CUDA backend plugin の build 範囲。
