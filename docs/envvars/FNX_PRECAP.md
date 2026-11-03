# `FNX_PRECAP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

split engine の `Engine::batch_graph_ready()` と `batch_graph_stash()` が、現在の slot にある CUDA graph と異なる lane/layout の graph を別 cache に保持・再利用するかを制御します。有効時は `FNX_PRECAP_GRAPHS` 件を上限に LRU で保持し、同じ key の graph が cache にあれば再 capture せず slot に戻します。無効時は現在の slot に一致する graph だけを再利用し、別 layout は再 capture します（`src/split/src/engine_common.cu:260-277,290-325`）。

この値は `Engine::precap()` が直接 `env_int("FNX_PRECAP", ...)` で読みます。CLI 引数や設定ファイルから同じ設定を与える経路は、対象 commit の参照箇所にはありません（`src/split/src/engine_common.cu:238-245`）。

## 値と判定

`env_int()` が値全体を符号付き base-10 整数として読みます。未設定なら backend ごとの既定値、設定済みなら整数値が 0 以外で有効です。

| ビルド | 未設定 | 設定値 |
|---|---:|---|
| `FNX_HIP` が定義された HIP build | 有効（既定値 1） | 整数 0 は無効、0 以外は有効 |
| `FNX_HIP` が定義されない build | 無効（既定値 0） | 整数 0 は無効、0 以外は有効 |

空文字、先頭・末尾の空白、末尾に文字が付く値、整数範囲外は整数として受理されず、`<名前>: '<値>' is not a whole number` の例外になります。先頭文字は `+`、`-`、または数字でなければならず、残りは数字のみです。したがって `+1`, `-1`, `00` は受理され、`1x`, ` 1`, 空文字は拒否されます。受理後の値に範囲制限はなく、負値も 0 以外なら有効です（`src/split/src/env.hpp:15-21,33-40`; `src/split/src/engine_common.cu:238-245`）。

## 有効になる条件

- split engine が `Engine::precap()` を呼ぶ経路で有効です。`sfnx` server は初期化時に `warm_graphs()` を呼びます。そこで `FNX_BATCH_DRAFTS` が `off` でなければ、この値が有効な場合に限り uniform な batched verify window を先に capture して cache に保持します（`src/split/tools/sfnx.cpp:435-446`; `src/split/src/engine_common.cu:328-378`）。
- `FNX_BATCH_DRAFTS` は未設定または `1` なら MTP drafts、`0` なら off、`lookup` なら lookup drafts です。これは上記の warm precapture 条件に影響します（`src/split/src/engine_common.cu:1020-1028`）。
- warm-up 後も、実際の graph key が cache 内にある場合に再利用します。cache に無い layout は通常の capture 経路に進みます。`FNX_CAPTURE_AFTER` はこの未 cache layout を最初に capture するまでの eager 実行回数に関係します（`src/split/src/engine_common.cu:260-277,279-287,1125-1187`）。
- `FNX_PRECAP_GRAPHS` は cache の容量であり、この機能の on/off ではありません。保持上限は未設定時 64、設定値が 1 未満なら 1 です（`src/split/src/engine_common.cu:290-302`）。

## 実行時の詳細

`precap()` 内の関数ローカル `static const bool` が最初の呼び出し時に値を評価し、以後はそのプロセス内で同じ結果を使います。起動後の環境変更は再評価されません（`src/split/src/engine_common.cu:238-245`）。`env_int()` 自体は毎回環境を読む helper ですが、この変数については `static` 初期化の中で一度だけ呼ばれます（`src/split/src/env.hpp:33-40`）。

`warm_graphs()` は通常の window graph と prompt 用 buffer を温めた後、`FNX_BATCH_DRAFTS` が有効で `FNX_PRECAP` が有効なら、uniform な複数 lane / 複数 row の batched window を capture します。stderr に `fnx: warm: precapture of the uniform batched windows ...` と capture 数・平均時間・保持 graph 数を含む完了行を出します（`src/split/src/engine_common.cu:328-377`）。この warm-up は `sfnx` server 初期化中、最初の request を受ける前に実行されます（`src/split/tools/sfnx.cpp:435-446`）。

無効値を読み込むと `env_int()` が `std::runtime_error` を投げ、fallback はありません（`src/split/src/env.hpp:33-40`）。`sfnx` の server 初期化中に発生した例外は stdout の `ERR <理由>` と stderr の `sfnx: failed: <理由>` を出し、終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1063-1092`）。`FNX_PRECAP_TRACE` は別の診断変数で、`verify_rows()` が graph を capture したとき等に `fnx: capture ... verify_rows ...` を stderr に出します。`FNX_PRECAP` 自体の状態を報告するログではありません（`src/split/src/engine_common.cu:1191-1197`）。

## 根拠

- 値の parse と不正値時の例外: `src/split/src/env.hpp:15-21,33-40`
- backend ごとの既定値と初回評価: `src/split/src/engine_common.cu:238-245`
- layout key の再利用、cache miss、LRU 保持: `src/split/src/engine_common.cu:260-277,290-325`
- warm-up precapture とログ: `src/split/src/engine_common.cu:328-378`
- 未 cache layout の capture と trace: `src/split/src/engine_common.cu:1125-1197`
- `sfnx` 初期化時の warm-up と失敗出力: `src/split/tools/sfnx.cpp:435-446,1030-1035,1063-1092`
- `FNX_BATCH_DRAFTS` の設定値: `src/split/src/engine_common.cu:1020-1028`
