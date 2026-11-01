# `STRATA_PIPELINE_PRESTAGE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`--pipeline-windows 2` の speculative decode で、次の window B の verifier 入力を実際の launch より前に host 側で stage するかを制御します。既定では stage を先行させます。無効にすると、B を launch する箇所で通常の stage 処理を行います。対象名は `src/program/generate.cpp` と `sycl/src/program/generate.cpp` に各1箇所あり、どちらも `Verifier::prestage()` の呼び出しを制御します。

## 値と判定

この設定は `pipe_dbg_env()` を通して読みます。同 helper は `STRATA_PIPELINE_DEBUG` を初回呼び出し時に `static` へ cache し、値が未設定・空文字・先頭文字 `0` の場合は、すべての `STRATA_PIPELINE_*` tuning/test 値について `nullptr` を返します。それ以外の値なら、指定された名前を `getenv()` で取得します。したがってデバッグ gate が無効の場合、この変数は未設定と同じ既定値になります。

gate が有効な場合、`STRATA_PIPELINE_PRESTAGE` 自体の判定は次のとおりです。

| `STRATA_PIPELINE_DEBUG` | `STRATA_PIPELINE_PRESTAGE` | 結果 |
|---|---|---|
| unset、空文字、先頭が `0` | 任意 | helper が `nullptr` を返し、既定 ON |
| gate 有効 | unset | 既定 ON |
| gate 有効 | `atoi(value) != 0` | ON |
| gate 有効 | `atoi(value) == 0` | OFF |

変換は `std::atoi` で、文字列全体の厳密な検証ではありません。空文字、数字で始まらない文字列、`0` または `0` の後に文字が続く値は 0 となり OFF です。先頭の空白と符号付き10進整数は `atoi` の規則で処理され、整数部分の後ろの文字列は判定に使われません（例: `1junk` は ON、`-1` は ON）。範囲 clamp や無効値の警告・fallback はありません。

`STRATA_PIPELINE_DEBUG` の gate 結果はプロセス内で初回 `pipe_dbg_env()` 呼び出し時に cache されます。`pl_prestage` も pipeline decode 経路で初めて初期化される `static const bool` です。その後に環境変数を変更しても、このプロセス内の判定は再評価されません。

根拠: `src/program/generate.cpp:461-467,16365-16368`; `sycl/src/program/generate.cpp:298-303,11377-11380`。

## 有効になる条件

- 呼び出し側は `--serve` の layer split pipeline を必要とします。pipeline loop は `o.pipeline_windows > 0`、少なくとも2 stage、同一 GPU 上の split ではないこと、および stage 数が設定された数と一致することを条件に作られます。`--pipeline-windows 2` 自体は serve、複数 GPU の layer split、MTP drafter と `--spec` 2以上を必要とし、batch slots、peer device、helper cache 等との併用は無効化されます。
- この変数の参照箇所は `--pipeline-windows 2` loop 内です。加えて `pl_snap_ok` が必要です。通常の request がこの loop を使うには `pipe && pl_pw >= 2 && pl_snap_ok` が成立し、repetition penalty (`penalty_last_n`) または coupled draft sampling の request でないこと、キャンセルされておらず、まだ出力上限に達していないことが必要です。これらの理由で loop を使わない request は serial decode へ進み、この設定は効果を持ちません。
- 変数が ON でも、B が用意され、B の前 window 全体の受理見込み `B.p_on` が speculative gate `theta` 以上で、B 用 verifier が in-flight でなく、rollback が pending (`doomed`) でない場合だけ先行 stage します。`theta` は別の `STRATA_PIPELINE_THETA` debug tuning 値から取得され、既定は `0.2` です。
- CUDA と SYCL の両方に同じ判定と条件分岐があります。OS 固有の値判定、build macro による差、CLI 引数によるこの変数の上書きは実装にありません。debug tuning 群を有効にする `STRATA_PIPELINE_DEBUG` が必要です。

根拠: `src/program/generate.cpp:4988-5020,10005,16079-16099,16496-16500`; `sycl/src/program/generate.cpp:300-303,11377-11380,11504-11508`; pipeline の制約説明 `docs/MULTI_GPU.md:188-197`。

## 実行時の詳細

MTP chain から B が決まったとき、ON かつ上記 gate 条件を満たせば、実装は A の token 列から B より前に成立する PLE の直近2 token を作り、B 用 verifier の `prestage(B.T, B.tok, B.p, prev, err)` を呼びます。これは host 上で `pl_stage()` を実行し、入力を prestaged として記録します。後続の `pl_launch()` は window サイズ・position・token 列を照合し、PLE staging が有効なら直近 token 2個も照合します。一致すれば staging を再利用し、異なれば `pl_stage()` を launch 時にやり直します。従ってこの設定は B の入力 staging の時期を変え、token の推測や受理条件そのものは変更しません。

OFF の場合、`prestage()` 呼び出しを飛ばします。B の front stage が A の後ろで launch 可能になると `pl_launch()` が呼ばれ、通常の staging が launch 処理内で行われます。

先行 staging に失敗した場合は pipeline loop の `die(err)` に入り、stderr に `strata serve: pipelined decode: <error>`、stdout に `ERR <error>` を出して戻り値1で終了します。CUDA/SYCL とも、たとえば verifier が in-flight、window size 不正、または pipeline window 用に準備されていない場合に `prestage()` が失敗を返します。環境変数の値だけを理由にしたログはありません。

根拠: `src/program/generate.cpp:16492-16500,16529-16558,16166-16180`; `src/core/verify.cpp:4859-4867,4884-4890`; `sycl/src/program/generate.cpp:11500-11508,11526-11529`; `sycl/src/core/verify.cpp:3785-3793,3808-3815`。

## 根拠

- 候補名の全参照を `rg` で調べた結果、Strata ソースの直接参照は CUDA `src/program/generate.cpp:16365-16368` と SYCL `sycl/src/program/generate.cpp:11377-11380` の2箇所です。両方とも同じファイル内の `pipe_dbg_env()` を経由します。その他の出現は helper の説明コメントと環境変数候補一覧 `docs/envvars/000_envvers.md:1266` です。
- `pipe_dbg_env()` の debug gate は `src/program/generate.cpp:464-466` と `sycl/src/program/generate.cpp:300-302` にあります。対象変数の `atoi` 判定と静的 cache は前記の各 `pl_prestage` 初期化箇所にあります。
- `--pipeline-windows` の対応 backend・制約に関する説明は `docs/MULTI_GPU.md:188-197` にあります。同資料も `STRATA_PIPELINE_*` tuning/test 値は `STRATA_PIPELINE_DEBUG=1` のときだけ読むと説明しています。コード上は `1` 固定の比較ではなく、未設定・空文字・先頭 `0` 以外を gate 有効と判定します。
