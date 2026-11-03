# `FNX_CAPTURE_AFTER`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の batched `verify_rows()` で、見たことのない window layout を CUDA/HIP graph に capture する前に、何回 eager 実行するかを指定します。eager 実行では同じ window の kernel を graph capture せず個別に enqueue します。既に graph が保持されている layout はこの設定にかかわらずその graph を使います。

## 値と判定

`src/split/src/env.hpp:15-21,33-40` の `env_int()` は、値全体を符号付き base-10 `long long` として読みます。先頭の `+` / `-` は許されますが、空白、空文字、数字以外の後続文字、範囲外の値は受け付けません。未設定時のみ backend ごとの既定値を使います。

| ビルド | 未設定時 | 整数値の効果 |
|---|---:|---|
| HIP (`FNX_HIP=1`) | `2` | 2 以上なら layout ごとに初回から `N-1` 回を eager 実行し、N 回目に capture。1 以下なら初回から capture。 |
| CUDA (`FNX_HIP` 未定義) | `0` | 2 以上なら layout ごとに初回から `N-1` 回を eager 実行し、N 回目に capture。1 以下なら初回から capture。 |

たとえば `2` は最初の実行を eager にして、次の未保持 layout の実行時に graph を capture します。`1`、`0`、負数は eager 実行を挟まず、最初の未保持 layout で capture します。上限・下限への clamp はありません。空文字や `2x` などの不正値は `FNX_CAPTURE_AFTER: '<値>' is not a whole number` の例外になります。

## 有効になる条件

- 変数を読むのは `src/split/src/engine_common.cu` の `Engine::lazy_capture()` です。split engine の HIP/CUDA ビルドで使われ、Strata の CMake 設定では `strata-split` 自体が opt-in です（`src/split/CMakeLists.txt:1-5,20-25,64-80,96-103`）。
- 適用対象は `verify_rows()` のみです。入力 layout の graph が現行 slot または cache にあれば、その graph が使われて判定関数は呼ばれません。cache miss 時にのみ値を参照し、eager/capture の選択を行います（`src/split/src/engine_common.cu:260-277,1125-1135`）。
- `verify_rows()` は batch decoder の window から呼ばれます（`src/split/src/batch.cpp:120-141`）。単一 window の `verify()` / `step()` や prefill、他の Strata engine の graph 設定を変える変数ではありません。
- CLI 引数や別の環境変数による上書きは、この値の読み取り経路にはありません。

## 実行時の詳細

HIP では未設定時の `after` が `2`、CUDA では `0` です。値は `lazy_capture()` 内の function-local `static const` に保存されるので、最初にこの関数が呼ばれた時点で一度だけ環境から取得され、その後の環境変更は反映されません。この static 値は process 内で共有されます。一方、layout ごとの出現回数 `seen_` は `Engine` instance の map です。cache miss のたびに `++seen_[key] < after` を評価し、真なら eager、偽なら graph capture に進みます（`src/split/src/engine_common.cu:279-288,1131-1189`; `src/split/src/engine.hpp:326-330`）。

eager の場合は、layout 用 table を eager 用 buffer と交換して `enqueue_rows()` を実行し、capture を開始せずに table を戻します。その後 `verify_rows()` は通常どおり stream を同期し、結果と window error を確認します（`src/split/src/engine_common.cu:1137-1179,1255-1292`）。capture を行う場合は CUDA/HIP stream capture を開始・終了し、graph を install します（同 `:1175-1189`）。

不正値の例外は `std::runtime_error` です。読み取りは `verify_rows()` の graph cache miss 時なので、sfnx の server loop で発生した例外は `fail()` まで伝播し、stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:646-668,961-970,1086-1092,1027-1035`）。値の有効性を確認する専用ログはありません。`FNX_PRECAP_TRACE` が有効なら stderr の `fnx: eager verify_rows ...` / `fnx: capture verify_rows ...` 行で選択結果を観測できます（`src/split/src/engine_common.cu:1191-1197`）。

## 根拠

- 全候補名の参照検索では、実装上の参照は `src/split/src/engine_common.cu:281,283` の2箇所で、いずれも共通 helper `env_int()` を通じた読み取りです。他の参照はコメントです。
- helper の parse 規則とエラー文: `src/split/src/env.hpp:15-21,33-40`。
- backend ごとの既定値と eager/capture 閾値: `src/split/src/engine_common.cu:279-288`。
- 適用する cache miss、実行分岐、統計上の eager/capture 区分: `src/split/src/engine_common.cu:260-277,1125-1197`; `src/split/src/engine.hpp:199-212,326-330`。
- split engine の backend/build 条件: `src/split/CMakeLists.txt:1-5,20-25,64-80,96-103`。
