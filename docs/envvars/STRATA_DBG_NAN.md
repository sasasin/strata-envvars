# `STRATA_DBG_NAN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU prefill と speculative verify の中間値を調べ、非有限値（NaN / Inf）の数を stderr に出す診断用スイッチ。値の内容は判定せず、環境変数が存在するかで有効になるため、生成 token や演算結果を修正・置換する設定ではない。診断のための同期と device-to-host copy が加わる。CUDA/HIP の prefill は MoE 後の作業領域、プロンプト末尾の状態、HIP の FP16 GEMM 出力を調べ、CUDA と SYCL の verifier は logits を調べる。SYCL prefill にも対応する診断経路がある。主な実装は `engine/src/prefill/prefill.cpp`、`engine/sycl/src/prefill/prefill.cpp`、`engine/src/core/verify.cpp`、`engine/sycl/src/core/verify.cpp`。

また、有効時は一部の高速経路の条件から外れる。CUDA は `share_gate_workspace` と MoE weight-stationary 経路、SYCL は Battlemage FP16 group と expert window の経路でこの変数の未設定を要求する（`engine/src/prefill/prefill.cpp:1306-1311,6543-6556`、`engine/sycl/src/prefill/prefill.cpp:4840-4849,5842-5848`）。

## 値と判定

すべての読み取り箇所は `getenv(...) != nullptr`（または同等の真偽判定）で、値を数値・文字列として parse しない。したがって unset のみ無効で、空文字、`0`、`0anything`、`false`、大文字小文字違いを含む任意の設定値は有効。境界値・無効文字列の fallback はない。ドキュメント中の `=1` は例であり、`1` 固有の意味はない。

| 条件（build / 実行経路） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA / HIP prefill・verify、SYCL prefill・verify | 無効 | `1`, `0`, 空文字, `false`, `0anything` | unset のみ |

CLI 引数や別環境変数による上書き・優先順位はない。各コード経路は同じ環境変数の有無を独立に判定する。

## 有効になる条件

- 該当する CUDA/HIP または SYCL backend を含む実行バイナリで、対応する経路が実行されること。CPU-only 経路にはこの診断処理はない。
- prefill の MoE 診断は該当する MoE chunk の処理後、FP16 GEMM 診断は HIPCC でコンパイルされた `Gemm::f16_inplace`、状態診断は prompt 処理完了時に実行される（`engine/src/prefill/prefill.cpp:7631-7655,7903-7923`、`engine/sycl/src/prefill/prefill.cpp:5332-5386,5640-5669`、`engine/src/prefill/gemm.cu:1460-1483`）。
- verifier の logits 診断は window の sampling 完了後に実行される（`engine/src/core/verify.cpp:4242-4290`、`engine/sycl/src/core/verify.cpp:2958-2993`）。
- 環境変数有効時には、CUDA の共有 gate workspace / weight-stationary MoE と、SYCL の FP16 group / expert window の一部条件付き高速経路は使われない。その他の MoE 形状・モデル条件は通常のコード分岐に従う（上記「役割」参照）。

## 実行時の詳細

