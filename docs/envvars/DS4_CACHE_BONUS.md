# `DS4_CACHE_BONUS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`strata-dsv41` の expert cache が VRAM に入れる CPU lane expert を選ぶ比較式の加算項です。対象 expert の heat が、現在 VRAM にある最も低い heat の expert に `DS4_CACHE_MARGIN` を掛けた値へこの bonus を加えた値を超えると、VRAM の入れ替え候補になります。単独でキャッシュを有効化するスイッチではありません。

## 値と判定

`env_f()` は環境変数が未設定なら既定値を返し、設定されていれば `std::atof()` の結果を `float` に変換します。`DS4_CACHE_BONUS` の既定値は `1.0f` です。文字列全体の検証、範囲制限、clamp はありません。

| 環境変数の状態 | `c_bonus` |
|---|---:|
| 未設定 | `1.0` |
| 空文字 | `0.0`（`atof("")`）|
| 数値として読める文字列 | 先頭から `atof()` が変換した値。例: `2.5tail` は `2.5` |
| 数値に変換できない文字列 | `0.0` |
| 負値 | 負値のまま使用 |

数値以外の末尾は拒否されず、変換できた先頭部分が使われます。読み取りはモデルオブジェクトの `c_bonus` 初期化時に行われ、その値をインスタンス内に保持します。実行中に環境を変更しても、そのインスタンスの値は再読込されません。別の既定値や CLI 値で `c_bonus` を上書きする経路は見つかりません。

## 有効になる条件

- 対象は DSV41 用 `strata-dsv41` のモデル実装です。CMake では DSV41 GPU target は CUDA または HIP backend 時に作られ、HIP gfx906 target は除外されています。GPU backend なしの分岐は host-side `ds4_gg_bench` のみを作ります。
- CLI の `--no-expert-cache` が指定されると `o.expert_cache` が false になり、キャッシュ初期化・更新が行われません。既定では `expert_cache = true` です。
- 実際の VRAM swap 候補判定には、CPU lane の hit があること、VRAM 側に入っていない最熱 expert があること、layer に spare VRAM slot があり swap が pending でないこと、同時 swap 数が `DS4_CACHE_INFLIGHT` 由来の上限未満であること、VRAM resident expert が比較対象として存在することが必要です。
- RAM tier の候補判定にも別の処理がありますが、そこで使われる閾値は固定の `1.25 * heat + 1.0` です。`DS4_CACHE_BONUS` はその RAM tier 判定には使われません。

## 実行時の詳細

swap 判定は `cache_tick_swaps()` が行います。CPU lane expert の heat が VRAM にない候補の中で最大のものを選び、VRAM resident expert の最小 heat を求め、`best_heat > cold_heat * c_margin + c_bonus` を満たす場合に swap を queue します。選ばれた値は heat に加算され、モデルの window / prompt 更新時に cache tick から評価されます。判定式は厳密な `>` なので閾値と等しい場合は入れ替えません。bonus を大きくすると VRAM 入れ替えに必要な heat 差が増え、小さくすると減ります。

この変数専用のログ、警告、無効値エラーはありません。swap worker で VRAM への移動に失敗すると stderr に `ds4 cache: layer %d expert %d: the move into VRAM failed` を出しますが、これは変数の parse エラーではありません。`DS4_CHECK_SWAPS` が有効な経路では、swap 内容の検証結果を `ds4 cache: ... matches the model file` または `MISMATCH` として stderr に出します。設定値そのものや比較閾値はログに出ません。

## 根拠

- `src/dsv41/ds4_model.cu:1163-1168` — swap の heat 比較式の説明、`env_f()`、`DS4_CACHE_BONUS` の既定値と `atof()` 変換。
- `src/dsv41/ds4_model.cu:3158-3172` — expert cache が有効な場合の swap buffer / worker 初期化と、`DS4_CACHE_THREADS` による worker 数。
- `src/dsv41/ds4_model.cu:7250-7251,7335-7357` — cache tick の有効条件、CPU hit の候補選択、inflight / spare slot 条件、bonus を含む swap 判定。
- `src/dsv41/ds4_model.cu:7365-7369` — RAM tier 判定に固定閾値が使われ、`c_bonus` が参照されないこと。
- `src/dsv41/ds4_model.cu:7146-7149` — swap の検証ログおよび VRAM move failure の stderr。
- `src/dsv41/ds4_model.hpp:37`, `src/dsv41/ds4_main.cpp:1331` — expert cache の既定有効状態と `--no-expert-cache`。
- `CMakeLists.txt:910-920,2780-2792` — DSV41 GPU target と backend なしの host-side benchmark の条件。
