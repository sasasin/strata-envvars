# `HY4_PF_MIN_T`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

HY4 の CPU tier expert を使ったハイブリッド実行で、prefill streaming を適用する最小 chunk token 数 `T` を指定する。既定値は 128 で、`T >= pf_min_T` のとき streaming 経路が有効になる。値は計算結果や expert 選択を変更する設定ではなく、CPU tier expert の取得・転送を prefill 処理に組み込む経路の適用閾値である（`engine/src/hy4flash/run/hy4_graph.hip.h:270-272,372,405-406`）。

環境変数を読むのは `Runner::pf_init()` であり、HY4 の共通 GPU 実装ヘッダーにある。この実装は `strata-hy4` の CUDA または HIP ビルドに使われる。CMake では `STRATA_BUILD_HY4` は既定 OFF で、ON にする場合 CUDA または HIP のいずれかを要求する。Metal/SYCL は別実装であり、この読み取り箇所はない（`engine/CMakeLists.txt:846-852,884-890`; `engine/src/hy4flash/run/hy4_main.hip.cpp:11`）。

## 値と判定

`getenv("HY4_PF_MIN_T")` が null でなければ、その文字列を `atoi` に渡して `pf_min_T` に代入する。したがって未設定ならフィールド初期値 128 のまま、空文字は設定済みとして `atoi("") == 0` になり、0 として扱われる。全体の数値妥当性や末尾文字の検査、clamp はない。`atoi` の数値変換規則により、先頭の空白と符号付き 10 進整数の接頭辞を変換し、変換できる数字がなければ 0 になる。例えば `256tail` は 256、`words` は 0 となる。大文字小文字の区別は値を文字列比較しないため該当しない。

| 条件 | unset | 値の例と結果 |
|---|---|---|
| `pf_init()` が当該箇所まで到達 | 既定値 128 | `128` は閾値 128、`0` / 空文字 / `words` は閾値 0、`-1` は閾値 -1、`256tail` は閾値 256 |
| `pf_init()` が呼ばれない、またはそれ以前に戻る | 環境変数を読まず、streaming は未初期化 | 値は実行に影響しない |

chunk ごとの判定は整数比較 `T >= pf_min_T` で、境界値を含む。HY4 の chunk token 数は正の値として渡されるため、閾値 0 や負数なら全 chunk が閾値判定を通る。非常に大きい値なら通常の chunk は通らない。範囲検査がないため、範囲外入力の変換結果を独自に保証するコードはない（`engine/src/hy4flash/run/hy4_graph.hip.h:372,405-406,639`）。

## 有効になる条件

- `strata-hy4` の CUDA/HIP 実装を使うこと。Metal/SYCL 実装でこの変数は読まれない（`engine/CMakeLists.txt:848-852,884-890`; `engine/src/hy4flash/run/hy4_main.hip.cpp:11`）。
- モデルの expert 配置が CPU tier を含み、初期化で `hyb` が true になること（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1583`）。
- `HY4_PF_STREAM` が未設定、または `atoi` 結果が 0 以外であること。`HY4_PF_STREAM=0`（および `atoi` が 0 を返す値）では `pf_init()` 自体を呼ばない（`engine/src/hy4flash/run/hy4_graph.hip.h:1706-1708`）。
- `pf_init()` が、CPU expert が存在するか、必要な scratch / bounce buffer 等の確保に成功して `pf_stream = true` まで到達すること。CPU expert の最大 layer byte 数が 0 なら早期 return し、scratch 容量不足または pinned bounce ring 確保失敗時にも streaming を無効にして戻る（`engine/src/hy4flash/run/hy4_graph.hip.h:545-563,597-600,603-620,621-646`）。
- chunk の `T` が設定閾値以上であること。満たさない chunk は prefill streaming 判定に入らない（`engine/src/hy4flash/run/hy4_graph.hip.h:405-406,2473,3403-3405`）。
- 閾値以上でも経路は一つではない。`T < HY4_PF_GATHER_MAX_T` かつ bounce buffer がある場合は active-expert gather、それ以外は通常の prefill pipe 判定になる。HY4_PF_MIN_T は上限や gather 条件そのものは変えない（`engine/src/hy4flash/run/hy4_graph.hip.h:373,405-406,2473-2492,3403-3405`）。

## 実行時の詳細

初期化処理は CPU tier expert の有無を調べ、GPU / host 側の buffer と stream 等を準備した後に環境変数を読み、`pf_stream` を true にして group を構築する。初期化時の読み取りはこの一度で、値を `Runner` の `pf_min_T` に保存する。prefill chunk ごとに環境を再読せず、`pf_active(T)` と `pf_use_gather(T)` が保存値と chunk の `T` を比較するため、プロセス実行中に環境を変更してもこの Runner の閾値には反映されない（`engine/src/hy4flash/run/hy4_graph.hip.h:405-406,545-646,1706-1708`）。

閾値以上の chunk では、`moe_hybrid_tail()` が GPU 側の router index などを必要に応じて host に取り出し、gather 条件を満たすとその chunk で使用される CPU tier expert のみを集めて転送対象にする。それ以外の prefill pipe 経路では、各 layer の CPU tier expert 群を scratch buffer に DMA し、attention 等の GPU 処理と重ねる。従って閾値を下げると小さな prefill chunk もこの処理経路の候補となり、上げると閾値未満の chunk は通常の hybrid tail 経路を使う。出力 token の内容を閾値で変更する処理はこの分岐にはない（`engine/src/hy4flash/run/hy4_graph.hip.h:270-272,2473-2511,3403-3405`）。

## ログと測定値

初期化成功後、group 構築時に stderr へ `[hybrid] prefill streaming on (...)` と出力し、末尾に `active for T >= %d (gather < %d)` と実効閾値を表示する。設定値が既定値でも同じ初期化ログに閾値が含まれる。scratch buffer の容量不足時は `[hybrid] prefill streaming disabled: no room for a scratch buffer ...`、pinned bounce ring の確保失敗時は `[hybrid] prefill streaming disabled: cannot allocate ... pinned bounce ring ...` を出す。CPU expert がない場合はその箇所で無言で戻る。`HY4_PF_MIN_T` 自体の値不正を示す警告やエラーはなく、別途性能測定値を記録する処理もこの設定にはない（`engine/src/hy4flash/run/hy4_graph.hip.h:541-543,562,597-600,617-620`）。

`docs/DETAILS.md` にこの閾値の説明や条件付き測定値は見当たらず、ここでは性能向上や精度への影響を主張しない。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:270-272,372,405-406,639` — 初期閾値、読み取り・変換、active/gather 判定。
- `engine/src/hy4flash/run/hy4_graph.hip.h:545-646,1706-1708` — streaming 初期化、資源不足時の return、呼び出し条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1564-1583,2473-2511,3403-3405` — CPU tier 条件と chunk 処理経路。
- `engine/CMakeLists.txt:846-852,884-890`; `engine/src/hy4flash/run/hy4_main.hip.cpp:11` — 対象バイナリと backend のビルド条件。
