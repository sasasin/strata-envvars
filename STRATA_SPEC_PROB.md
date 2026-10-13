# `STRATA_SPEC_PROB`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

サンプリング中の MTP speculative decoding で、draft head が出した token を常に完全一致で判定する代わりに、draft head の分布 `q` から token を引き、主モデルの分布 `p` に対する棄却サンプリングで採否を決めます。採択確率は `min(1, p(d)/q(d))`、棄却時は `max(0, p-q)` の残差分布から replacement を選びます。draft に分布がない suffix / prompt lookup の token は point mass として扱い、既存の完全一致判定を使います。

## 値と判定

`spec_prob_env()` は `getenv()` の結果が null でなく、空文字列でもなく、文字列全体が正確に `"0"` でない場合に有効です。大文字小文字や数値としての parse はありません。

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字列 | 無効 |
| `0` | 無効 |
| `1`、`true`、`false`、`00`、`0abc`、その他の非空文字列 | 有効 |

判定結果は `spec_prob_env()` 内の function-local `static const bool` に初回評価時から保存されます。プロセス内で環境を後から変更しても再評価されません。`STRATA_SPEC_COUPLED` も有効なら、両方の設定が共同 sampler を有効にしますが、確保された `h_q_` があると draft では確率的 sampling が選ばれます。

## 有効になる条件

- MTP が有効で、対象の生成リクエストが greedy ではなく `temperature > 0` である必要があります。greedy / temperature 0 では `coupled_active_` が false になり、この方式は使われません。
- 実装は `src/kernels/cuda/sampler.cu` の CUDA sampler と `src/core/mtp.cpp` の MTP 経路にあります。対応する本番実装を確認できたのはこの CUDA 経路です。
- draft logits の語彙幅が coupled sampler の上限を超え scratch サイズが 0 になる場合、setup は警告を出し argmax drafts に戻ります。その経路では分布 buffer `h_q_` を確保しないため、確率的判定も有効になりません。
- MTP の分布 buffer を mapped memory として確保できない場合、setup は `mtp: the draft distributions' buffer does not fit` で失敗します。
- verifier が `sample_tokens_spec()` を実行できない場合（split sampler 以外の sampler path、語彙 block / window の上限超過、stream capture 中、scratch 確保失敗など）は false を返し、通常の `sample_tokens()` に fallback します。MTP 分布のない行や suffix draft も point mass / 完全一致の扱いです。

## 実行時の詳細

`coupled_draft_env()` はこの変数または `STRATA_SPEC_COUPLED` が有効なら MTP の共同 sampler setup を要求します。`STRATA_SPEC_PROB` が有効な setup では、MTP が各 sampled draft の `q` を最大 64 token の ID・確率列として mapped buffer に書きます。draft の乱数 stream は verifier の draw と別の Philox counter 空間を使います。主モデル側の `p` は penalties、top_k、top_p、min_p、temperature を適用した後の sampler 分布です。

生成側は MTP drafts に対応する `q` 列を verifier に渡します。CUDA verifier は各 draft 行で採択判定をし、棄却時は residual 分布から token を選び、最後の行は通常の `p` から sample します。ホスト側の既存の accepted-prefix 判定はそのままです。実装は `strata mtp: probabilistic draft acceptance on (STRATA_SPEC_PROB): ...` を stderr に出します。MTP 未使用、greedy request、または fallback 経路ではこのログがあっても個々の行で rejection sampling が走らない場合があります。

`docs/DETAILS.md` は RTX 3060、IQ3_XXS、200-token の story/code 各回答、10 組の interleaved run で rejection sampling が 0.3 / 0.7 / 1.0 temperature 時に 41.0 / 42.6 / 42.6 tok/s と記載し、default の 42.4 / 43.2 / 43.3 tok/s を上回らず、繰り返し間の差は最大 5% としています。これは同資料の測定条件での記録です。`docs/MULTI_GPU.md` にも `STRATA_SPEC_PROB=1` の行（137.2 tok/s、1788 MiB）が載っていますが、そこでの表はその値単独の測定条件を説明していません。

## 根拠

- 値判定、共同 sampler との関係: `include/strata/core/coupled_draft.hpp:65-79`。
- setup、幅上限時の argmax fallback、分布 buffer、stderr ログ、request sampling 条件: `src/core/mtp.cpp:520-573,576-580,682`、`include/strata/core/mtp.hpp:116-120`。
- MTP が `q` を出力し、分布列を verifier に渡す箇所: `src/core/mtp.cpp:999-1009`、`src/program/generate.cpp:12046-12049,13216-13217`。
- draft distribution の計算・記録と CUDA verifier の採択、残差 sampling: `src/kernels/cuda/sampler.cu:937-1003,1005-1099`。
- verifier の fallback 条件と plain sampling への切替: `src/kernels/cuda/sampler.cu:1347-1369`、呼び出し側 `src/core/verify.cpp:2309-2336`。
- 測定記録: `docs/DETAILS.md:1260`、補助記録 `docs/MULTI_GPU.md:332-334`。
