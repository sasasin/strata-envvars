# `STRATA_SCORES_THREAD`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA の prompt block score 計算で、warp 単位の scorer の代わりに thread-per-head（HIP の実装コメントでは four-lanes-per-query）kernel を選びます。CUDA では active block 数が指定された prompt 呼び出し、HIP ではさらに GPU 世代・live block 数・query 数の条件を満たす呼び出しに適用されます。decode の `active_blocks <= 0` 経路はこの切替判定を通りません。

ソースコメントと `docs/DETAILS.md` は、置き換え先と bitwise 同じ score を計算すると説明しています。実行条件を満たさない呼び出しは通常の warp scorer に進みます。

## 値と判定

| ビルド | unset | 設定時 | 空文字・不正文字列 |
|---|---|---|---|
| CUDA | Turing（compute capability 7.5）では `STRATA_SM75_PERF` が非ゼロなら有効。それ以外は無効 | `atoi(value) != 0` なら有効。0 は無効 | `atoi` の結果で判定。空文字や数字で始まらない文字列は 0。先頭空白や符号の後の数値は変換され、数値以降の文字列は全体検査されない |
| HIP | gfx12 では有効、gfx1100 およびその他では無効 | `atoi(value) == 1` のときだけ明示的な有効値。その他は無効 | `atoi` の結果が厳密に 1 かで判定。空文字・数字で始まらない値・`2` は無効。`1x` は 1 として扱われる |

CUDA の設定値は「1 との一致」ではなく、`atoi` の結果が非ゼロかで判断されます（例: `2` は有効）。HIP は `atoi` の結果が厳密に 1 かで判断されます。いずれも文字列の大文字小文字比較はしません。

## 有効になる条件

- **CUDA**: QSA block scorer が `active_blocks > 0` で呼ばれ、環境判定が有効であること。明示した非ゼロ値は GPU 世代を問わずこの scorer を選択可能にします。unset 時の既定 ON は Turing（CC 7.5）かつ `STRATA_SM75_PERF` が `atoi` で非ゼロの場合に限られます。
- **HIP**: `active_blocks >= 16385`、`active_blocks <= max_blocks`、`nq >= 64` であり、GPU が gfx12 であるか、`STRATA_SCORES_THREAD` が明示的に 1 と判定されて GPU が gfx1100 であること。gfx12 は unset でも候補になります。gfx1100 は unset では有効になりません。
- HIP の GPU 判定は device 名から gfx12 / gfx1100 を確認します。その他の GPU では有効値を設定してもこの kernel に切り替わりません。
- QSA scorer の上位経路が tensor-core scorer を選んだ場合はこの block scorer に到達しません。たとえば prefill は `qsa_block_scores_tc` が成功すると `qsa_block_scores` を呼びません。CUDA の `STRATA_SELECT_OLD` は通常その tensor-core scorer を迂回する条件の一つです。
- `active_blocks <= 0` かつ複数 query の通常経路では、`qsa_block_scores` 内の別の multi scorer が先に選ばれます。したがって CUDA の任意 GPU opt-in は、この早期分岐を迂回して全呼び出しに適用されるものではありません。

## 実行時の詳細

値は `qsa_block_scores` 内の関数ローカル static で初回評価時に保存されます。CUDA は `scores_thread_on()` の static 値として、HIP は `thread_env` としてキャッシュするため、判定後に同じプロセス内で環境値を変更しても再評価されません。未設定時の CUDA Turing 既定は `sm75_default()` に委譲され、これは CC 7.5 と `STRATA_SM75_PERF` の `atoi(value) != 0` の両方を要求します。

HIP で実際に切り替わると、`block_scores_thread_kernel` に続けて `block_scores_tail_kernel` を起動します。CUDA も同じ2 kernel を起動します。起動エラー時は stderr に `qsa exact thread: <CUDA error>`（HIP）または `qsa_block_scores thread: <CUDA error>`（CUDA）を出し、プロセスを終了します。

HIP は一 host thread あたり一度だけ利用ログを出せます。環境変数が unset の gfx12 既定動作では TRACE 未設定でもログを出し、明示設定時は `STRATA_SCORES_THREAD_TRACE` が設定されているときに限ります。TRACE は設定有無だけで判定され、空文字でも設定扱いです。ログ文字列は `qsa exact thread: the prompt's block scorer runs as the four-lanes-per-query kernel ...` です。CUDA のこの切替箇所には利用ログがありません。

## 文書と測定値

`docs/DETAILS.md` は CUDA Turing の thread-per-head scorer を説明し、Tesla P100 の 30–60K token 条件で prompt speed +1–3% と報告しています。HIP の `docs/AMD_HIP.md` は gfx12 を既定 ON、gfx1100 を opt-in とし、R9700 上の測定・比較条件を記載しています。これらは資料に記された機種・条件での結果であり、他の機種や prompt での性能を示すものではありません。

## 根拠

- `src/kernels/cuda/qsa_select.cu:1219-1237` — HIP 対象 GPU の分類（gfx12 / gfx1100）。
- `src/kernels/cuda/qsa_select.cu:1676-1691` — CUDA の値判定と Turing 既定条件。
- `include/strata/core/sm75_series.hpp:24-37` — `STRATA_SM75_PERF` の読み取り・既定条件。
- `src/kernels/cuda/qsa_select.cu:1709-1793` — 早期分岐、CUDA/HIP の有効条件、kernel 選択とエラー処理。
- `src/prefill/prefill.cpp:3150-3162` — prompt 経路の active block 算出、tensor-core scorer からの fallback。
- `CMakeLists.txt:405-418,455-460` — parity test が環境値を設定する箇所（本番挙動の根拠ではなく、テスト専用設定）。
- `docs/DETAILS.md:2244-2257`, `docs/AMD_HIP.md:307-319` — Strata 資料の適用説明と測定条件。
