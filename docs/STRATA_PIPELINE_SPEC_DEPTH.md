# `STRATA_PIPELINE_SPEC_DEPTH`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の decode pipeline で、推測実行する窓 B を先行させる front stage 数の上限を指定します。値 `k` のとき、B は先頭から stage index `0` 〜 `k-1` までで推測実行されます。pipeline の有効化自体や `--pipeline-windows` の設定は行いません。

この環境変数の読み取りは `src/program/generate.cpp` にだけあります。CUDA/HIP 共通の生成実装内の pipeline loop に置かれています。SYCL 側の `sycl/src/program/generate.cpp` にはこの変数の読み取りがなく、この制限は適用されません。

## 値と判定

`pipe_dbg_env()` が値を返す場合に限り、`std::atoi()` で整数変換し、`std::max(1, ...)` で下限を 1 にします。文字列全体の妥当性検査はありません。

| 状態・値 | `pl_spec_depth` |
|---|---:|
| `STRATA_PIPELINE_DEBUG` が無効で、対象変数が helper から隠される | 1,048,576（既定値） |
| デバッグ有効、対象変数 unset | 1,048,576（既定値） |
| デバッグ有効、空文字または `0`、負数 | 1 |
| デバッグ有効、`2`, `2tail`, ` 2tail` | 2（`atoi` が読む整数部分） |
| デバッグ有効、整数に変換できない文字列 | 1（`atoi` が 0 を返し、下限を適用） |
| デバッグ有効、stage 数以上の正数 | 指定値。ただし実際には存在する front stage まで |

`atoi` は先頭の空白と符号を受け付け、数字の後ろに続く文字列を無視します。大きすぎて `atoi` で表現できない数値の挙動には依存しないでください。

## 有効になる条件

- `--pipeline-windows` による layer-split pipeline が有効で、decode pipeline loop が実行される必要があります。環境変数だけでは pipeline は開始しません。
- 読み取りは `STRATA_PIPELINE_DEBUG` によってゲートされます。未設定、空文字、または先頭文字が `0` の場合は他の `STRATA_PIPELINE_*` 値と同様にこの値も無視され、既定の深さになります。非空で先頭文字が `0` 以外なら読み取りを許可します。`1` との完全一致や数値 parse は行いません。
- 深さの上限はコード上 clamp されませんが、B の front-stage index が `pl_nf`（front stage 数）未満かどうかで判定するため、実行される stage 数を超えた値は追加の効果を持ちません。
- Stage 0 ではさらに、予測の信頼度 `B.p_on >= theta` と context 上限の条件が必要です。条件を満たさない場合 B は破棄され、`pl_gate` が増えます。後続 front stage では同じ gate 条件を使いません。
- pipeline loop 自体が別条件（たとえば repetition penalty や coupled draft sampling）で serial decode に切り替わる要求では、この値による推測実行は起きません。

## 実行時の詳細

`pipe_dbg_env()` は `STRATA_PIPELINE_DEBUG` の判定結果を関数内 `static const bool` に保存します。未設定・空文字・先頭 `0` は無効、それ以外の設定値は有効です。この gate は最初に helper が呼ばれた時に評価され、その後の環境変更では再評価されません。

深さ `pl_spec_depth` は pipeline loop 内の `static const int` として初回評価時に保存されます。従って対象変数も、初回評価後にプロセス環境を変更しても反映されません。debug gate が無効なら helper は対象変数を読まず、既定値 `1 << 20` を使います。

B が stage `st` で推測実行される条件には `B.fr < pl_nf` と `B.fr < pl_spec_depth` が含まれます。条件を満たすと、先行する A の commit と GDN snapshot を行った後に B を launch し、B が使った stage を `A.com` に記録します。後で A が受理されれば未使用 stage に実 commit を行い、拒否されれば speculative window を snapshot から戻して実 commit を再実行します。この環境変数はこの先行 stage 範囲を絞るだけで、窓の生成数や verifier 自体の stage 数を変更しません。

この変数専用のログ出力はありません。pipeline の開始・serial fallback 等に伴うログは環境変数以外の pipeline 条件で決まります。

## 根拠

- `src/program/generate.cpp:340-345` — `STRATA_PIPELINE_DEBUG` のゲートと helper のキャッシュ。
- `src/program/generate.cpp:9124-9129` — front stage 数 `pl_nf` と debug gated helper の使用例。
- `src/program/generate.cpp:14067-14086` — decode pipeline の適用条件、serial fallback。
- `src/program/generate.cpp:14510-14549` — 深さの parse、front-stage 条件、stage 0 の追加 gate、speculative launch。
- `src/program/generate.cpp:14632-14651` — A の受理時 commit と speculative window の rollback。
- `sycl/src/program/generate.cpp:296-300,11000-11120` — SYCL に helper はあるが、`STRATA_PIPELINE_SPEC_DEPTH` は読み取られない（候補変数の完全一致検索も実施）。
- `docs/DETAILS.md:195-199` — `--pipeline-windows 2` と `STRATA_PIPELINE_ADAPT_ASYNC` の関係。`STRATA_PIPELINE_SPEC_DEPTH` の説明や測定値は見つからなかった。
