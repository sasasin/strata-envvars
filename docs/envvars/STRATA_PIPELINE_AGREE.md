# `STRATA_PIPELINE_AGREE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`--pipeline-windows` の speculative decode で、先行 window `A` の drafter 予測が chain の出力と一致するかを、次 window `B` の開始確率 `p_on` に反映するかを切り替えます。環境変数は CUDA 系の `src/program/generate.cpp` と SYCL 系の `sycl/src/program/generate.cpp` の両方にあります。通常の serial decode や pipeline 経路を使わないリクエストでは、この設定による差はありません。

## 値と判定

`pipe_dbg_env()` が返す値に対して `std::atoi()` を使い、結果が 0 かどうかだけで判定します。文字列全体の検証はなく、`atoi` の規則に従って先頭の空白・符号・数字列を変換し、数字列の後ろは無視します。数値として読めない文字列と空文字は 0、負数を含む非 0 の数値は有効です。

| 状況 | `pl_agree` | 処理 |
|---|---:|---|
| `STRATA_PIPELINE_DEBUG` が有効で、この変数が未設定 | `true`（既定） | chain 確率と元の draft 確率の不一致を調べ、不一致なら `p_on=0` にする |
| debug が有効で、値の `atoi()` が 0 | `false` | chain 確率を使わず、元の draft 確率だけを使う。不一致による `p_on=0` 化もしない |
| debug が有効で、値の `atoi()` が非 0 | `true` | 一致判定を有効にする |
| `STRATA_PIPELINE_DEBUG` が未設定、空文字、または先頭文字が `0` | `true`（既定） | `pipe_dbg_env()` が対象値を読まず `nullptr` を返すため、上と同じ既定動作 |

したがって `STRATA_PIPELINE_AGREE=0` が無効化するには `STRATA_PIPELINE_DEBUG` も有効である必要があります。debug helper の有効判定は `v != nullptr && v[0] != 0 && v[0] != '0'` で、たとえば空文字と `0anything` は無効、`1`・`true`・`false` は有効です。debug helper の結果は最初の呼び出し時に `static const bool` へ cache され、`pl_agree` も pipeline decode 本体の初回実行時に cache されます。以後プロセス内で環境を変更しても再評価されません。

## 有効になる条件

- pipeline windows が選択され、リクエストが speculative pipeline decode 本体に入る必要があります。文書化された構成は `--serve` と複数 GPU の layer split、MTP drafter、`--spec` 2 以上などを要し、NVIDIA build では `--pipeline-windows 2` が opt-in です。環境変数だけで pipeline を開始する機能ではありません。
- `--batch` slots、`--peer-device`、helper cache、draft layer の欠如など pipeline 自体を止める条件があります。repetition penalty や coupled draft sampling を含むリクエストは serial decode になります。
- `STRATA_PIPELINE_DEBUG` は tuning/test 変数へのアクセス gate です。debug gate が無効でも pipeline 本体で `pl_agree` は既定 `true` として動きます。
- CUDA 実装と SYCL port に同じ判定・確率処理があります。OS や GPU driver がこの変数を読む処理は Strata ソースでは確認されません。

## 実行時の詳細

chain を使って `A` を強制的に通した場合（`chain_kind == 1`）、実装は `A` の各 draft 位置で chain の確率 `op[i]` と、`A.prob[i]` に保持した元の draft 確率のどちらを掛けるか選びます。`pl_agree=true` なら `op[i]` を掛け、chain が出した token `oc[i]` と `A.tok[i+1]` の不一致が一つでもあれば `pa` を 0 にします。`pl_agree=false` なら `A.prob[i]` を掛け、token 不一致による 0 化は行いません。こうして求めた `pa` は `make_b()` で `B.p_on` になり、theta 閾値以上なら `B` を speculative に開始できるため、この変数は次 window の開始可否に影響します。別の chain 分岐では `A.prob` を掛ける既存処理があり、この設定の分岐は通りません。

`STRATA_PIPELINE_DEBUG` 有効時の mismatch 数は `pl_disagree` に加算され、decode timing 出力が有効な場合は `strata pipeline classes: ... forced-chain disagreements %lld ...` に表示されます。debug gate や `STRATA_PIPELINE_AGREE` 自体を理由とする警告・エラー出力はありません。

## 根拠

- 候補一覧には掲載されていますが、Strata 内の実読み取りは CUDA 系と SYCL 系の各一箇所です。`000_envvers.md` にある名前だけでなく両方の本番ソースを確認しました。
- `src/program/generate.cpp:461-467`, `sycl/src/program/generate.cpp:298-303` — tuning/test 変数を `STRATA_PIPELINE_DEBUG` で gate する helper と、その debug 有効判定の cache。
- `src/program/generate.cpp:16364-16373`, `sycl/src/program/generate.cpp:11376-11385` — `STRATA_PIPELINE_AGREE` の読み取り、`atoi` 判定、既定値。
- `src/program/generate.cpp:16478-16492`, `sycl/src/program/generate.cpp:11485-11500` — 元 draft 確率と chain 確率の選択、不一致時の確率ゼロ化、`B` 作成への伝搬。
- `src/program/generate.cpp:16496-16505`, `src/program/generate.cpp:16522-16532` — `B.p_on` と theta による speculative staging / launch 条件。
- `src/program/generate.cpp:16713-16723`, `sycl/src/program/generate.cpp:11737-11747` — mismatch 数が timing 出力に載る条件と文言。
- `src/program/generate.cpp:4985-5032`, `src/program/generate.cpp:14777-14814`, `docs/MULTI_GPU.md:174-197` — pipeline の有効構成、serial fallback の説明、および tuning/test 変数が `STRATA_PIPELINE_DEBUG=1` 時のみ読まれる説明。
