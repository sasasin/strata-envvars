# `STRATA_PIPED_CONCURRENT_PRIO`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

CUDA の Verifier が内部 stream を作るとき、`STRATA_PIPED_CONCURRENT` も非 0 なら stream priority range の最高優先度で作成するかを制御します。この変数だけでは concurrent prompt 読み込みを有効にしません。また、priority の判定箇所は concurrent read の他の適用条件を検査しないため、それらの条件で concurrent read が無効でも stream priority は試され得ます。

## 値と判定

判定は `std::atoi()` の結果が 0 かどうかです。文字列全体の妥当性検査はなく、10進数として先頭から変換できる部分を使います。したがって `1`, `-1`, `2abc`, ` 1` は非 0、未設定、空文字、`0`, `abc`, `1abc` のうち `1abc` は先頭の数値 `1` に変換されるため非 0 です（`abc` は 0）。

| `STRATA_PIPED_CONCURRENT` | `STRATA_PIPED_CONCURRENT_PRIO` | priority stream を試すか |
|---|---|---|
| `atoi` が 0（未設定・空文字を含む） | 任意 | いいえ |
| `atoi` が非 0 | 未設定 | はい |
| `atoi` が非 0 | `atoi` が 0（空文字・数値で始まらない文字列を含む） | いいえ |
| `atoi` が非 0 | `atoi` が非 0 | はい |

この条件は `Verifier::init()` 内の関数ローカル static に保存され、最初に `make_stream()` が呼ばれた時点で評価されます。同じプロセスで以後の環境変更は反映されません。値のオーバーフロー時の扱いは `atoi` に委ねられており、Strata 側に追加の範囲処理はありません。

## 有効になる条件

- `src/core/verify.cpp` の該当分岐がコンパイルされる CUDA ビルド（`STRATA_USE_HIP` と `STRATA_HIP_GFX906` が定義されていない場合）に限られます。HIP と GFX906 のビルドではこの変数を読みません。
- `STRATA_PIPED_CONCURRENT` 自体も `std::atoi()` で非 0 と判定されなければ、priority は要求されません。priority 分岐と concurrent read の適用判定は別です。後者には `generate.cpp` が構成を検査して `concurrent_read_off()` が理由を返さないこと、batch の piped 経路であること、画像入力がないことなど別の条件があります。
- `Verifier` に外部 stream が渡されている場合、`cs_` はその stream を共有するため、この関数は `cs_` を作成しません。pipeline stage stream は `generate.cpp` 側で `cudaStreamCreateWithFlags()` により作られます。この環境変数が直接指定するのは `Verifier::init()` の `make_stream()` を通る内部 stream です。

## 実行時の詳細

条件が成立すると `cudaDeviceGetStreamPriorityRange()` で優先度範囲を取得し、上端 `top` を指定して `cudaStreamCreateWithPriority(..., cudaStreamNonBlocking, top)` を試します。priority range の取得または priority stream の作成に失敗した場合は CUDA の直近エラーをクリアし、通常の `cudaStreamCreateWithFlags(..., cudaStreamNonBlocking)` に fallback します。通常 stream の作成にも失敗すれば `Verifier::init()` が `verify: copy stream create failed` または `verify: stream create failed` を返します。priority の試行自体について専用ログはありません。

この `make_stream()` は copy stream、外部 stream が未設定の場合の `cs_`、および `sh_cs_` の作成に使われます。HIP の独立 copy-stream 分岐は別の `STRATA_COPY_HIP_PRIO` を参照しますが、`STRATA_PIPED_CONCURRENT_PRIO` の対象ではありません。

## 根拠

- 値の取得、`atoi` 判定、ビルド条件、priority 作成と fallback: `src/core/verify.cpp:848-886`。
- `Verifier::init()` の位置: `src/core/verify.cpp:634`。
- concurrent read の環境変数判定、設定不適合時のログ、および `piped && pr_conc && req_imgs.empty()` の適用条件: `src/program/generate.cpp:12870-12893`。
- pipeline stage の外部 stream 作成と Verifier への設定: `src/program/generate.cpp:8418-8429`。
- 設計資料は concurrent read の window streams を CUDA の最高優先度で実行し、`STRATA_PIPED_CONCURRENT_PRIO=0` で既定 priority に戻すと説明しています: `docs/BATCHING.md:197-200`。これは資料の説明であり、上記の stream 作成分岐と区別しました。
