# `STRATA_QSA_DUMP_LAST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の選択セルを `STRATA_QSA_DUMP` のファイルへ追記する診断処理について、どの prompt position の chunk を dump するかを指定する。CUDA/HIP と SYCL の chunk 処理で、`p0 + T > pos0 + n - last` のときにその chunk の選択セルを出力する。変数単独では dump を有効にせず、`STRATA_QSA_DUMP` が設定されている場合にだけ値を読む。通常の QSA 選択・attention の計算そのものを切り替える値ではない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5507-5531`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3820-3844`）。

## 値と判定

`STRATA_QSA_DUMP` が設定され、該当する QSA prefill 処理に到達したとき、`std::getenv` で取得した文字列を `std::atoll` に渡す。変換後の値を clamp したり、文字列全体が数値であることを検査したりするコードはない。未設定だけ既定値 `4096` となる。明示的な空文字や数値として読めない文字列は `atoll` の変換結果 `0` となる。符号と先頭の空白は数値変換で扱われ、数値の後ろの文字は検査されないため、例えば `12tail` は `12` として扱われる。オーバーフロー値の扱いはこのコードで検査・規定していない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5512-5516`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3823-3826`）。

| 条件 | unset | 有効になる値（例） | 無効になる値・範囲例 |
|---|---|---|---|
| `STRATA_QSA_DUMP` が未設定 | 関連処理に入らず、この変数も読まない | なし | すべて無視 |
| CUDA/HIP または SYCL の dump 処理に到達し、`STRATA_QSA_DUMP` が設定済み | `4096` | 正の値（`1`, `4096`, `12tail`）で、chunk の終端が指定した末尾境界を越えると dump 対象になる | `0`, 負値（通常の position 範囲では条件成立なし）、空文字、`true`, `false`, `0anything`（いずれも変換結果 0） |

「有効」は末尾境界の計算に使われるという意味で、chunk が実際に条件を満たすかは別に判定される。`0` なら境界は prompt の終端 `pos0 + n` となり、chunk 終端は通常これを越えないため dump されない。正値でも chunk 単位の判定なので、指定位置数より多い position が含まれる chunk 全体が出力されることがある。値が prompt 長より大きい場合、境界が prompt 開始位置より前になり得るため、全 chunk が対象になり得る（同上）。

## 有効になる条件

- `STRATA_QSA_DUMP` が設定されている必要がある。値が空文字でも設定済みとして分岐に入るが、空のパスへの `fopen` は失敗し、dump は作られない（`engine/src/prefill/prefill.cpp:5512,5520`、`engine/sycl/src/prefill/prefill.cpp:3823,3838`）。
- 実行が QSA prefill layer/chunk 処理まで到達する必要がある。decode-only 処理にはこの読み取り位置がない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5507-5516`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3820-3826`）。
- CUDA/HIP の `Prefill::run` が layer-major 経路を選ぶと `run_layer_major` を呼んで戻るため、`run_impl` 内にあるこの dump 処理を通らない。Metal は `Prefill::run` で Metal prompt 経路へ分岐して戻る。これらの経路では本変数は適用されない（`engine/src/prefill/prefill.cpp:9629-9651,9657-9705`）。SYCL の `Prefill::run` は `run_impl` を呼ぶ（`engine/sycl/src/prefill/prefill.cpp:5959-5963`）。
- CUDA/HIP ではさらに `STRATA_QSA_DUMP_LAYER` が設定されている場合、`atoi` で得た値が負値なら全 QSA layer、非負なら一致する `qsa_index` だけを出力する。この条件は `STRATA_QSA_DUMP_LAST` の末尾判定と AND で適用される。SYCL 実装にはこの layer filter がない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5515-5516`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3823-3826`）。
- `STRATA_QSA_DUMP_STEPS` は CUDA/HIP で追加の step 配列も書くかを設定するが、末尾境界の計算には影響しない。SYCL の同 dump 箇所では step 配列を出力しない（`engine/src/prefill/prefill.cpp:5524-5529`、`engine/sycl/src/prefill/prefill.cpp:3838-3843`）。

## 実行時の詳細

両 backend とも、`STRATA_QSA_DUMP` の path は関数内 `static` として初めて該当処理に到達したときに読み込まれ、その後はプロセス内で cache される。`STRATA_QSA_DUMP_LAST` も static local で、dump path が設定されている場合に初めて評価され、一度変換した値がその後の呼び出しで使われる。したがって実行中に環境を変更しても、初回読み込み後は反映されない。`STRATA_QSA_DUMP` が未設定のままなら `STRATA_QSA_DUMP_LAST` の初期化自体が実行されない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5512-5515`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3823-3825`）。

条件を満たす chunk では、選択セル ID 配列を host memory にコピーして stream/queue を同期し、`STRATA_QSA_DUMP` のファイルを append binary (`ab`) で開く。各 record は int32 4 個の `{qsa_index, p0, T, cap}` header と `T * cap` 個の int32 selection ID からなる。ファイルは複数 record を追記する形式で、既存内容を truncate しない。CUDA/HIP では `STRATA_QSA_DUMP_STEPS` が設定されていると `T * kStepCount` 個の int32 step data も続けて書く（`engine/src/prefill/prefill.cpp:5516-5529`）。

## ログと測定値

この変数に固有のログや警告はない。ファイルを `fopen` できなかった場合は if 文内の書き込みを行わず、その失敗をログや戻り値に反映しない。`fwrite` の戻り値も検査しない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5520-5529`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3838-3842`）。実装コメントは `tools/qsa_locality.py` 用の dump と説明しているが、測定結果はこの値の仕様根拠として記載していない（`engine/src/prefill/prefill.cpp:5507-5511`、`engine/sycl/src/prefill/prefill.cpp:3820-3822`）。

## 根拠

- `engine/src/prefill/prefill.cpp:5507-5531` — CUDA/HIP の読み取り、境界判定、layer filter、データ追記。
- `engine/sycl/src/prefill/prefill.cpp:3820-3844` — SYCL の読み取り、境界判定、データ追記。
- `engine/src/prefill/prefill.cpp:9629-9705` — Metal と CUDA/HIP layer-major 経路の分岐、および `run_impl` 呼び出し。
- `engine/sycl/src/prefill/prefill.cpp:5959-5963` — SYCL の `run_impl` 呼び出し。
