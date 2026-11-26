# `STRATA_PIPELINE_AGREE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数 GPU の layer split で動く `--pipeline-windows` の speculative 次ウィンドウについて、直前の window を全採用できる確率の推定方法を切り替える。既定（有効）では、強制 chain が前 window の draft token と一致するかを確認し、chain が出した各 token の確率を積算する。不一致なら全採用確率を 0 として、次の speculative window の `p_on` と gate 判定に使う。無効にすると、draft 時に保存した `A.prob` の積を使う。これは先読み window を起動するかどうかの推定に関わる設定であり、前 window の実際の採用 token は verifier 出力との token 一致で決まる。CUDA/HIP 側では `engine/src/program/generate.cpp`、SYCL 側では `engine/sycl/src/program/generate.cpp` の pipeline decode loop にある。(`engine/src/program/generate.cpp:22242-22259`, `engine/src/program/generate.cpp:21968-21982`, `engine/sycl/src/program/generate.cpp:12289-12310`, `engine/src/program/generate.cpp:22378-22380`, `engine/src/program/generate.cpp:22430-22433`)

## 値と判定

対象値は `pipe_dbg_env("STRATA_PIPELINE_AGREE")` で取得し、返された文字列に `std::atoi` を適用して 0 かどうかを判定する。`pipe_dbg_env` は `STRATA_PIPELINE_DEBUG` が設定され、先頭文字が空でなく `'0'` でもないときだけ対象名を `getenv` する。debug gate が無効なら対象値は未設定相当となる。(`engine/src/program/generate.cpp:681-687`, `engine/sycl/src/program/generate.cpp:325-339`, `engine/src/program/generate.cpp:22124-22127`, `engine/sycl/src/program/generate.cpp:12128-12131`)

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| engine 側（CUDA/HIP の pipeline 実装） | helper が nullptr を返し、有効 | `1`, `-1`, `1tail`（`atoi` が 0 以外を返す文字列） | `0`, `0tail`, 空文字, `true`（`atoi` が 0 を返す） |
| SYCL pipeline 実装 | helper が nullptr を返し、有効 | `1`, `-1`, `1tail` | `0`, `0tail`, 空文字, `true` |
| どちらも `STRATA_PIPELINE_DEBUG` が無効 | helper が nullptr を返すため有効（既定値） | 対象値は読まれない | 対象値は読まれない |

`atoi` は文字列全体の厳密な数値検証ではなく、先頭の空白と符号の後にある数値部分を変換し、後続文字を検査しない。従って ` 1tail` は有効、`false` や数値に変換できない文字列は無効になる。大文字小文字は値判定に関与しない。明示的な空文字は `atoi("") == 0` となり無効。`STRATA_PIPELINE_DEBUG` の空文字および `0...` は gate を無効にする一方、`false` や先頭が空白の値は gate を有効にする。いずれの無効値にも専用の警告・fallback ログはない。(`engine/src/program/generate.cpp:684-687`, `engine/src/program/generate.cpp:22124-22127`)

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が有効であること。debug gate が無効なら `STRATA_PIPELINE_AGREE` 自体を読み取らず、既定の有効扱いになる。(`engine/src/program/generate.cpp:681-687`)
- `--pipeline-windows` が有効な pipeline decode 経路に入ること。engine 側の pipeline は複数 stage の layer split で使われ、SYCL 側は 2 stage の split で使われる。pipeline の有効化には `--serve`、複数 GPU に分かれた split、MTP drafter と `--spec` など backend ごとの条件があり、条件不成立時は pipeline が無効化される。(`engine/src/program/generate.cpp:6560-6601`, `engine/src/program/generate.cpp:13256-13268`, `engine/sycl/src/program/generate.cpp:3587-3629`, `engine/sycl/src/program/generate.cpp:7707-7713`)
- 変数は CLI 引数で上書きされない。`--pipeline-windows` は pipeline の有効・無効を選ぶが、この推定方法の設定は `STRATA_PIPELINE_DEBUG` gate と本変数で決まる。(`engine/src/program/generate.cpp:4119`, `engine/src/program/generate.cpp:22124-22127`)
- SYCL では `STRATA_PRIVATE_MTP_DEMAND=1` のとき private demand 機能を開始する条件にも `pl_agree` が含まれる。従って `STRATA_PIPELINE_DEBUG=1` かつ `STRATA_PIPELINE_AGREE=0`（または `atoi` が 0 となる値）なら、その private demand 開始条件を満たさない。CUDA/HIP 側にはこの連携コードがない。(`engine/sycl/src/program/generate.cpp:12128-12135`)

