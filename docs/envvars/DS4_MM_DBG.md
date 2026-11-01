# `DS4_MM_DBG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 上の DeepSeek 4.1 expert matrix multiply 経路（gate/up と down）で、バッファ wrapping、行列パラメーター、pipeline、dispatch 引数の情報を標準エラーへ出す診断用スイッチです。計算方法や dispatch を変える分岐ではなく、ログ出力の有無だけを切り替えます。

## 値と判定

`std::getenv("DS4_MM_DBG")` の結果が null かどうかだけを検査します。未設定ならログを出さず、設定されていれば値の内容を問わず出力対象です。したがって空文字、`0`、`false` も設定済みとして扱われます。数値変換、文字列比較、範囲判定はありません（`metal/src/engine/ds4_finish.cpp:2501,2512,2528,2614-2615`）。

この変数を読み取る箇所はすべて `mm_set()` 内で、各診断箇所で `getenv` を呼びます。値を `static` 等に保存するコードはなく、読み取り時のキャッシュはありません。CLI 引数や別の環境変数との優先順位・fallback もありません。

## 有効になる条件

この実装は `metal/` の macOS Metal ビルドに含まれます。`metal/CMakeLists.txt` は Apple 以外では設定を停止し、`strata_ds4` のソースに `metal/src/engine/ds4_finish.cpp` を含めます（`metal/CMakeLists.txt:13-16,127-140,165-175`）。CUDA/HIP/SYCL の `ds4_iq.cu` 経路では `STRATA_METAL` 条件の呼び出しがコンパイルされないため、この読み取りは使われません（`src/dsv41/ds4_iq.cu:1585-1608`）。

DeepSeek expert の gate/up または down 計算で、`hbounds` が非 null の場合に Metal host 関数が呼ばれます（`src/dsv41/ds4_iq.cu:1585-1608`）。ただし `mm_set()` は空の expert/row、未対応量子化形式、次元や stride 条件不成立、pipeline 準備失敗などで早期 return します。これらの経路では、その後にある `DS4_MM_DBG` ログ箇所に到達しないものがあります（`metal/src/engine/ds4_finish.cpp:2476-2484,2494-2495,2505-2507,2517-2528`）。

## 実行時の詳細

`DS4_MM_DBG` が設定され、対応する処理地点まで到達すると、次の内容が `stderr` に出ます。

- `mm wrap ...`: host memory の wrap 範囲の基底アドレスと長さ、Strata の GPU buffer に属するかを表す `own`、残り allocation bytes の `rem`（`metal/src/engine/ds4_finish.cpp:2497-2502`）。
- `mm gu` または `mm dn ...`: embedding/FFN 次元、gate/up と down の型、limit、stride、weight table offsets、行当たりの byte 数（`metal/src/engine/ds4_finish.cpp:2510-2512`）。
- `pipe ...`: 選択された pipeline 名、最大 thread 数、threadgroup memory、SIMD width（`metal/src/engine/ds4_finish.cpp:2517-2528`）。
- `arg ...`: gate/up または down dispatch の buffer size、bias、offset、pointer（`metal/src/engine/ds4_finish.cpp:2614-2615`）。
- `dn tile0 ...`: down dispatch で別の `DS4_MM_ONE` が設定されて grid を1 tile に制限した場合、その tile と grid/row 情報（`metal/src/engine/ds4_finish.cpp:2614`）。

これらは診断表示です。dispatch の成否や関数の戻り値を `DS4_MM_DBG` 自体が変える処理はありません。実際の計算を抑止・変更する環境変数はこの関数内に別途ありますが、それらの挙動は `DS4_MM_DBG` の作用ではありません（`metal/src/engine/ds4_finish.cpp:2598-2618`）。本変数に固有の警告、エラー、終了経路はありません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2497-2502,2510-2512,2517-2528,2614-2615` — `getenv` 判定と出力。
- `metal/src/engine/ds4_finish.cpp:2476-2484,2494-2495,2505-2507,2616-2634` — 診断が置かれた計算経路と早期 return、dispatch。
- `src/dsv41/ds4_iq.cu:1585-1608` — Metal 条件で gate/up・down host 関数を呼ぶ箇所。
- `metal/CMakeLists.txt:13-16,127-140,165-175` — macOS Metal と `strata_ds4` へのソース組み込み。
