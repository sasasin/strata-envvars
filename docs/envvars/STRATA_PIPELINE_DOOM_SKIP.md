# `STRATA_PIPELINE_DOOM_SKIP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

2 段以上のレイヤー分割で `--pipeline-windows 2` の serve デコードを行う際、採用されず先行ステージで実行中の投機ウィンドウ（コード上の `D`）について、残りの層を CPU expert pool に依頼せず処理するかを選ぶ。既定では残りを省略する。`STRATA_PIPELINE_DEBUG` が有効な状態でこの変数を `0` と評価できる値にすると、省略せず最後まで処理する。ウィンドウの結果は破棄され、後続では GDN snapshot を戻して正しいコミットを再実行するための処理であり、通常の採用ウィンドウの計算方法は変えない（`engine/src/program/generate.cpp:21944-21949,22388-22400`、SYCL は `engine/sycl/src/program/generate.cpp:11917-11922,12490-12498`）。

読み取り箇所は CUDA/HIP 系と SYCL 系の各 1 箇所で、いずれも `pipe_dbg_env` 経由。索引の候補名が実際に読まれていることを両実装で確認した（`engine/src/program/generate.cpp:684-687,21947`、`engine/sycl/src/program/generate.cpp:337-340,11920`）。

## 値と判定

`pipe_dbg_env` はまず `STRATA_PIPELINE_DEBUG` を確認し、未設定・空文字・先頭文字が `0` の場合は対象名の `getenv` を行わず `nullptr` を返す。それ以外は対象環境変数を `getenv` する。ゲートの判定値は関数内 `static` で初回に保存される。対象変数は helper の返値を `std::atoi` に渡し、未設定（またはデバッグゲートで隠された場合）は skip 有効、変換結果 0 は無効、それ以外は有効とする（`engine/src/program/generate.cpp:684-687,21947-21949`、SYCL は `engine/sycl/src/program/generate.cpp:337-340,11920-11922`）。

| `STRATA_PIPELINE_DEBUG` | 対象変数 | skip 判定 |
|---|---|---|
| 未設定、空文字、先頭が `0` | 任意（対象名は読まれない） | 有効（既定） |
| 設定され、先頭が `0` 以外 | 未設定 | 有効（既定） |
| 設定され、先頭が `0` 以外 | `0`、空文字、`0anything`、`true`、`false`、数字で始まらない文字列 | 無効（`atoi` が 0） |
| 設定され、先頭が `0` 以外 | `1`、`-1`、`2tail`、先頭空白の後に非 0 数字がある文字列 | 有効（`atoi` が非 0） |

`atoi` は文字列全体の真偽値比較ではなく、先頭の整数部分を変換する。先頭空白と符号は変換に含まれ、数字の後ろは判定に使われない。大文字小文字の区別や厳密な数値形式の検証、clamp はない。整数として変換できない文字列は 0 となる。表の `true` / `false` はいずれも数値で始まらないため無効。範囲外数値の変換結果は C の `atoi` の仕様上保証されない（`engine/src/program/generate.cpp:21947`、SYCL は `engine/sycl/src/program/generate.cpp:11920`）。

## 有効になる条件

- CUDA/HIP 実装では `pipe = o.pipeline_windows > 0 && n_stages >= 2 && !split_same && stages.size() == n_stages - 1`。SYCL 実装では `o.pipeline_windows > 0 && n_stages == 2 && !split_same && stages.size() == 1`（`engine/src/program/generate.cpp:13263-13268`、`engine/sycl/src/program/generate.cpp:7708-7713`）。
- デコード中の実行には `pipe` に加えて `--pipeline-windows` の値が 2 以上で、GDN snapshot が用意できている必要がある。満たさない場合はこの投機デコード分岐に入らない（`engine/src/program/generate.cpp:13724-13740,21810-21822`、SYCL は `engine/sycl/src/program/generate.cpp:11783-11795`）。
- repetition penalty（`hist_n > 0`）または coupled draft sampling のリクエストは直列デコードに戻る。キャンセル済み、または出力上限到達後も投機デコードを開始しない（`engine/src/program/generate.cpp:21811-21822`、SYCL は `engine/sycl/src/program/generate.cpp:11784-11795`）。
- `STRATA_PIPELINE_DEBUG` が有効であることは対象変数を読ませる条件だが、無効でも既定値の skip は有効になる。CLI 引数や別環境変数による対象値の上書きはない。`--pipeline-windows` はこの機能が走るパイプライン自体の条件。

## 実行時の詳細

`STRATA_PIPELINE_DEBUG` の有効判定は `pipe_dbg_env` の関数内 `static` に一度保存される。対象変数の `doom_skip` も `pump0` 内の関数内 `static` で一度評価される。従って両方ともプロセス内でキャッシュされ、起動後の環境変更は以後の判定に反映されない（`engine/src/program/generate.cpp:684-687,21941-21949`、SYCL は `engine/sycl/src/program/generate.cpp:337-340,11914-11922`）。

先行窓の判定が誤り、または停止処理で投機窓を取り消す場合、`doomed` が立ち、その窓は `D` として処理される。skip が有効なら `Verifier::service` に null pool を渡す。CUDA/HIP verifier は null pool 時に空の plan を発行して待機側を進め、SYCL verifier も同じく null pool の場合は pool 呼び出しをせず、plan 未発行を検出して空 plan を設定する（`engine/src/program/generate.cpp:22388-22400`、`engine/src/core/verify.cpp:6071-6093`、`engine/sycl/src/program/generate.cpp:12490-12501`、`engine/sycl/src/core/verify.cpp:4359-4393`）。省略した投機窓の処理完了後、GDN snapshot を復元して、元の窓の正しいコミット数で状態を再構成する（CUDA/HIP: `engine/src/program/generate.cpp:22169-22189`、SYCL: `engine/sycl/src/program/generate.cpp:12159-12183`）。

## ログと測定値

この変数自体を理由にしたログや測定値はない。通常の pipeline ログは別の `STRATA_PIPELINE_LOG` / `STRATA_DECODE_TIMING` による。省略対象の service や snapshot 復元が失敗した場合は通常の pipeline エラー経路に入り、CUDA/HIP は `strata serve: pipelined decode: ...` を stderr、`ERR ...` を stdout に出して 1 を返す（`engine/src/program/generate.cpp:21917-21928`）。SYCL 側も stderr に同じ prefix、stdout に `ERR ...` を出す（`engine/sycl/src/program/generate.cpp:11894-11901`）。

`docs/DETAILS.md` にこの変数固有の説明や測定結果は見当たらないため、性能・正確性の数値は記載しない。

## 根拠

- `engine/src/program/generate.cpp:681-687,13263-13268,13724-13740,21802-21822,21917-21928,21941-21955,22169-22189,22388-22400`
- `engine/sycl/src/program/generate.cpp:325-340,7708-7713,11775-11795,11894-11928,12159-12183,12490-12501`
- `engine/src/core/verify.cpp:6071-6097`
- `engine/sycl/src/core/verify.cpp:4359-4402`
