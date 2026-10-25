# `STRATA_PIPELINE_LOG`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`--pipeline-windows` の pipelined decode ループが、speculative chain と window の verdict を stderr に記録する診断用スイッチです。生成や検証の判断を変える制御ではなく、すでに進行するループの内部状態をログに出すために使われます。CUDA と SYCL の `generate.cpp` に同じ役割の実装があります。

## 値と判定

この変数の値は文字列として parse されません。`pipe_dbg_env("STRATA_PIPELINE_LOG") != nullptr` で設定有無だけを判定するため、空文字を含め、どんな値でも「設定済み」ならログ要求になります。ただし共通 helper は先に `STRATA_PIPELINE_DEBUG` を確認します。

| `STRATA_PIPELINE_DEBUG` | `STRATA_PIPELINE_LOG` | 結果 |
|---|---|---|
| 未設定、空文字、または先頭文字が `0` | 任意 | helper が `nullptr` を返し、ログは無効 |
| 先頭文字が `0` 以外の非空文字列 | 未設定 | `nullptr` が返り、ログは無効 |
| 先頭文字が `0` 以外の非空文字列 | 設定あり（空文字を含む） | ログ有効 |

`STRATA_PIPELINE_DEBUG` は完全一致や数値変換ではなく、先頭文字だけで判定します。たとえば `false` や `2` は有効、`0anything` は無効です。`STRATA_PIPELINE_LOG=0` も設定有りとして扱われるため、debug gate が開いていればログ有効です。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が上表の有効条件を満たす必要があります。Strata の `docs/MULTI_GPU.md` も `STRATA_PIPELINE_*` の調整・テスト変数をこの debug gate 配下に説明しています。
- 実際に `--pipeline-windows` の pipelined decode 経路が実行される必要があります。変数だけを設定しても、その経路を選択しなければ、このコードの `pl_log` 判定や出力には到達しません。
- このソースで確認できるのは CUDA 実装 (`src/program/generate.cpp`) と SYCL 実装 (`sycl/src/program/generate.cpp`) です。他 backend の対応はこの調査では確認できません。

## 実行時の詳細

CUDA/SYCL それぞれの pipelined decode ループ内で、`pl_log` を関数内 `static const bool` として初回評価し、`pipe_dbg_env("STRATA_PIPELINE_LOG")` が null でないかを保存します。helper の `STRATA_PIPELINE_DEBUG` 判定も static に一度だけ評価されます。そのため、各判定が初回に行われた後でプロセス環境を変更しても反映されません。

`pl_log` が true の場合、chain を作ったときに `strata pipeline: chain ...`、window の検証結果を確定したときに `strata pipeline: verdict ...` を stderr に出します。CUDA の verdict ログには採用出力 token ID も続けて表示します。SYCL は chain と verdict の状態を記録します。これらは `fprintf(stderr, ...)` による診断出力で、`STRATA_PIPELINE_LOG` 自体が token、window size、speculation の採否を変更する分岐はありません。

## 根拠

- `src/program/generate.cpp:340-346` — `STRATA_PIPELINE_DEBUG` gate の値判定と `pipe_dbg_env`。
- `src/program/generate.cpp:14114` — CUDA 側 `pl_log` の static 判定。
- `src/program/generate.cpp:14491-14493,14609-14615` — CUDA 側 chain/verdict ログ。
- `sycl/src/program/generate.cpp:297-300` — SYCL 側 gate helper。
- `sycl/src/program/generate.cpp:10796,11236-11238,11345-11347` — SYCL 側 `pl_log` と chain/verdict ログ。
- `docs/MULTI_GPU.md:498-500` — `STRATA_PIPELINE_*` 診断・調整変数に必要な debug gate の説明。