## 実行時の詳細

両実装とも対象値の判定は block-scope `static const bool pl_agree` で一度だけ初期化され、同プロセス内の後続 request ではキャッシュ値を使う。helper の `STRATA_PIPELINE_DEBUG` 判定も `static` で一度だけキャッシュされる。初回評価後に環境を書き換えても反映されない。(`engine/src/program/generate.cpp:684-687`, `engine/src/program/generate.cpp:22124-22127`, `engine/sycl/src/program/generate.cpp:337-340`, `engine/sycl/src/program/generate.cpp:12128-12131`)

chain kind 1（A の draft を強制した chain）で、A 全体の採用確率を推定する際に、enabled なら chain の各出力 `oc[i]` と draft token `A.tok[i+1]` の一致を調べ、`op[i]` を確率積に使う。不一致が一つでもあると推定値を 0 にする。disabled なら一致を条件にせず、代わりに保存済みの `A.prob[i]` を積算する。chain kind 2 ではいずれの設定でも `A.prob` の積算である。得られた推定値は次 window の `B.p_on`（さらに bonus token の確率を掛けた値）になり、theta または hit-rate gate の判定材料となる。従ってこの変数は先読み window の推定・起動判断や rollback の発生に影響し得るが、verifier が比較する実 token 一致条件を書き換えない。(`engine/src/program/generate.cpp:22240-22259`, `engine/src/program/generate.cpp:21968-21982`, `engine/src/program/generate.cpp:22288-22295`, `engine/src/program/generate.cpp:22378-22380`, `engine/src/program/generate.cpp:22430-22433`, `engine/sycl/src/program/generate.cpp:12289-12319`)

値を読めても、pipeline が起動していない実行では効果はない。プロセス間の継承や環境値の設定・転送を行うコードはこの変数の参照経路にはない。

## ログと測定値

この変数を読み取ったことを示す専用ログや無効値の警告はない。pipeline timing が出力されるときは、forced-chain disagreement の件数が `strata pipeline classes: ... | forced-chain disagreements %lld, chain late %lld` の行に含まれる。engine 側では chain 不一致時の推定値を 0 に直した回数を数える。SYCL 側では `pl_agree` が有効な状態で chain と draft が不一致だった回数を数える。(`engine/src/program/generate.cpp:22288-22290`, `engine/src/program/generate.cpp:22595-22599`, `engine/sycl/src/program/generate.cpp:12301-12306`, `engine/sycl/src/program/generate.cpp:12627-12637`)

`docs/MULTI_GPU.md:182-203` の pipeline 説明は speculative window の仕組みと `STRATA_PIPELINE_DEBUG=1` の gate を記載しており、今回確認したコードと矛盾しない。`STRATA_PIPELINE_AGREE` の効果に関する測定値は同資料にないため記載しない。

## 根拠

- `engine/src/program/generate.cpp:681-687` — pipeline debug helper と gate の値判定。
- `engine/src/program/generate.cpp:6560-6601`, `engine/src/program/generate.cpp:13256-13268` — pipeline が使われる条件と実行経路。
- `engine/src/program/generate.cpp:21968-21982`, `engine/src/program/generate.cpp:22120-22127`, `engine/src/program/generate.cpp:22240-22259` — 値の cache、chain/draft の比較、確率推定と B の gate 値。
- `engine/src/program/generate.cpp:22288-22295`, `engine/src/program/generate.cpp:22595-22599` — mismatch counter と観測ログ。
- `engine/sycl/src/program/generate.cpp:337-340`, `engine/sycl/src/program/generate.cpp:3587-3629`, `engine/sycl/src/program/generate.cpp:7707-7713`, `engine/sycl/src/program/generate.cpp:12124-12135`, `engine/sycl/src/program/generate.cpp:12289-12319`, `engine/sycl/src/program/generate.cpp:12627-12637` — SYCL 側の同等実装、pipeline 条件、private demand との連携、観測ログ。
- `docs/MULTI_GPU.md:182-203` — Strata の pipeline 説明と debug gate の照合。
