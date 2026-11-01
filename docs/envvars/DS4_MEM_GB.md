# `DS4_MEM_GB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Metal 版 DeepSeek V4.1 のホスト側診断で確保する一時領域のサイズを選びます。環境変数名に `GB` とありますが、Strata のコード上のサイズは未設定時 4096 bytes、設定時 64 MiB です。通常のモデル計算やメモリ上限を設定するものではありません。`DS4_DBG_MEM` または `DS4_DBG_BIND` による診断用 allocation でのみ参照されます（`metal/src/engine/ds4_finish.cpp:62-89`）。

## 値と判定

| `DS4_MEM_GB` の状態 | 診断 allocation のサイズ |
|---|---:|
| 未設定 | 4096 bytes |
| 空文字を含む任意の設定値 | 64 MiB（`64u << 20`） |

`std::getenv()` の null / 非 null だけを判定し、文字列を parse しません。したがって `0`、`1`、任意の文字列、空文字はすべて同じ設定済み扱いで、数値変換・無効値・境界値・clamp はありません。CLI 引数や別設定による上書きもありません。設定有無の判定は二つの診断ブロックに直接書かれています（`metal/src/engine/ds4_finish.cpp:65,88`）。

## 有効になる条件

- 読み取り箇所は `metal/src/engine/ds4_finish.cpp:65,88` の二つです。どちらも `ensure()` 内で、動的な名前を渡す環境変数 helper は経由しません。
- 1つ目の読み取りは `DS4_DBG_MEM` が設定されている場合だけ実行されます。このブロックは `ensure()` の `g_cx` 初期化済み判定より前にあるため、`DS4_DBG_MEM` が有効なら呼び出しごとに診断とサイズ判定が行われます（同 `:62-79`）。
- 2つ目は初期化後の `g_lib >= 0` と `DS4_DBG_BIND` の両方が成立した場合だけ実行されます（同 `:79-89`）。`g_cx` が既に作成されていれば `ensure()` はこのブロックより前で戻るので、これは初回の初期化経路での診断です。
- このファイルは macOS 専用の `metal/` CMake プロジェクトに含まれる `strata_ds4` ターゲットのソースです。Metal の DeepSeek V4.1 エンジン経路に限定され、通常の CUDA/HIP/SYCL ビルドにはこの読み取り箇所はありません（`metal/CMakeLists.txt:16-18,132-142`）。

## 実行時の詳細

`DS4_DBG_MEM` が設定されていれば、Strata は選んだサイズで `cudaMalloc` を呼び、成功時に `host_view()` を得て先頭へ `42.0f` を書き、4 bytes を `cudaMemcpy` で読み戻して stderr に `DBG mem: ...` を出します。`DS4_MEM_GB` 自体はこれらの操作を有効化せず、領域サイズだけを変えます。allocation が失敗するとこの診断ブロックは専用ログなしで先へ進み、host view が得られない場合は `DBG mem: gpu=%p has no host view` を出します（`metal/src/engine/ds4_finish.cpp:63-77`）。

`DS4_DBG_BIND` が設定され、初期 Metal library `ds4_init.metal` の compile が成功した場合は、同じサイズ選択で領域を確保して二通りの書き込み診断を実行し、それぞれの読み戻し値を `DBG bind A ...` / `DBG bind B ...` として stderr に出します。`cudaMalloc` に失敗した場合は診断を実行せず、専用ログもありません（同 `:82-89,91-117`）。DeepSeek の `finish()` は `STRATA_METAL` 時に Metal host 実装へ委譲し、その処理も `ensure()` を呼びます（`src/dsv41/ds4_kernels.cu:2196-2217`; `metal/src/engine/ds4_finish.cpp:136-143`）。

`DS4_DBG_MEM` 経路では `DS4_MEM_GB` を `ensure()` 呼び出しごとに読み直すため、その経路を実行中に環境値が変化すれば後続回のサイズ判定に反映されます。`DS4_DBG_BIND` 経路での読み取りは初期化時の一度です。環境変数だけを理由に Strata が終了したり、通常のモデル計算を切り替えたりする分岐はありません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:222`。Strata ソース全体の完全一致検索では上記の2箇所だけで、値を転送・保持する別 helper や他 backend の参照はありません。
- サイズ判定、診断ゲート、出力・allocation 失敗時の分岐: `metal/src/engine/ds4_finish.cpp:62-89`。
- Metal 専用ビルド条件と DeepSeek ターゲットへの組み込み: `metal/CMakeLists.txt:16-18,132-142`。
- `finish()` から Metal host 実装への経路: `src/dsv41/ds4_kernels.cu:2196-2217`。
