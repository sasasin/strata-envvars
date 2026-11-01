# `DS4_MM_LEAK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DS4 expert GEMM の Metal 実装で、dispatch 用 tile-list buffer `bt` を解放するかどうかを切り替えます。`DS4_MM_LEAK` が設定されていると、成功した `g_cx->run({d})` の後に `g_cx->free(bt)` を呼びません。行列計算の値や dispatch の形を変える分岐ではなく、一時 buffer の解放を抑止する診断・実験用フックです。

## 値と判定

| 環境値 | 判定 | 結果 |
|---|---|---|
| 未設定 | `std::getenv()` が `nullptr` | dispatch 後に `bt` を解放する |
| 空文字を含む任意の設定値 | `std::getenv()` が非 `nullptr` | dispatch 後の `bt` 解放を省略する |

値の文字列、数値、先頭文字は調べません。`1` だけでなく `0` や空文字も「設定済み」として同じ扱いです。CLI 引数や他の設定値との優先順位、範囲制限、無効値時の fallback はありません。該当分岐は各 `mm_set()` 呼び出しの dispatch 後に `getenv` を評価し、結果を static cache しません。

## 有効になる条件

- macOS の Metal ビルドで有効です。Metal プロジェクトは `APPLE` 以外では構成を失敗させ、DS4 engine のソース一覧に `ds4_finish.cpp` を含めます。CMake の OS guard 自体は CPU architecture を判定しません。
- DSV41 の IQ expert 経路で、`set_gate_up()` または `set_down()` が `STRATA_METAL` の下から `iq_set_gu()` / `iq_set_dn()` を呼ぶ必要があります。さらに `hbounds != nullptr` でなければ Metal helper は呼ばれません。
- `mm_set()` が dispatch まで進む必要があります。たとえば `n_exp <= 0`、`total_rows <= 0`、未対応の型・shape、Metal context/library 準備失敗、必要な host view の欠如などでは早期 return します。呼び出し元は helper が `false` を返すと通常の IQ 実装へ続行します。
- `DS4_MM_NOGU`（gate/up）または `DS4_MM_NODN`（down）が設定されている場合、該当分岐は `bt` を解放して `true` を返すため、`DS4_MM_LEAK` の判定箇所まで到達しません。

CUDA/HIP の通常ビルドではこの Metal helper 呼び出しは `STRATA_METAL` 条件の外となり、DS4_MM_LEAK を読むこのコード経路は使われません。対象変数自体にモデル状態・CLI・別環境変数による上書きはありません。

## 実行時の詳細

`mm_set()` はタイル一覧を構築し、その一覧を `g_cx->alloc()` で確保した `bt` にコピーします。gate/up と down の dispatch 引数に `bt` を渡し、`g_cx->run({d})` の直後に `DS4_MM_LEAK` の設定有無を確認します。未設定なら解放し、設定済みならその解放呼び出しを飛ばします。設定時はこの経路の各成功 dispatch で確保した `bt` が `g_cx->free()` されずに残ります。

この変数を読む分岐自体はログ出力、エラー、終了処理を行いません。pipeline 構築や入力 buffer の確認など、それ以前に失敗した場合は `bt` を解放して `false` を返す箇所があります。`DS4_MM_NOGU` / `DS4_MM_NODN` の早期 return も `bt` を解放します。下流の allocator や Metal runtime が保持 buffer をどう管理するかは、この Strata 分岐だけからは断定できません。

## 根拠

- `metal/CMakeLists.txt:16-18,132-142` — Metal build の Apple 限定と、DS4 ソースへの `ds4_finish.cpp` の組み込み。
- `src/dsv41/ds4_iq.cu:1585-1601,1604-1620` — Metal 条件と `hbounds` を満たす場合に gate/up・down helper を呼び、`false` 時は通常経路へ進むこと。
- `metal/src/engine/ds4_finish.cpp:2466-2484` — Metal context/library 準備、shape/type 検査など helper の早期 return 条件。
- `metal/src/engine/ds4_finish.cpp:2508-2510` — tile-list buffer `bt` の確保と tile-list のコピー。
- `metal/src/engine/ds4_finish.cpp:2518-2527,2544-2550,2576-2582` — pipeline/host view/状態の失敗時に `bt` を解放して `false` を返す経路。
- `metal/src/engine/ds4_finish.cpp:2614-2618` — `DS4_MM_NOGU` / `DS4_MM_NODN` の先行分岐と、dispatch 後の `DS4_MM_LEAK` 判定。
- `metal/include/metal_compat/ds4_metal_host.h:56-57` — DSV41 IQ 経路から呼ばれる helper の宣言。
