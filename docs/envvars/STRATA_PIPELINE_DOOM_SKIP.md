# `STRATA_PIPELINE_DOOM_SKIP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の speculative decode で、先行 window の判定が外れて破棄予定になった window（`D`）を、残りの layer で最後まで処理するか、処理を省くかを切り替える診断用変数です。既定では省略を有効にし、破棄 window の残りの expert work を省いて stage 0 と pool を早く解放します。省略しても、その window の行は破棄され、snapshot の復元と正しい commit のやり直しが行われます。

## 値と判定

この変数は単独では参照されず、`pipe_dbg_env()` を通じて読み取られます。`STRATA_PIPELINE_DEBUG` が有効でなければ、この helper は常に `nullptr` を返します。

| `STRATA_PIPELINE_DEBUG` | `STRATA_PIPELINE_DOOM_SKIP` | 判定 |
|---|---|---|
| unset、空文字、または先頭文字が `0` | 任意 | helper が値を隠すため、既定の省略 ON |
| 先頭文字が `0` 以外で空文字ではない | unset | 既定の省略 ON |
| 同上 | `atoi(value) != 0` | 省略 ON |
| 同上 | `atoi(value) == 0` | 省略 OFF。破棄予定 window も最後まで処理 |

`atoi` を使うため、文字列全体の検証はありません。先頭の空白と符号付き整数は変換され、整数の後ろに文字があっても数値部分が使われます（例: `1tail` は ON、`0tail` は OFF）。空文字、数値に変換できない文字列、`0` は OFF です。`STRATA_PIPELINE_DEBUG` は「未設定でない」だけでは ON にならず、空文字と先頭が `0` の文字列は OFF、それ以外の非空文字列は ON です。

## 有効になる条件

- `--serve` の decode が実際に pipelined window loop に入る必要があります。該当 loop の入口は `pipe && pl_pw >= 2 && pl_snap_ok` です。単に環境変数を設定しても pipeline が使われない request では動作しません。
- `STRATA_PIPELINE_DEBUG` が有効な場合に限り、この変数の値が読まれます。無効時は `pipe_dbg_env()` が `nullptr` を返すため、値を `0` にしても省略を止められません。
- `doomed` は speculative window の予測が外れた場合（または終了処理）に立ち、`D` にその window が移されます。省略判定は `doomed && &w == &D` の場合だけ真になり、通常 window や破棄予定でない window には適用されません。
- CUDA 実装と SYCL 実装に同じ判定があります。各 backend の pipeline が実際に実行される場合に限ります。

## 実行時の詳細

`pipe_dbg_env()` は `STRATA_PIPELINE_DEBUG` の判定を関数内 `static const bool` に保存します。debug gate の初回評価後に環境を書き換えても再評価されません。`doom_skip` も pipeline loop 内の `pump0` にある `static const bool` で、最初に評価された値がプロセス内で保持されます。したがって、この変数は request ごとには再読込されません。

省略が有効で破棄予定の `D` を処理するとき、verifier の `service()` に通常の `drive_pool_split` ではなく `nullptr` を渡します。実装コメントでは、これにより残りの layer の CPU/GPU expert work を行わず、window の行を捨てて snapshot を戻すと説明されています。`STRATA_PIPELINE_DOOM_SKIP=0`（debug gate 有効時）は `service()` に通常の pool を渡し、window を最後まで処理します。この変数専用のログ出力はありません。

## 根拠

- `src/program/generate.cpp:340-346`: `STRATA_PIPELINE_DEBUG` gate と helper の値の返し方。
- `src/program/generate.cpp:14075-14088`: pipelined loop の入口、破棄 window の処理と `service()` 引数。
- `src/program/generate.cpp:14129-14133,14183-14190,14638-14651`: `D` と `doomed` の管理、誤った推測後の rollback 処理。
- `sycl/src/program/generate.cpp:297-300,10848,10893-10901,11355-11372`: SYCL 側の同じ helper / 判定 / rollback 経路。
- `docs/DETAILS.md` に本変数固有の仕様や測定値の記載は見つかりませんでした。
