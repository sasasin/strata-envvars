# `STRATA_PREFILL_PIPE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

複数 GPU の layer split で、prompt の chunk サイズを各 stage の処理が重なるように計画する設定です。通常の prompt prefill 動作全般や decode を切り替える変数ではありません。`--prefill-pipe` が未指定のときの既定値として使われます。対象実装は共通の prefill 経路で、Qwen3.6 専用 engine の `STRATA_Q36_CHUNK` とは別の設定です。

## 値と判定

環境値は最初に必要になったときに一度だけ読み、`static const` に保存します。未設定または空文字列なら `0` です。非空文字列は `std::atof` で数値化し、`std::max(0.0, value)` により負値を `0` にします。文字列全体の検証はしないため、`"1536tail"` は `1536`、数値として読めない文字列は `0` になります。正の無限大は後段で最大 `1,048,576` token 相当に丸められます。NaN は `std::max(0.0, NaN)` の結果として無効値側になります。

| 値 | layer split での意味 |
|---|---|
| 未設定、空、0、負値、無効文字列 | pipeline chunk 計画を使わない |
| `0` より大きく `1` 以下 | 既定の chunk 数を維持し、条件を満たすとき chunk を均等化する |
| `1` より大きい有限値 | stage 間の固定費/ token 費の比 `b/a`（token 単位）として chunk 数を探索する |

設定名から想像される真偽値 parse ではありません。たとえば `true` は `atof` で `0` となり無効、`1suffix` は均等化モード、`1536tail` は比率 1536 として扱われます。大文字小文字の比較はありません。

優先順位は、リクエストの `pipe=` 値、起動引数 `--prefill-pipe`、環境変数、既定値 `0` の順です。`--prefill-pipe` は負数も 0 に clamp されます。サーバーの `strata_tune.prefill_pipe` は数値（bool は除外）かつ 0..262144 の場合だけ `pipe=` として転送されます。各リクエストの `pipe=` 値はそのリクエストに限り、リクエストごとに未指定状態へ戻されます。

## 有効になる条件

値が正でも、prefill が 2 stage 以上の layer split であること、現在の prefill が stage 間で hand-in 済みでないことが必要です。1 stage、単一 GPU、値 0 以下では `plan_chunk()` が 0 を返し、既存の buffer chunk (`impl_->T`) を使います。従って環境変数を設定しただけでは単一 GPU の chunk サイズは変わりません。

この環境変数の fallback は CLI 引数とリクエスト設定に限られます。`--prefill-pipe 0` は環境変数を明示的に無効化します。CLI の値は parse 後 `Prefill::set_pipe()` で設定され、リクエスト値は `Prefill::set_pipe_request()` で上書きされます。

## 実行時の詳細

`Prefill::plan_chunk()` は stage 数を数え、正の設定値かつ 2 stage 以上の場合に `pipeline_chunk()` を呼びます。値が 1 以下なら現在の chunk 数を維持した均等化候補を使いますが、chunk 数が 1 以下、または末尾 chunk が `stream_all_min()` 未満なら均等化せず、既存の chunk 上限を返します。値が 1 より大きい場合は `b/a` を最大 `2^20` token に丸め、許される chunk 数候補を評価します。候補サイズは 256 token 境界に切り上げ、最低 512 token とし、通常の分割より計算コストが 3% を超えて改善するときだけ小さい chunk を採用します。

計画された chunk が従来の上限より小さく実際に分割される場合、stderr に `strata prefill: <N> tokens in <C>-token chunks over <S> stages (--prefill-pipe <値>)` 形式のログが出ます。通常値 1 以下の表示は `1: today's chunk count, evened out`、大きい値は `<丸めた b/a>: b/a` です。ログが出ない場合も、変数を読んだことや設定値が正であることだけから chunk が変更されたとはいえません。

環境値の変更は同一プロセスでは、static 初期化後に再評価されません。CLI や per-request 値は別の上書き経路です。環境変数自体を子プロセスへ転送する処理はこの実装では確認できません。

## 文書との照合

`docs/MULTI_GPU.md` の「Prompt chunks sized for the pipeline」節は、`STRATA_PREFILL_PIPE=<R>` を `--prefill-pipe` と同じ設定として説明し、chunk の計画と layer split に限ることを記載しています。実装とも整合します。同節にある性能測定値は特定環境の記録であり、この調査で再測定していません。

## 根拠

- `src/prefill/prefill.cpp:2037-2069` — env 読み取り、parse、static cache、CLI/request 値との優先順位。
- `src/prefill/prefill.cpp:2071-2105,2112-2128` — 比率の丸め、候補 chunk 計画、適用条件、ログ。
- `src/prefill/prefill.cpp:2410-2429` — 既定 chunk と planned chunk の選択、実際の prefill への適用。
- `src/program/generate.cpp:622-625,2456,4246` — CLI オプションの説明、parse、設定反映。
- `src/program/generate.cpp:11651,11685,11702` — request 値の既定、parse、各 request での設定。
- `serve/server.py:1199-1209` — server tuning config から request `pipe=` を送る条件。
- `src/program/generate.cpp:12757-12805` — request prompt segment に chunk を計画し、forced chunk として読み進める処理。
- `docs/MULTI_GPU.md:245-292` — 設計説明と記載された測定条件・例。
