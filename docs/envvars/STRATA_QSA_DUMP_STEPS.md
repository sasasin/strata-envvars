# `STRATA_QSA_DUMP_STEPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`Prefill::run_impl` が QSA の選択結果を `STRATA_QSA_DUMP` のファイルへ追記するとき、各レコードの末尾に各 query の QSA step 情報も保存します。既存のレコードは `int32` 4 個のヘッダーと `T * cap` 個の選択 cell で、その後ろに `T * kStepCount` 個の `int32` が続きます。`kStepCount` は 4 で、step は位置、KV cell 数、完了 block 数、選択幅を表します（`engine/src/prefill/prefill.cpp:5507-5527`、`engine/include/strata/kernels/qsa.hpp:160-177`）。

この分岐はデータをファイルへコピーする診断用処理です。step や選択結果を変更せず、読み取った値で QSA の計算分岐も変えません。一方、step の device-to-host コピーとファイル書き込みが加わります（`engine/src/prefill/prefill.cpp:5517-5529`）。

## 値と判定

値そのものは変換・比較せず、対象箇所で `std::getenv(...) != nullptr` かどうかだけを判定します。したがって空文字、`0`、`1`、`true`、`false`、その他の文字列はいずれも「設定あり」です。大文字小文字、空白、数値としての妥当性は検査しません（`engine/src/prefill/prefill.cpp:5524`）。

この判定が行われるのは、`STRATA_QSA_DUMP` が設定され、対象の prompt 範囲と QSA layer が dump 条件に合い、ファイルを開けた場合だけです（`engine/src/prefill/prefill.cpp:5512-5524`）。

| 条件 | 未設定 | 設定ありの例 | 無効になる値の例 |
|---|---|---|---|
| `STRATA_QSA_DUMP` のファイル出力が実行される | steps を付けない | 空文字、`0`、`1`、`true`、`false` | なし。設定値の内容による無効値はない |

## 有効になる条件

- `STRATA_QSA_DUMP` が設定されている必要があります。未設定なら外側の分岐に入らず、この変数も読み取られません。`STRATA_QSA_DUMP` が空文字の場合も設定済みとして分岐しますが、空のパスを `fopen` するため通常ファイルを開けず、steps は出力されません（`engine/src/prefill/prefill.cpp:5512-5524`）。
- 対象 chunk が prompt の末尾範囲にかかり、かつ `STRATA_QSA_DUMP_LAYER` が未設定または現在の QSA layer と一致する必要があります。末尾範囲は `STRATA_QSA_DUMP_LAST` で決まり、未設定時は 4096 です（`engine/src/prefill/prefill.cpp:5513-5516`）。
- QSA layer を処理する `run_impl` の経路が必要です。`STRATA_PREFILL_LAYER_MAJOR` / `STRATA_DEFAULTS` による設定解決後に layer-major が選ばれ、その prompt の `lm_prepare_chain` が通ると `Prefill::run` は `run_impl` を呼ばずに戻ります。layer-major の QSA 処理には debug dump がなく、`STRATA_QSA_DUMP_STEPS` 自体も layer-major を無効にする条件には含まれません（`engine/src/prefill/prefill.cpp:8205-8208, 9346-9349, 9657-9705`）。Metal は独自の `prompt_run` を呼んで戻るため、この箇所を通りません（`engine/src/prefill/prefill.cpp:9629-9651`）。

## 実行時の詳細

`STRATA_QSA_DUMP` のポインター、`STRATA_QSA_DUMP_LAST`、`STRATA_QSA_DUMP_LAYER` は関数内 `static` として初回評価時に保存されます。これに対し `STRATA_QSA_DUMP_STEPS` は dump 対象レコードごとに `getenv` されるため、その値をキャッシュしません。実行中に環境を変更できる場合、次の対象レコードの判定に反映されますが、既にキャッシュされた dump path・末尾長・layer 選択は再読込されません（`engine/src/prefill/prefill.cpp:5512-5525`）。

ファイルは `"ab"` で開かれ、既存内容の後ろへヘッダー、選択 cell、続けて step 配列を書きます。step 配列は `m.steps_dev` から `T * 4` 個の `int32` としてコピーされます（`engine/src/prefill/prefill.cpp:5517-5529`）。CLI 引数による上書きや優先順位はなく、この変数は値を読む他の環境変数もありません。`STRATA_QSA_DUMP`、`STRATA_QSA_DUMP_LAST`、`STRATA_QSA_DUMP_LAYER` が出力経路を絞ります。

## ログと測定値

この変数の読み取り・書き込みに伴う専用ログはありません。ファイルを開けない場合はそのレコードの書き込みを行わず、警告やエラーを出しません。step の device-to-host コピー、`fwrite` の戻り値もこの箇所では検査されないため、コピー失敗や短い書き込みを Strata が報告する経路は確認できません（`engine/src/prefill/prefill.cpp:5518-5529`）。

## 根拠

- `engine/src/prefill/prefill.cpp:5507-5529` — dump 条件、環境変数の読み取り、追記形式、steps の追加。
- `engine/src/prefill/prefill.cpp:4586-4591` — chunk の各位置について step レコードを作成し device に upload。
- `engine/include/strata/kernels/qsa.hpp:160-177` — 4 個の `int32` step フィールドと意味。
- `engine/src/prefill/prefill.cpp:9346-9349, 9629-9651, 9657-9705` — layer-major / Metal と `run_impl` の経路差。
- `engine/tests/cuda/pa_bench.cpp:1-3, 25-33` — 生成されたレコードを読み、steps がない場合に短い dump として扱うテスト用ツール。動作仕様の根拠にはしていません。
