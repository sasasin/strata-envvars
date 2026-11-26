# `STRATA_PREFILL_STREAM_AHEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prefill の routed-only expert staging で、次に計算する expert から何件先まで host-to-device 転送を進めるかを決める。未設定または 0 以外なら、リング内でまだ消費されていない転送数 `pending` が上限未満の間、次の転送を発行する。0 なら、処理位置から固定 lookahead 内にある expert だけを先行 staging する。対象は expert のアップロード順序であり、共有 expert の計算を router 後に遅らせる分岐も同じ設定で選ぶ。値による専用ログはない。実装は `engine/src/prefill/prefill.cpp` の `stream_ahead_enabled()` と prefill の二つの expert walk にある（`engine/src/prefill/prefill.cpp:348-355, 5661-5662, 7502-7518, 8831-8867`）。

## 値と判定

`std::getenv` の結果を `std::atoi` に渡し、変換結果が 0 以外かを判定する。未設定は有効 (`true`) として扱う。設定されている空文字、数値に変換できない文字列、および数値の先頭が `0` の文字列は無効になる。`atoi` のため文字列全体の厳密な検証はせず、先頭の空白と符号付き整数の数値部分を変換し、後続文字は判定に使わない。大文字小文字という概念はない。例えば `1`、`-1`、`2tail` は有効、`0`、`0tail`、`true`、空文字は無効。整数変換の範囲外入力の結果は文書化できない（`engine/src/prefill/prefill.cpp:349-355`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `stream_ahead_enabled()` を使う CUDA/HIP prefill 経路 | 有効 | `1`, `-1`, `2tail` | 空文字, `0`, `0tail`, `true` |

`stream_ahead_enabled()` は結果を関数内 `static const bool` に保存する。プロセスで最初にこの helper が呼ばれた時に一度読み、以後の環境変更は反映しない（`engine/src/prefill/prefill.cpp:349-355`）。この設定に対応する CLI 引数は確認できない。

## 有効になる条件

- 通常の chunk-major prefill では、expert walk が `!stream_all` の routed-only staging 経路に入り、かつその layer が weight-stationary 経路で処理されない場合に転送スケジュールへ影響する。`stream_all` は `m.ring > STAGE`、chunk token 数 `T >= stream_all_min()`、expert source `m.src != nullptr` のすべてが成立する場合である（`STAGE` は 8、`engine/src/prefill/prefill.cpp:321, 4625-4629, 7482-7496`）。従って `STRATA_PREFILL_RING` や `STRATA_PREFILL_STREAM_MIN` などでこれらの条件が変わると、この設定が使われる経路も変わる（`engine/src/prefill/prefill.cpp:648-658, 843-879`）。
- routed-only 経路で `STRATA_PREFILL_GROUP_GATHER` が未設定または `atoi` の結果が 0 以外なら、対象となる native layer の grouped staging で lookahead と pending 上限が `STAGE_GRP - MMQ_GROUP - 1` と `STAGE_GRP - MMQ_GROUP` を基に決まる。空文字・`0` などで無効なら通常の `STAGE - 1` と `STAGE`（8）を使う。resident expert は転送数 `pending` に含まれず、転送した expert の計算後に pending を減らす（`engine/src/prefill/prefill.cpp:7001-7013, 7502-7532`）。
- layer-major prefill が `Prefill::run` から選択されている場合も、layer 内の expert walk で `stream_ahead_enabled()` を参照する。ただし `fz_l` の fused layer は `fz_l ? ... : ...` の分岐で固定 `ahead` を使い、この設定の値をスケジュール判定に使わない。layer-major の選択条件は `STRATA_PREFILL_LAYER_MAJOR`、build/platform、stage 数などによる別の resolver に従う（`engine/src/prefill/prefill.cpp:9652-9660, 8831-8867`）。
- `engine/src/prefill/prefill.cpp` の Metal 用 `Prefill::run` 分岐は `prompt_run` を呼んで先に return するため、この helper を呼ぶ経路に入らない（`engine/src/prefill/prefill.cpp:9633-9650`）。SYCL は別の `engine/sycl/src/prefill/prefill.cpp` をビルドし、この候補名の参照は見つからなかった。CUDA/HIP の同じ prefill 実装が組み込まれる箇所は `engine/cmake/strata_gpu_engine.cmake:482`。

## 実行時の詳細

設定は prefill request ごとではなく、上記 helper のプロセス内初回呼び出しで評価・cache される。通常の chunk-major routed-only walk では、値が有効だと実際の未消費転送数 `pending < max_pending` を条件に `stage_one` を発行する。無効だと `staged <= j + lookahead` を条件にする。これにより resident expert が混ざっても、有効時は resident を除いた実転送数で先行枠を管理する（`engine/src/prefill/prefill.cpp:7502-7518`）。

同じ walk の前段では、有効かつ `!stream_all` の場合に共有 expert の計算を router の直後に実行せず、CPU grouping と routed-only path の初期 expert upload の後に実行する。無効時または `stream_all` 時は router 後すぐ共有 expert を計算する（`engine/src/prefill/prefill.cpp:5648-5662, 5993-6001`）。layer-major walk では有効・無効の判定式は同じ pending 枠方式だが、grouped layer は現在の group 内に staging を制限し、`fz_l` はこの設定を使わず `ahead` で先行させる（`engine/src/prefill/prefill.cpp:8790-8800, 8831-8867`）。

## ログと測定値

この環境変数の値、有効化、無効化を示す専用ログや、この値に固有のエラー・終了分岐はない。`stage_one` が失敗した場合は呼び出し元の prefill が失敗を返すが、その失敗条件は expert source や staging 処理側にあり、この変数を検査して発生させるものではない（`engine/src/prefill/prefill.cpp:7054-7074, 7513-7518, 8801-8828`）。このスイッチ自体を比較した測定値は確認できなかった。

## 根拠

- `engine/src/prefill/prefill.cpp:348-355` — 値の読み取り、未設定時の既定値、初回評価 cache。
- `engine/src/prefill/prefill.cpp:4625-4629, 7482-7518` — chunk-major の全 expert streaming 条件、routed-only 経路と staging 先行条件。
- `engine/src/prefill/prefill.cpp:7001-7013, 7520-7532` — grouped staging、resident expert と pending の扱い。
- `engine/src/prefill/prefill.cpp:5648-5662, 5993-6001` — 共有 expert 計算の遅延。
- `engine/src/prefill/prefill.cpp:8790-8800, 8831-8867` — layer-major walk の条件と fused layer の例外。
- `engine/src/prefill/prefill.cpp:9633-9650, 9652-9660` — Metal の早期経路と layer-major 選択位置。
- `engine/src/prefill/prefill.cpp:648-658, 843-879` — streaming floor と ring 条件。
- `engine/cmake/strata_gpu_engine.cmake:482`、`engine/sycl/CMakeLists.txt:304`、`engine/metal/CMakeLists.txt:143` — backend ごとの実装ビルド位置。
