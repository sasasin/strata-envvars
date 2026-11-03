# `FNX_PRECAP_GRAPHS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX split engine が保持する batched-window CUDA/HIP graph cache の最大 entry 数を指定します。`FNX_PRECAP` が有効なとき、異なる window layout の graph を cache し、layout が再利用された場合に取り出します。上限を超えると least recently used entry が追い出されます。この変数自体は precapture の有効化を行いません。

## 値と判定

`fnx::env_int` が環境値全体を符号付き base-10 整数として読みます。符号は任意で、数字以外の末尾、空白、空文字は受け付けません。値の後にコード上の上限検査はなく、cache 上限に使う直前に `max(1, 値)` が適用されます。

| 値 | 結果 |
|---|---|
| 未設定 | 既定値 64 |
| 正の整数 | 指定数を cache 全体の上限にする |
| 0 または負の整数 | 1 に丸める（cache を空にする設定にはならない） |
| 空文字、整数でない文字列、long long の範囲外 | `std::runtime_error`。メッセージは `FNX_PRECAP_GRAPHS: '<値>' is not a whole number` |

parser は文字列全体を検査し、`strtoll` の範囲外を拒否します。cache 上限への `size_t` 変換は 1 以上に丸めた後に行われます。

## 有効になる条件

- Strata の通常エンジンではなく、`STRATA_BUILD_SPLIT=ON` で組み込む opt-in の sFNX split engine が対象です。ビルド設定上、Linux CUDA または Linux HIP のみが対象です。ビルド時に変数を読むのではなく、split engine の実行プロセスが読みます。
- `FNX_PRECAP` が有効で、現在の graph slot に graph がある状態で `batch_graph_stash()` に到達した場合に上限が使われます。`FNX_PRECAP` は HIP では既定 ON、CUDA では既定 OFF です（`src/split/src/engine_common.cu:238-245`）。
- `FNX_BATCH_DRAFTS` が `0` なら batched drafts は無効です。既定値（unset）は `1` 相当で、`lookup` も有効な mode です。`warm_graphs()` の uniform batched-window precapture は batch drafts が off でない場合に `FNX_PRECAP` と併せて実行されます（`src/split/src/engine_common.cu:328-380,1020-1028`）。
- CLI 引数や別設定による `FNX_PRECAP_GRAPHS` の上書きは、この読み取り経路にはありません。

## 実行時の詳細

`batch_graph_stash()` は precap が off、または slot に graph がない場合に何もせず戻ります。それ以外では、関数内の `static const size_t max_graphs` 初期化時に一度だけ環境値を読み、以後そのプロセス内の stash で同じ上限を使います。したがって、初回 stash 後に環境を変更しても反映されません（`src/split/src/engine_common.cu:290-293`）。

cache 数は `cb_[0]` の全 row-count bucket の entry 数を合計して判定します。上限に達しているときは全 bucket から最も古く使われた entry を選び、各 card の対応 graph exec を破棄して、その entry の作業 table を次の capture 用に再利用します。その後、新しい graph entry を現在の row-count bucket に追加します。上限は cache 内 entry に対するもので、現在 slot にある graph はこの集計に含みません（`src/split/src/engine_common.cu:247-257,290-326`）。

上限値の初期化時に parse error が起きると `env_int` は上記 `std::runtime_error` を投げます。stash は graph miss 後の capture 経路から呼ばれるため、その経路は例外になります（`src/split/src/env.hpp:15-22,33-40`; `src/split/src/engine_common.cu:932-935,1129-1136`）。sFNX server では初期化時の失敗が `ERR <例外文>` と stderr の `sfnx: failed: <例外文>` になり、終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1027-1035,1055-1062`）。`fnx_run` では stderr の `fnx_run: <例外文>` と終了コード 1 になります（`src/split/tools/fnx_run.cpp:1364-1373`）。正常な warm precapture では stderr に `fnx: warm: precapture ...` と、完了時に capture 数・平均 capture 時間・保持 graph 数を出しますが、これらは `FNX_PRECAP_GRAPHS` の値そのものを表示しません（`src/split/src/engine_common.cu:358-377`）。

## 根拠

- `src/split/src/engine_common.cu:290-326` — 上限の読み取り、全 bucket の件数、LRU eviction と entry の格納。
- `src/split/src/env.hpp:15-22,33-40` — 整数文字列の全体 parse、unset 時の default、無効値の例外。
- `src/split/src/engine_common.cu:238-245,260-277,328-380` — precap の backend 既定値、cache lookup、および warm precapture 条件。
- `src/split/src/engine_common.cu:932-935,1129-1136` — cache miss 後に stash が呼ばれる経路。
- `src/split/src/batch.cpp:64-85`; `src/split/src/engine_common.cu:1020-1028` — batch draft mode の読み取りと有効値。
- `src/split/CMakeLists.txt:1-5,20-30,92-115` — sFNX split engine の対象 build 条件と executable。
