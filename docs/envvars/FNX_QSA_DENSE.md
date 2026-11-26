# `FNX_QSA_DENSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

split engine の QSA（選択型 attention）で、通常は indexer が選ぶ KV 位置のリストを使うところを省き、現在行までの全 KV 位置を attention に渡します。コメントには比較用とありますが、コード上は attention が参照する位置集合を切り替える処理です。通常のモデルや全 backend に共通する設定ではなく、`engine/src/split/src/kernels.cu` の QSA 実装に限られます（`engine/src/split/src/kernels.cu:1280-1286,1315-1328,1359-1377`）。

## 値と判定

`env_flag()` は `env_int(name, 0) != 0` です。未設定だけが既定値 0 になり、設定値は符号付き 10 進整数として全体を解析します。空文字、前後の空白、整数の後ろに文字がある値、整数でない文字列、`long long` の範囲外は無効で、`<name>: '<value>' is not a whole number` の例外になります。数値として有効なら 0 以外（負数も含む）が ON です。clamp はありません（`engine/src/split/src/env.hpp:15-21,33-39,51-52`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| split engine の QSA 実装 | OFF（選択処理を実行） | `1`, `-1`, `+2` | `0`, `-0`, 空文字, `true`, `1x`, `0anything`, ` 1`, 整数範囲外 |

`0` は通常の選択処理へ進みます。`true` / `false` を真偽値として扱う規則や、大文字小文字の変換はありません（`engine/src/split/src/env.hpp:15-21,34-39,52`）。

## 有効になる条件

- split engine のビルドに QSA launcher を含む `FNX_KPART == 5` のコードがあること（`engine/src/split/src/kernels.cu:1280`）。このソースは CUDA runtime / HIP 互換層を使う実装です（同 `:6-8`）。
- モデル実行が QSA の `Engine::attention()` または lane / MTP の `qsa_select_lanes()` に到達すること。通常の `Engine::attention()` は `qsa()` で indexer の出力を用意し、後続の `attn()` に選択数を渡します（`engine/src/split/src/engine.cu:908-927`）。lane 処理と MTP は `qsa_select_lanes()` を経由します（同 `:1111-1115,1197-1201,1397-1400`）。
- lane 経路では `LaneRows` の `pos` と `pt` が必要です。どちらかが null の場合は、環境変数を評価する前に `qsa_select_lanes: no lane rows` 例外になります（`engine/src/split/src/kernels.cu:1315-1320`）。
- prompt の選択処理は別の `qsa_select()` にあり、この関数では `FNX_QSA_DENSE` を読まず通常の `k_idx_score` / `k_idx_select` を実行します。したがって、この変数だけで prompt の全行が dense attention に切り替わるとは言えません（`engine/src/split/src/kernels.cu:1305-1312`; 呼び出し `engine/src/split/src/prefill.cu:1677-1682`）。

## 実行時の詳細

読み取り箇所は `qsa_select_lanes()` と `qsa()` の 2 箇所です。それぞれの関数内 `static const bool` に保存され、各関数で最初に実行されたときに一度だけ環境値を判定します。正常に初期化された後のプロセス環境変更はその関数の判定に反映されません。2 つの static は別々に初期化されます（`engine/src/split/src/kernels.cu:1315-1320,1359-1370`）。

ON の場合、両関数は QSA indexer の選択 kernel を呼ばず、`n_cells` の各行を `cudaMemsetAsync(..., 0xff, ...)` で `-1` にして戻ります。後続の `k_attn_part` は `n_cells[t] < 0` を選択リストなしの印として扱い、現在行の位置と card の割り当てから `kv_owned()` を計算します。その結果、各 card が所有する現在行までの位置を走査します。OFF なら `k_idx_score` と `k_idx_select` が選択リストを作ります（`engine/src/split/src/kernels.cu:1319-1328,1367-1377,512-517,519-528`）。

この切替は QSA が attention に渡す KV 位置集合に作用します。ここでのコードから生成 token や性能・数値的一致を断定できる測定値はありません。CLI 引数や別環境変数による `FNX_QSA_DENSE` の上書きは見つかりません。

## ログと測定値

有効時に `FNX_QSA_DENSE` 専用の有効ログや警告はありません。無効な文字列は env helper が例外 `FNX_QSA_DENSE: '<値>' is not a whole number` を投げます。`sfnx` の実行中に発生した例外は stdout に `ERR <例外>`、stderr に `sfnx: failed: <例外>` を出して終了コード 1 になります（`engine/src/split/src/env.hpp:34-39`; `engine/src/split/tools/sfnx.cpp:1097-1103,1160-1163`）。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-39,51-52` — 整数値の全体 parse、既定値、flag 判定。
- `engine/src/split/src/kernels.cu:1280-1286,1305-1328,1359-1377` — QSA の選択関数、環境変数の全読み取り箇所、dense 分岐。
- `engine/src/split/src/kernels.cu:512-528` — `-1` sentinel から全所有位置を処理する経路。
- `engine/src/split/src/engine.cu:908-927,1111-1115,1197-1201,1397-1400` — decode / lane / MTP の呼び出しと attention への引き渡し。
- `engine/src/split/src/prefill.cu:1677-1682` — prompt は別の選択関数を使う。
- `engine/src/split/tools/sfnx.cpp:1097-1103,1160-1163` — 実行時例外の出力と終了処理。
