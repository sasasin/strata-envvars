# `STRATA_SCORES_HALVE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の block score 計算で、複数 query をまとめる経路が使われるとき、warp 内の reduction を再帰的 halving 方式の `block_scores_halve_kernel` に切り替える。`qsa_block_scores` が出力した score 行は後段の top-k 選択に使われる。ソースコメントは旧 `block_scores_multi_kernel` と同じ score bits を作る経路として説明しているが、この調査では実行比較をしていない。実装は CUDA/HIP GPU engine 共通ソース `engine/src/kernels/cuda/qsa_select.cu` にある（カーネルと score の合成: `engine/src/kernels/cuda/qsa_select.cu:2055-2069,2135-2148`、呼び出しと後段: `engine/src/kernels/cuda/qsa_select.cu:2194-2229,3245-3256`）。

## 値と判定

`scores_halve_on()` の関数内 `static` 初期化で `std::getenv` の値を `std::atoi` に渡す。未設定は `-1` の sentinel となり GPU 別の既定判定へ進む。設定済みなら `atoi(v) != 0` がそのまま on/off になる。したがって空文字、数字で始まらない文字列、`0`、`0anything` は off、`1`、`-1`、`1anything` は on。先頭空白の後に数値があれば `atoi` の規則で変換される。文字列全体の検証、範囲検査、clamp はないため、`true` は数値に変換できず off になる。`atoi` で表現できない範囲の値は安全な入力として規定されていない（読み取りと変換: `engine/src/kernels/cuda/qsa_select.cu:2179-2181`）。

| 条件 | unset | 設定時に on | 設定時に off |
|---|---|---|---|
| 任意の対象 GPU | GPU ごとの既定を使う | `atoi(value) != 0`（例: `1`, `-1`, `1x`） | `atoi(value) == 0`（例: 空文字, `0`, `0x`, `false`） |

未設定時は現在 device を取得し、その compute capability が sm_75 かつ `STRATA_SM75_PERF` が設定されて `atoi` 非ゼロ、または sm_70 かつ `sm70_default_on()` が真なら on。それ以外は off。sm_70 側の `sm70_default_on()` は `STRATA_SM70_PERF` が未設定または先頭文字が `'0'` 以外で、かつ `STRATA_DEFAULTS` が厳密に `026` ではない場合に有効になる。ここでは `0.2.6` / `v0.2.6` は `026` と同じ扱いにならない（`engine/src/kernels/cuda/qsa_select.cu:2155-2161,2182-2191`; `engine/include/strata/core/sm75_series.hpp:24-37`）。

## 有効になる条件

- QSA GPU engine の当該 `qsa_block_scores` 経路を通ること。`nq > 0` で geometry が `IDX_DIM` / `IDX_HEADS` / `R` と一致し、`scores_multi_on()` が on、`nq <= MQ`、`active_blocks <= 0` のすべてを満たす必要がある（`engine/src/kernels/cuda/qsa_select.cu:2194-2205`）。
- `STRATA_SCORES_MULTI` が未設定または `atoi` 非ゼロであること。`0`、空文字、非数値文字列なら複数 query の分岐に入らず、この変数の値にかかわらず halve kernel は呼ばれない（`engine/src/kernels/cuda/qsa_select.cu:1607-1610,2201-2206`）。
- 同じ分岐内で `STRATA_QSA_ROWS` が厳密に文字列 `1` のとき、rows kernel が成功すれば先に return するため halve kernel は使われない。`1x` や `01` は rows 条件に一致しない（`engine/src/kernels/cuda/qsa_select.cu:2202-2206`）。
- `active_blocks > 0` の prompt 用分岐では halve 判定に進まない（`engine/src/kernels/cuda/qsa_select.cu:2201-2206,2231-2269`）。HIP 側には同じ関数の後続分岐があるが、これは `active_blocks > 0` の別処理。
- CUDA engine の起動時、可視 GPU が 1 枚以上かつすべて同じ compute capability と判定される場合は `apply_nv_defaults` が先に呼ばれる。Volta (sm_70) の default table は `STRATA_SM70_PERF` の先頭文字が `0` でなく、`STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` のどれでもなければこの変数を `1` に追加する。既に環境に名前が存在すれば、その値が `0` や空文字でも保持される。異なる capability の複数 GPU ではこの table 適用を飛ばすが、未設定時の `scores_halve_on()` 自身の GPU 別既定判定は残る。特に `0.2.6` / `v0.2.6` では table は適用されず、fallback 判定は文字列が厳密な `026` ではないため sm_70 で on になる（`engine/src/program/generate.cpp:4425-4449`; `engine/src/core/nv_defaults.cpp:136-163,222-234`; `engine/include/strata/core/defaults_026.hpp:22-29`）。

## 実行時の詳細

明示値は `scores_halve_on()` が最初に呼ばれた時に一度だけ読み、以後プロセス内で環境を変更しても反映されない。未設定時も環境値 sentinel は一度だけ保持し、GPU capability による既定結果を `ok[dev]` に device ごとにキャッシュする（`engine/src/kernels/cuda/qsa_select.cu:2179-2191`）。

halve が選ばれた場合、`nq` に応じて `V=4/8/16` のテンプレートカーネルを起動し、5–8 query は最大 4 query ずつに分けて計算する。各 query の 4 head の score を合成し、末尾の不完全 block には `1e9f` を加算する既存処理を行う（`engine/src/kernels/cuda/qsa_select.cu:2065-2072,2141-2148,2206-2220`）。後続の kernel launch エラーは stderr に `qsa_block_scores halve: <CUDA error string>` を出して `exit(1)`。geometry 不一致も stderr に `qsa_block_scores: unsupported indexer geometry` を出して終了する（`engine/src/kernels/cuda/qsa_select.cu:2197-2199,2221-2223`）。

## ログと測定値

halve の有効・無効だけを知らせるログはない。sm_70 の自動 default table が一つ以上の値を追加した場合は stderr に `strata: %s: %zu %sspeed switches on by default (%s=0 turns them off%s; a switch you set is kept%s): ` という書式文字列で告知し、続けて追加した変数名を空白区切りで出す。列挙項目に `SCORES_HALVE` が含まれる（`engine/src/core/nv_defaults.cpp:240-255`）。ただし利用者が先に設定した変数は追加リストに入らない。

コードコメントには Turing の測定例として 420K cells、query 数 1 / 3 / 6 に対する 117 / 265 / 509 μs とあるが、比較対象の説明は halving カーネルの動機としての従来 kernel であり、今回の checkout における再測定値ではない。機種などの完全な測定条件は同コメントに記されていないため、性能比較値としてはここでは扱わない（`engine/src/kernels/cuda/qsa_select.cu:2055-2063`）。

## 根拠

- 読み取り・変換・未設定時の capability 判定: `engine/src/kernels/cuda/qsa_select.cu:2179-2191`
- `STRATA_SCORES_MULTI`、QSA rows 分岐、適用条件、halve kernel の選択とエラー経路: `engine/src/kernels/cuda/qsa_select.cu:1607-1610,2194-2229`
- Volta の自動値と既存値優先: `engine/src/core/nv_defaults.cpp:136-163,222-234`; 起動時適用: `engine/src/program/generate.cpp:4425-4449`
- Turing既定条件: `engine/include/strata/core/sm75_series.hpp:24-37`; score 算出: `engine/src/kernels/cuda/qsa_select.cu:2055-2069,2135-2148`
