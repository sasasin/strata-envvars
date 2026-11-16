# `STRATA_PRIVATE_MTP_DEMAND_MICRO`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は SYCL のパイプラインデコードで private demand MTP が有効なとき、追加検証とホスト継続のマイクロベンチマークを実行する chain の序数を指定する。値はオン・オフではなく `atoi` で読まれる chain 番号である。指定 chain の完全実行と分割実行を追加で行い、token/probability の一致を調べた後、3 種類の arm の時間を stderr に出す。通常の MTP 計算の単なるログ出力ではなく、選択した chain を再実行する診断・測定フックである（`sycl/src/program/generate.cpp:12150-12218`）。

この名前の参照は、状態初期化で設定有無を確認する箇所と、pipeline 処理後に値を数値変換する箇所の 2 箇所である。後者がベンチマーク実行を選び、前者は計時カウンターも有効にする（`sycl/include/private_mtp_demand.hpp:27-30`、`sycl/src/program/generate.cpp:12153-12155`）。

## 値と判定

pipeline 処理の終わりで `std::getenv` が返す文字列を `std::atoi` に渡し、private demand state の `ordinal` と整数比較する。文字列全体の妥当性、末尾文字、範囲は検証しない。空文字や数字で始まらない文字列は `atoi` の結果が 0 となり、通常 1 から始まる序数には一致しない。先頭の符号・空白と初期の数字列は `atoi` の規則で解釈される（`sycl/src/program/generate.cpp:12153-12155`、序数の更新は `sycl/include/private_mtp_demand.hpp:27-30`）。

| 条件 | 未設定 | 一致してベンチマークを選ぶ値 | 一致しない例 |
|---|---|---|---|
| SYCL pipeline、private demand が有効 | ベンチマークなし | 実行中 thread-local state の 1 始まりの `ordinal`。例: 2 番目なら `2`、`2junk` も `atoi` 結果 2 | 空文字、`0`、`0anything`、`true`、`junk`、負数、処理済み序数より大きい値 |
| 上記以外、または前提を満たさない | ベンチマークなし | なし | 設定値にかかわらず実行されない |

`STRATA_PRIVATE_MTP_DEMAND_MICRO` が空文字を含め設定されていれば、状態初期化では `metrics` も有効になる。ただし空文字はベンチマーク序数としては 0 になる。比較は大文字小文字を使わない文字列判定ではなく整数変換であり、`true` / `false` は特別扱いされない（`sycl/include/private_mtp_demand.hpp:27-30`、`sycl/src/program/generate.cpp:12153-12155`）。

## 有効になる条件

- ビルドが SYCL エンジンであること。トップレベル CMake の `STRATA_ENABLE_SYCL` は既定 OFF で、ON の場合に別プロジェクト `sycl/` を追加する（`CMakeLists.txt:23-32`）。CUDA/HIP と同時に有効化すると構成エラーになる（同 `:26-29`）。
- 対象の `strata serve` 実行で `--pipeline-windows 2` 相当の decode が実際に走ること。コード上の `pl_want` は `pipe`、`pl_pw >= 2`、snapshot buffer を要求し、条件外の要求（repetition penalty 使用中、または coupled draft sampling）も serial に戻るため、この測定箇所に到達しない（`sycl/src/program/generate.cpp:738-743,11385-11396`）。
- private demand state が一致時点で直前 chain の入力と出力数を保持していること。通常の chain を取得できなければ、この環境変数で有効な測定対象はない（`sycl/src/program/generate.cpp:12150-12163`）。
- `STRATA_PRIVATE_MTP_DEMAND` も設定され、その先頭文字が `'1'` であること。さらに `pl_agree` が true で `force_miss == 0` でなければ private demand state 自体が有効にならず、この変数はベンチマークを起動できない（`sycl/src/program/generate.cpp:11725-11736`）。
- `pl_agree` は既定 true。`STRATA_PIPELINE_DEBUG` が有効な場合に `STRATA_PIPELINE_AGREE` が `atoi` で 0 になると false になる。`force_miss` は debug 設定または pipeline switch ファイルから設定され得る（`sycl/src/program/generate.cpp:326-329,10754-10778,11729-11736`）。
- 比較対象の `ordinal` は有効な `begin(..., true)` ごとに 1 増える。値が 0、負、まだ到達していない番号、あるいはそのスレッドで既に通過した番号なら一致しない（`sycl/include/private_mtp_demand.hpp:23-30`）。
- `STRATA_PRIVATE_MTP_DEMAND_LOG` は必須ではない。`MICRO` 自体の設定有無で計時カウンターが有効になる。`STRATA_PRIVATE_MTP_DEMAND_LOG` がある場合は、別途詳細 chain ログの有効条件にもなる（`sycl/include/private_mtp_demand.hpp:30`、`sycl/src/program/generate.cpp:11862-11868`）。

