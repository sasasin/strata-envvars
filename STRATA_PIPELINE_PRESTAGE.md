# `STRATA_PIPELINE_PRESTAGE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`--pipeline-windows 2` の decode loop で、次の推測 window B の入力を verifier に事前設定するかを制御します。有効なら、MTP drafter の chain から B が確定した時点で `Verifier::prestage()` を呼びます。これは B の GPU window を早く実行する指定ではなく、window の入力準備を先に行う指定です。無効なら、この時点での事前設定を省き、B の `pl_launch()` 時に通常の入力設定を行います。

## 値と判定

この値は `std::atoi()` で変換し、結果が 0 かどうかで判定します。文字列全体の妥当性検査はありません。

| 状態 | `STRATA_PIPELINE_DEBUG` が有効な場合の結果 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 無効（`atoi("")` は 0） |
| `0`、`0abc`、`false`、数値に変換できない文字列 | 無効（変換結果が 0） |
| `1`、`1abc`、`-1`、その他 0 以外に変換される文字列 | 有効 |

`std::atoi()` は先頭の空白や符号を受け付け、数値部分の後ろは判定に使いません。したがって、たとえば `1abc` は有効、`false` は無効です。

ただし `STRATA_PIPELINE_DEBUG` が無効なら、ヘルパーは対象変数を読まず `nullptr` を返します。この場合、`STRATA_PIPELINE_PRESTAGE` が設定されていても実質的に未設定扱いとなり、既定の有効になります。デバッグ gate は未設定・空文字・先頭が `0` の値で無効、それ以外で有効です。

## 有効になる条件

- パイプライン decode が選択されること。コード上は `--serve`、互いに異なる GPU に分けた layer split、MTP drafter と `--spec >= 2` が必要です。
- この事前設定箇所は `--pipeline-windows 2` の decode loop にあります。`--pipeline-windows 1` は短い prompt read 用です。
- `--pipeline-windows` は batch slots、peer-device、helper cache と併用できず、これらの条件では要求しても無効化されます。自動選択も別条件に従います。NVIDIA build では自動選択されず、明示的な指定が必要です。
- さらに B が作成済みで、`B.p_on >= theta`、B の verifier が実行中でなく、rollback (`doomed`) 中でない場合に限り `prestage()` が呼ばれます。値を有効にしてもこの条件に合わない B は事前設定されません。

Strata の `docs/MULTI_GPU.md` は `--pipeline-windows 2` が推測 window を先行させる仕組みと適用条件を説明していますが、この環境変数固有の記載や性能測定値は確認できませんでした。

## 実行時の詳細

CUDA/HIP 系 `src/program/generate.cpp` と SYCL 系 `sycl/src/program/generate.cpp` の双方に直接参照があります。両方とも `pipe_dbg_env()` を使用し、`STRATA_PIPELINE_DEBUG` の判定結果を関数内の `static const bool` に保存します。個別の `STRATA_PIPELINE_PRESTAGE` 判定も `static const bool` のため、一度評価された後のプロセス内環境変更は反映されません。

有効時、chain から B が決まった箇所で、現在の PLE 履歴と A の token を反映した `prev` を作り、B の token・長さ・位置とともに `Verifier::prestage()` に渡します。`prestage()` は verifier が実行中でないこと、window 長が有効範囲内であること、pipelined window の準備が済んでいることを確認し、`pl_stage()` を実行して事前設定済みフラグを立てます。検査に失敗した場合、decode loop はエラーとして終了します。

後の `pl_launch()` は、事前設定された長さ・位置・token が launch 対象と一致するか確認します。PLE staging が有効なときは PLE 履歴も照合します。一致すれば再利用し、不一致なら `pl_stage()` を改めて実行します。従って、この環境変数が直接変えるのは入力準備の時点であり、事前設定の不一致をそのまま使う挙動ではありません。専用ログはありません。

## 根拠

- `src/program/generate.cpp:251-257` — `STRATA_PIPELINE_DEBUG` gate と共通 helper。
- `src/program/generate.cpp:3391-3431` — `--pipeline-windows` の選択条件・併用制約。
- `src/program/generate.cpp:11591-11594,11718-11727` — 値の判定と B の事前設定呼び出し。
- `src/program/generate.cpp:11748-11785` — B の通常 launch 経路。
- `src/core/verify.cpp:3231-3239,3242-3261` — 事前設定と launch 時の再利用条件。
- `sycl/src/program/generate.cpp:293-298,10822-10825,10945-10954` および `sycl/src/core/verify.cpp:3630-3638,3641-3660` — SYCL 系の対応実装。
- `docs/MULTI_GPU.md:246-267` — パイプライン window の概要と文書化された適用範囲。
