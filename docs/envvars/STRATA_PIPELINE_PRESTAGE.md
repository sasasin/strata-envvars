# `STRATA_PIPELINE_PRESTAGE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`--pipeline-windows` の speculative window `B` について、B を実際に launch する前に verifier の入力と PLE 行を準備（prestage）するかを切り替えるデバッグ・調整用変数。既定では準備を先行させる。`STRATA_PIPELINE_PRESTAGE=0` にすると、chain から B が作られた時点の先行準備を省き、後段の B launch 時に通常の準備処理を行う。

## 値と判定

値の取得は `pipe_dbg_env("STRATA_PIPELINE_PRESTAGE")` 経由で行われる。これは `STRATA_PIPELINE_DEBUG` が設定され、空でなく、先頭文字が `0` でない場合に限り、指定名の `getenv` 結果を返す。それ以外では `nullptr` を返す（`src/program/generate.cpp:343-346`、同じ実装が `sycl/src/program/generate.cpp:298-301` にある）。

| 状態 | `pl_prestage` の値 |
|---|---|
| `STRATA_PIPELINE_DEBUG` が有効でなく、この変数が helper から見えない | `true`（既定） |
| debug が有効で、この変数が未設定 | `true` |
| debug が有効で、値の `atoi` 結果が `0` | `false` |
| debug が有効で、値の `atoi` 結果が非 `0` | `true` |

判定は `std::atoi(v) != 0` であり、文字列全体の数値検証はしない。したがって空文字や数値に変換できない文字列は 0 扱い、数値の後ろに文字が続く値は先頭の数値部分で判定される。`STRATA_PIPELINE_DEBUG` 自体も `=1` との完全一致ではなく、設定有無・空文字・先頭文字で判定する。

## 有効になる条件

- `--pipeline-windows` が有効になり、生成処理がそのパイプライン decode ループに入る必要がある。オプションの対応条件と、未対応時に無効化する分岐は `src/program/generate.cpp:4188-4240` にある。
- 本変数を明示して既定を変えるには `STRATA_PIPELINE_DEBUG` も有効である必要がある。debug が無効なら `pipe_dbg_env` は本変数を隠し、値に関係なく既定の `true` になる。
- CUDA 実装と SYCL 実装の双方で同じ判定と効果を持つ。参照位置は `src/program/generate.cpp:14353-14356,14484-14488` および `sycl/src/program/generate.cpp:11102-11105,11229-11233`。

## 実行時の詳細

パイプライン内で B の chain 出力が揃い、B が ready になった後、`pl_prestage` が true で、B の確率ゲート `B.p_on >= theta` を満たし、B の verifier が in-flight でなく、rollback 対象でもない場合に `Verifier::prestage` を呼ぶ。A の tokens を反映した PLE の前状態を計算し、B の tokens・位置とともに渡す（CUDA: `src/program/generate.cpp:14480-14488`、SYCL: `sycl/src/program/generate.cpp:11225-11233`）。

`Verifier::prestage` は verifier が実行中でないこと、window サイズが範囲内であること、capture 済みの pipelined window であることを確認し、`pl_stage` を呼んで準備済み状態を記録する（CUDA: `src/core/verify.cpp:4060-4069`、SYCL: `sycl/src/core/verify.cpp:3654-3663`）。その後の `pl_launch` はサイズ・位置・tokens・必要な PLE 前状態が一致すれば準備済みデータを再利用し、一致しない場合は launch 時に `pl_stage` を実行してから graph を launch する（CUDA: `src/core/verify.cpp:4082-4102`、SYCL: `sycl/src/core/verify.cpp:3677-3695`）。よって `0` は B の実行自体を止めず、先行準備を省く値である。

本変数の値は関数内 `static const bool pl_prestage` に格納され、初めて該当行に到達した時に一度評価される。そのプロセス内では後から環境を変更しても再評価されない。helper 内の `STRATA_PIPELINE_DEBUG` 判定も `static` であり、最初の helper 呼び出し時に一度評価される（CUDA: `src/program/generate.cpp:343-346,14353-14356`、SYCL: `sycl/src/program/generate.cpp:298-301,11102-11105`）。この変数専用のログ出力は見つからなかった。`prestage` の検査失敗時は verifier がエラー文字列を設定し、呼び出し側がパイプライン処理をエラー終了させる。

## 根拠

- `src/program/generate.cpp:340-346,14353-14356,14480-14488,14517-14548` — CUDA 側のデバッグ gate、値の判定、prestage と通常 launch の流れ。
- `sycl/src/program/generate.cpp:298-301,11102-11105,11225-11233,11264-11288` — SYCL 側の対応箇所。
- `src/core/verify.cpp:4060-4102`、`sycl/src/core/verify.cpp:3654-3695` — 入力準備、準備状態の再利用、graph launch。
- `docs/MULTI_GPU.md:427-499` — `--pipeline-windows` の利用条件、動作説明、`STRATA_PIPELINE_*` 調整変数が `STRATA_PIPELINE_DEBUG=1` の下で読まれる旨。文書の「`=1`」表記より具体的な判定はソースに従った。
