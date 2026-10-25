# `STRATA_PIPELINE_THETA`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

パイプライン化した prompt verify window で、次の speculative window を投機的に起動するための受理確率しきい値を指定します。候補 window の推定値 `B.p_on` がこの値以上の場合に、CUDA 系では後段 stage への起動や prestage を許可します。SYCL も同様にしきい値で起動を判定します。

これは通常利用者向けの独立設定ではなく、`STRATA_PIPELINE_DEBUG` で有効になる pipeline のテスト・調整用フックです。値を読んでも `--pipeline-windows` の経路が実行されなければ効果はありません。

## 値と判定

| 状態 | `pl_theta` |
|---|---:|
| `STRATA_PIPELINE_DEBUG` が無効 | `STRATA_PIPELINE_THETA` は読まれず、既定値 `0.2` |
| debug が有効で `STRATA_PIPELINE_THETA` が未設定 | `0.2` |
| debug が有効で設定済み | `std::atof` の結果を `float` に変換 |

`std::atof` は文字列全体の厳密な検証やエラー通知を行いません。空文字や数値として読めない先頭部分は `0` になり、数値の後ろに続く文字列は変換結果に影響しません（例: `0.4tail` は `0.4`）。符号、小数、指数表記も `atof` の変換規則に従います。実装に clamp や有限値チェックはありません。値がしきい値比較にそのまま使われるため、負値は通常の確率推定値を通しやすくし、1を超える値は通常の確率推定値を通しにくくします。

ただし `STRATA_PIPELINE_SWITCH=<file>` が debug 有効時に読み込まれ、ファイル内容に `theta=` があれば、その値で環境変数由来の値を上書きします。ファイル側も `atof` で変換され、変換失敗時は `0` です。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が最初に確認された時点で設定され、空でなく、先頭文字が `0` でないこと。`1`, `true`, `false`, `2` は有効、空文字、`0`, `0anything` は無効です。大文字小文字や文字列全体は検査しません。
- `--pipeline-windows` が有効で、prompt の該当部分が pipelined verify-window loop に入ること。逐次 prompt 読み込みなど別経路ではこのしきい値は使われません。
- 推定値 `B.p_on` が `theta` 以上であること。値は通常の確率推定値に適用されます。しきい値が高いと次 window の投機的起動が抑えられます。

`STRATA_PIPELINE_DEBUG` の有効・無効判定は `pipe_dbg_env()` 内の `static const bool` に初回呼び出し時にキャッシュされ、プロセス内で後から環境を書き換えても再判定されません。一方、`STRATA_PIPELINE_THETA` は prompt 処理ごとに読み直されます。`STRATA_PIPELINE_SWITCH` が使われる場合、そのファイルは各該当 request で開かれます。

## 実行時の詳細

CUDA 系コードは pipelined prompt window の処理時に `pl_theta` を読み、window chain 内で `theta` として参照します。`B.p_on >= theta` は speculative window の開始判定に使われ、prestage が有効な場合の早期 prestage 判定にも使われます。SYCL 実装にも同じ比較があります。値をログ出力するのは `STRATA_PIPELINE_SWITCH` ファイルを正常に開けた場合の `strata pipeline switch: ... theta=...` 行と、pipeline 統計ログであり、環境変数だけを設定した場合に常に設定値を表示するログは確認できません。

## 根拠

- `src/program/generate.cpp:340-345` — `STRATA_PIPELINE_DEBUG` の判定と `pipe_dbg_env()` のキャッシュ。
- `src/program/generate.cpp:12924-12948` — 既定値 `0.2`、`atof`、switch ファイルからの上書きとログ。
- `src/program/generate.cpp:14112-14114,14484,14514-14520` — しきい値比較と投機起動。
- `sycl/src/program/generate.cpp:296-301,10167-10190,10794,11229,11253` — SYCL 側の対応実装。
- `docs/MULTI_GPU.md:498-500` — `STRATA_PIPELINE_*` の調整・テスト変数は `STRATA_PIPELINE_DEBUG=1` のときだけ読むとの説明。
