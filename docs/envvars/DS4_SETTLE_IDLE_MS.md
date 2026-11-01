# `DS4_SETTLE_IDLE_MS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

独立した DSV41 engine の serve モードで、要求のない間に expert cache の入れ替えを続ける時間予算をミリ秒で指定します。各 idle 区間で `Model::settle_idle()` が cache の swap 処理を実行し、次の要求が届いたら処理をキャンセルします（`src/dsv41/ds4_main.cpp:388,716-738,1410`; `src/dsv41/ds4_model.cu:10774`）。

## 値と判定

| 設定 | `env_f` の結果 | idle 処理 |
|---|---:|---|
| 未設定 | 6000 ms | 最大 6000 ms を目安に実行 |
| 数値文字列 | `std::atof` で変換後、`float` にしてから `double` へ格納 | 正の値ならその時間予算で実行 |
| 空文字・数値に変換できない文字列 | 0 | ループに入らず終了 |
| 0 または負数 | その値 | ループに入らず終了 |

変換は文字列全体の検証ではありません。`std::atof` は数値として読める先頭部分を変換し、後続文字を検査しません。たとえば `1200junk` は 1200 相当、`junk1200` は 0 相当です。空白などの扱いも `atof` の変換に従います。値は `float` 精度を経由し、clamp、エラー報告、無効文字列用 fallback はありません。正の有限値でも、キャンセル要求または swap がなくなれば予算より早く終わります。NaN は時間比較を満たさずループせず、正の無限大はキャンセルまたは swap 不在まで時間上限で止まりません（`src/dsv41/ds4_model.cu:1165,7213-7228`）。

`DS4_SETTLE_IDLE_MS` 自体と CLI 引数との優先順位はありません。アイドル機能を有効にする別変数 `DS4_SETTLE_IDLE` が `0` 相当なら、`_MS` の値にかかわらずスレッドが起動しません（`src/dsv41/ds4_main.cpp:721-734`）。

## 有効になる条件

- DSV41 engine の serve モードであること。通常の単発生成、profile、score などの処理ではこの serve idle loop を通りません（`src/dsv41/ds4_main.cpp:388,1293-1410`）。
- `DS4_SETTLE_IDLE` が未設定、または `std::atoi(value) != 0` であること。ここでは未設定が有効、空文字や数値に変換できない値は `atoi` の結果 0 となり無効です。判定は serve 開始時に一度行います（`src/dsv41/ds4_main.cpp:721-724,730-738`）。
- expert cache が有効で、cache worker が存在すること。`--no-expert-cache` を指定すると `Options::expert_cache` が false となり、idle cache 処理は即時 return します（既定値は true、`src/dsv41/ds4_main.cpp:1331`; `src/dsv41/ds4_model.hpp:37`; `src/dsv41/ds4_model.cu:7213-7215`）。
- 該当する DSV41 engine build であること。CMake の `STRATA_BUILD_DSV41` は既定 OFF で、`STRATA_HIP_GFX906` でない場合に `strata-dsv41` target へ `ds4_main.cpp` と `ds4_model.cu` が入ります（`CMakeLists.txt:907-918`）。

## 実行時の詳細

serve loop は要求を待つ直前に idle thread を開始し、入力行が届くか入力が閉じると cancel flag を立てて join します。モデル側は各 layer について、MTP、予備 VRAM slot 不在、既に swap 中の layer を飛ばし、VRAM にない expert のうち heat が 2.0 以上のものを候補として `cache_tick_swaps(0)` に渡します。in-flight swap がなくなれば終了し、そうでなければ 1 ms sleep して次の反復へ進みます。次の idle 区間でも再度処理できます（`src/dsv41/ds4_main.cpp:725-738`; `src/dsv41/ds4_model.cu:7218-7228`）。

`budget` は `cache_settle_idle()` 内の function-local `static const` です。expert cache と worker がある状態での最初の呼び出しで読み取られ、その後の idle 区間では同じ値を使います。実行中に環境を変更しても反映されません。`env_f` の既定値は 6000.0f です（`src/dsv41/ds4_model.cu:1165,7213-7218`）。

verbose 時は処理終了後に stderr へ `ds4: expert cache: N swaps in the idle (M ms, cancelled C)` を出します。`N` は swap 数、`M` は実経過時間を丸めたミリ秒、`C` は終了時点の cancel flag です。verbose が無効ならこの行は出ません。予算値が無効という警告や、この処理単独による終了コード・失敗経路はありません（`src/dsv41/ds4_model.cu:7229-7231`）。

## 根拠

- 環境値 helper の変換、既定値、cache の候補・終了条件・ログ: `src/dsv41/ds4_model.cu:1165,7213-7231`。
- serve 起動時の別トグル、idle thread の開始・キャンセル、要求待ち: `src/dsv41/ds4_main.cpp:721-738`。serve への分岐: `src/dsv41/ds4_main.cpp:1408-1410`。
- expert cache の既定値と `--no-expert-cache`: `src/dsv41/ds4_model.hpp:37`; `src/dsv41/ds4_main.cpp:1331`。
- build target と既定 OFF の条件: `CMakeLists.txt:907-918`。