## 実行時の詳細

pipeline の private demand state はスレッドローカルであり、初期化時に `MICRO` の設定有無を読んで計時を有効にする。ベンチマーク選択文字列は pipeline 処理の drain 後に `getenv` で読むため、関数内 static に保存されない。序数は state の再初期化をまたいで維持され、有効な demand begin ごとに加算される（`sycl/include/private_mtp_demand.hpp:23-30`、`sycl/src/program/generate.cpp:11735-11736,12121-12155,12220-12224`）。

指定序数が一致すると、直前の実 chain の入力状態（T、位置、入力 token、force 情報、出力数）を保存する。まず完全 chain を基準に実行し、続いて各出力 prefix 長 `k=1..outputs` について「分割 chain、完全 chain」の組を実行する。各試行で token と probability の prefix を比較し、不一致ならエラー経路に入る。成功時には `STRATA_DEMAND_MICRO_FIXTURE` を出力する。その後、同じ完全 GPU work を通常 arm、分割 arm、通常 arm の順に各 3 sample 実行する。各 sample は warm-up が 1000 回かつ 2 秒以上、測定が 2000 回かつ 3 秒以上になるまで続き、平均時間を出力する。追加 GPU work のため、選択した要求の処理時間が延びる（`sycl/src/program/generate.cpp:12156-12218`）。

ベンチマーク後は private demand state と `mtp.ms_draft`、`mtp.rounds` を保存値へ戻してから通常の集計・後続処理へ進む（`sycl/src/program/generate.cpp:12156-12159,12217-12225`）。コードはこの再実行箇所にモデルや device allocation を行わない旨を記しているが、ここでは性能値や他の外部状態への影響を独自に測定していない。

## ログと測定値

成功時の stderr 出力は次の形式である。

- `STRATA_DEMAND_MICRO_FIXTURE {"T":...,"p":...,"a":...,"n_force":...,"n_out":...,"all_prefixes_equal":true,"next_chain_equal":true}`。prefix 比較のループを通過した後に出力される（`sycl/src/program/generate.cpp:12179-12195`）。
- `STRATA_DEMAND_MICRO_SAMPLE {"arm":...,"sample":...,"warm_iterations":...,"iterations":...,"mean_us":...}`。各 sample の測定後に stderr を flush する（同 `:12198-12215`）。
- `STRATA_MTP_DEMAND chains=... requested=... actual=... continuations=... dead_B=... reaction_ns=... submit_ns=... max_reaction_ns=...`。有効 state があると出力される（同 `:12220-12223`）。

prefix 不一致時はエラー文字列 `private demand micro: token/probability prefix differs` を設定して `die(err)` に進む。一般の pipeline エラー経路では stderr に `strata serve: pipelined decode: ...`、stdout に `ERR ...` を出して戻り値 1 を返す（`sycl/src/program/generate.cpp:12182-12189,11494-11503`）。ソースに掲載された既定性能値はないため、測定結果は実行ログごとの値として扱う。

SYCL serve wrapper `sycl/serve/strata-sycl.sh` は設定環境変数をコンテナへ転送する際、値が空または文字列 `0` の変数を転送対象から除外する（`sycl/serve/strata-sycl.sh:33-42`）。これは wrapper 経由の起動に限る。エンジンの直接実行では空文字も `getenv` で設定済みとして扱われ、計時フラグを立てるが、序数比較では一致しない。

## 根拠

- 候補名の実装参照: `sycl/include/private_mtp_demand.hpp:27-30`、`sycl/src/program/generate.cpp:12153-12155`。
- SYCL backend の分離と既定 OFF: `CMakeLists.txt:23-32`。
- pipeline demand state の条件: `sycl/src/program/generate.cpp:11396-11400,11725-11736`。
- chain 再実行、比較、反復測定: `sycl/src/program/generate.cpp:12156-12218`。
