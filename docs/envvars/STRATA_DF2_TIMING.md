# `STRATA_DF2_TIMING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

DFlash2 の診断用 timing スイッチ。CUDA/HIP では drafter の各 draft round に GPU event を記録して GPU 時間を集計する。SYCL の `serve` では、DFlash2 の prompt context 更新と request 終了時の context 更新にかかった wall-clock 時間を stderr に出す。一方、SYCL drafter 内にもこの変数を読むコードがあるが、その値を保持する `timing_` は現行 checkout で一度も参照されず、そこから計測や出力は発生しない。いずれの読み取りも draft の選択、生成内容、判定値を変える分岐ではない（`engine/src/core/dflash2.cpp:296-301,1197-1235`; `engine/sycl/src/core/dflash2.cpp:161`; `engine/sycl/include/strata/core/dflash2.hpp:187`; `engine/sycl/src/program/generate.cpp:7907-7914,12914-12918`）。

## 値と判定

| 読み取り箇所・条件 | 未設定 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP DFlash2 `make_streams()` | `timing_` は `false` | 値の先頭 byte が ASCII `1`。例: `1`, `10`, `1anything` | 空文字、`0`, `true`, `false`, ` 1` など先頭が `1` でない値 |
| SYCL drafter `load()` 内のフラグ | `timing_` は `false` | 上と同じ先頭 byte `1` | 上と同じ。ただし、この `timing_` は現行コードで未使用 |
| SYCL `serve` の prompt / request-end timing | `getenv(...) != nullptr` が偽 | 値の内容を問わず、環境変数が存在すれば有効。空文字、`0`, `false` も有効 | 未設定のみ |

文字列全体の parse、数値変換、大文字小文字変換、空白除去はありません。CUDA/HIP と SYCL drafter は先頭 byte だけを比較しますが、SYCL `serve` の二箇所は設定有無だけを見ます。そのため、`STRATA_DF2_TIMING=0` は CUDA/HIP と SYCL drafter のフラグを有効にせず、SYCL `serve` の timing 出力は有効にします（`engine/src/core/dflash2.cpp:297-301`; `engine/sycl/src/core/dflash2.cpp:161`; `engine/sycl/src/program/generate.cpp:7909,12917`）。

## 有効になる条件

- CUDA/HIP 側の計測には、DFlash2 がビルドに含まれ（`STRATA_HAVE_DFLASH2`）、実行経路で DFlash2 drafter がロードされる必要がある。`--draft dflash2` の開始条件には `--draft-model PACK`、`--spec 2` 以上、および `--mtp DIR` または `--mtp-draft-vocab FILE` がある。条件不成立やロード失敗は起動エラーまたは fallback の分岐になり、timing 変数が DFlash2 を有効化することはない（`engine/src/program/generate.cpp:6505-6508,8151-8159,8309-8326`）。
- CUDA/HIP では最初の drafter の `load()` が `make_streams()` を呼び、batch slot 用の各 drafter も `clone_alloc()` から個別に `make_streams()` を呼ぶ。従って、各オブジェクト生成時に環境値を読み、その個体の draft round 計測を決める（`engine/src/core/dflash2.cpp:187,267,271-302,658-667`）。
- SYCL の `serve` 側のログは `use_df2` の DFlash2 経路に限られる。prompt 行の callback は `STRATA_DF2_NO_PROMPT_CTX` が設定されていると先に return するため、prompt context 更新もその timing 行もありません。request-end の更新ログは別の箇所で、DFlash2 が有効で EOS または `max_new` 到達時に context 更新が成功すると出ます（`engine/sycl/src/program/generate.cpp:7892-7903,7907-7914,12914-12918`）。
- CLI 引数や他の環境変数による `STRATA_DF2_TIMING` 自体の上書き・優先順位はありません。`STRATA_DF2_NO_PROMPT_CTX` は SYCL prompt callback だけに影響します。

## 実行時の詳細

CUDA/HIP は `make_streams()` が環境値を読み、先頭が `1` のときだけ計測用 CUDA event を作成します。`draft_launch()` は DFlash2 のグラフを stream に積む直前と直後に event を記録し、`draft_finish()` が stream 完了後に event 間の GPU 時間を `ms_gpu` に加算します。wall-clock の `ms_draft` は別に常時積算されます。event 作成・記録の戻り値は失敗判定に使わず、`cudaEventElapsedTime()` が成功した場合だけ `ms_gpu` に加算します。したがって、この環境変数により draft の成否や token は変わらず、計測値が得られない場合も環境変数を理由に終了・警告する経路はありません（`engine/src/core/dflash2.cpp:296-301,1174-1215,1218-1240`）。

通常の CUDA/HIP generate の集計行は DFlash2 の round が 1 回以上あれば `stdout` に出て、GPU 平均を表示します。これは timing 変数の値にかかわらず表示されるコードであり、無効時の `ms_gpu` は加算されません（`engine/src/program/generate.cpp:25367-25370`）。

SYCL drafter の `load()` は先頭が `1` なら `timing_` を true にしますが、現行 checkout では `engine/sycl` 配下に `timing_` の読み取り箇所がなく、このフラグによる実行時効果は確認できません（`engine/sycl/src/core/dflash2.cpp:161`; `engine/sycl/include/strata/core/dflash2.hpp:187`）。

SYCL `serve` のログ用 bool はそれぞれ関数内 `static` です。prompt callback の初回呼び出し時と、request-end context 更新に初めて入った時に設定有無を読み、そのプロセス内で cache します。後から環境値を変えても各 bool には反映されません。prompt callback は更新を試した後に結果にかかわらず時間行を出してから `ok` を返します。request-end は context 更新が失敗すると `ERR %s` を stdout に出して return するため、その場合は timing 行を出しません（`engine/sycl/src/program/generate.cpp:7907-7914,12914-12918`）。

## ログと測定値

SYCL `serve` では以下の実装文字列を stderr に出します。prompt の行は callback 1 回ごとの処理で、`rows` と `pos0` を含みます。

- `strata serve: DFlash2: prompt context update, %lld rows at %lld, %.1f ms`（`STRATA_DF2_TIMING` が設定され、かつ `STRATA_DF2_NO_PROMPT_CTX` が未設定の場合）。
- `strata serve: DFlash2: the request-end context update (%d rows) took %.1f ms`（設定があり、request-end context 更新に成功した場合）。
- request-end context 更新に失敗した場合は `ERR %s` を stdout に出して終了コード `1` で戻り、上記 request-end timing 行は出ません。

CUDA/HIP の通常 generate 集計行は `dflash2`、draft 平均、round 数、GPU 平均、VRAM を表示します。これは環境変数を有効にした時だけのログではありません。対象変数について Strata 資料に条件付き測定値は見つかりませんでした（`engine/src/program/generate.cpp:25367-25370`）。

## 根拠

- `engine/src/core/dflash2.cpp:271-302,658-667,1174-1240` — CUDA/HIP の読み取り、event の記録・集計、および複製 drafter の初期化。
- `engine/include/strata/core/dflash2.hpp:276-277` — CUDA/HIP event とフラグ。
- `engine/sycl/src/core/dflash2.cpp:161`、`engine/sycl/include/strata/core/dflash2.hpp:187` — SYCL drafter の読み取りと未使用フラグ。
- `engine/sycl/src/program/generate.cpp:7905-7916,12914-12918` — SYCL `serve` の設定有無判定、prompt / request-end timing 行と失敗経路。
- `engine/src/program/generate.cpp:6505-6508,8151-8159,25367-25370` — DFlash2 の起動条件、ビルド条件、および CUDA/HIP の集計表示。