- CUDA verifier、SYCL verifier、両 backend の MoE chunk 診断は、関数内 `static const bool` に初回評価結果を保存する。これらは最初の該当呼び出し時に環境を読み、以降の環境変更は反映しない（`engine/src/core/verify.cpp:4274-4276`、`engine/sycl/src/core/verify.cpp:2976-2978`、`engine/src/prefill/prefill.cpp:7631-7633`、`engine/sycl/src/prefill/prefill.cpp:5333-5335`）。CUDA/HIP の FP16 GEMM も同様に最初の `f16_inplace` 呼び出しで cache する（`engine/src/prefill/gemm.cu:1473-1475`）。
- prompt end の状態診断は各 prompt 完了時に `getenv` を再評価する。CUDA/SYCL の `share_gate_workspace`、weight-stationary、FP16 group、expert window 条件も呼び出しごとに有無を直接確認するため、これらの判定は static cache ではない（`engine/src/prefill/prefill.cpp:1306-1311,6545-6549,7903-7908`、`engine/sycl/src/prefill/prefill.cpp:4840-4845,5640-5645,5842-5848`）。
- MoE 診断は stream/queue を同期し、GPU バッファを host に複製して非有限値を数える。CUDA は `GU`, `H`, `Dm`, `bo`, `shared`, `sg`, `w` を調べ、融合・部分 CPU 処理などでは一部領域を除外する。SYCL は主に `GU`, `H`, `Dm`, `bo` と、利用可能な FP16 activation / dequantized gate-up 入力を調べる。異常がなければ MoE の行ログは出さない。ログは chunk ごとに最初の異常 layer で一度出す（`engine/src/prefill/prefill.cpp:7632-7655`、`engine/sycl/src/prefill/prefill.cpp:5334-5385`）。
- prompt end は最後の residual row、利用可能なら PLE history、GDN state 0 の非有限値数と有限値の最大絶対値を出す。これは異常がゼロでも出る（`engine/src/prefill/prefill.cpp:7907-7923`、`engine/sycl/src/prefill/prefill.cpp:5644-5669`）。
- HIP の FP16 GEMM は出力を FP32 に widen する際に非有限値を数える。診断有効時は GEMM ごとに stream synchronize し、count が 0 より大きいときだけログを出してカウンタをゼロに戻す。該当関数の `#else` 側は引数を未使用にするため、この計測は HIPCC build に限られる（`engine/src/prefill/gemm.cu:105-112,1460-1485`）。SYCL 側コピーにも同じ HIPCC 条件付き実装がある（`engine/sycl/src/prefill/gemm.dp.cpp:61-75,1054-1075`）。
- これらの診断分岐自体はエラーを返したり値を修復したりしない。SYCL prefill の診断用 host copy が `sycl::exception` を投げた場合は例外文と file/line を stderr に出し `exit(1)` する（`engine/sycl/src/prefill/prefill.cpp:5336-5351,5646-5661`）。

## ログと測定値

- verifier は最初に非有限 logits を検出した window を一度だけ stderr に出す。文言は `strata dbg: verify window at position %lld, row %d: %lld of %lld logits non-finite (token out %d)`（CUDA: `engine/src/core/verify.cpp:4274-4288`、SYCL: `engine/sycl/src/core/verify.cpp:2976-2991`）。
- MoE で異常を検出すると `strata dbg: layer ... non-finite ...` の2行を出す。SYCL は異常がある場合に限り、先行して `strata dbg: layer ... fp16 inputs: activations ...` も出す（`engine/src/prefill/prefill.cpp:7648-7655`、`engine/sycl/src/prefill/prefill.cpp:5372-5385`）。
- prompt end は `strata dbg: prompt end: last residual row` に各状態の `non-finite` 数と `max |x|` を続ける（CUDA: `engine/src/prefill/prefill.cpp:7915-7923`、SYCL: `engine/sycl/src/prefill/prefill.cpp:5654-5669`）。
- FP16 GEMM で非有限出力があれば `strata prefill: STRATA_DBG_NAN: %llu non-finite FP16 GEMM outputs (T=%lld N=%lld K=%lld; FP16 ends at 65504)`（`engine/src/prefill/gemm.cu:1475-1481`、SYCL tree の HIPCC 経路: `engine/sycl/src/prefill/gemm.dp.cpp:1063-1069`）。
- `docs/INTEL.md:468` は「experts' FP16 inputs」を含む診断と要約するが、実装では backend により調べる領域・出力条件が異なる。`docs/AMD_HIP.md:516` の「non-finite FP16 outputs」は HIP GEMM 経路の限定的な説明である。ここでは資料の要約を全 backend 共通の挙動とは扱わない。測定値の記載はない。

## 根拠

- 全ソース参照（実装とコメント）: `engine/src/core/verify.cpp:4247,4274-4290`、`engine/sycl/src/core/verify.cpp:2976-2993`、`engine/src/prefill/gemm.cu:103-112,1473-1483`、`engine/sycl/src/prefill/gemm.dp.cpp:65-75,1061-1071`、`engine/src/prefill/prefill.cpp:1306-1311,6545-6549,7631-7655,7903-7923`、`engine/sycl/src/prefill/prefill.cpp:1311,4840-4849,5333-5386,5644-5669,5842-5848`。
- 候補一覧: `docs/envvars/000_envvers.md:898`。候補名に対応する Strata 所有コードの実読み取りが確認できた。
- 作業開始時の checkout: `git rev-parse HEAD` は記録した SHA、`git status --short --branch` は `## main...origin/main`。
