# `STRATA_LOGPOS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

診断・測定用のフックです。`--serve` のプロンプト読み込みで、verify window を通った token について、その位置の logit 分布から teacher-forced の log-probability を stderr ではなくファイルへ 1 行ずつ追記します。生成結果や routing を変えるものではなく、Strata が llama.cpp など別エンジンと同じ token 列に対して分布を比較できるようにするための出力です（`docs/UNSLOTH_Q4.md:190-226`）。

読み取り箇所は 2 箇所あります。

- `src/program/generate.cpp:10650` — 値の有無だけを見て、pipelined prompt read を使うか serial loop を使うか分岐する。
- `src/program/generate.cpp:10683-10686` — 出力先パスとして読み、`std::fopen(p, "ab")` で開く。

実装本体は `src/core/verify.cpp:2438-2492`（`Verifier::window_logprobs`）、宣言と行フォーマットの説明は `include/strata/core/verify.hpp:278-285`。SYCL ビルドには同じ構造の写しがある（`sycl/src/program/generate.cpp:9966,9993-10001`、`sycl/src/core/verify.cpp:2558-2612`、`sycl/include/strata/core/verify.hpp:232-238`）。

## 値と判定

値は数値でもフラグでもなく、**出力ファイルのパス文字列**として扱われます。判定は 2 種類で、意味が異なります。

| 状態 | `10650` の分岐（pipelined read） | `10683-10686` のファイル |
|---|---|---|
| 未設定 | pipelined path を使う（条件が揃えば） | 開かない。行を書かない |
| 空文字 `""` | `getenv` は nullptr ではないので **serial loop へ fallback** | `std::fopen("", "ab")` は失敗して nullptr。分岐だけ効き、出力は無い |
| 有効なパス | serial loop へ fallback | append mode で開く。失敗すれば nullptr で、警告なしに出力だけ止まる |

- パスとして解釈されるだけで、内容の妥当性検査・`~` 展開・ディレクトリ作成はしません。開けなければ黙って何も出ません。
- 開いたファイルは閉じられません（この経路に `fclose` がない）。プロセス終了まで append で保持されます。
- 値は関数内 `static std::FILE*` に一度だけ初期化されます。プロセス起動後に環境を書き換えても、ファイルハンドルは再評価されません。一方 `10650` の `std::getenv("STRATA_LOGPOS") == nullptr` 判定は `read_windows` が呼ばれるたびに実行されます（リクエストごとに環境を反映する部分と、static cache される部分が混在している）。

関連変数（個別文書は未作成、ここでは必要条件としてのみ記載）:

- `STRATA_LOGPOS_EXTRA` — `std::atoi` で読む整数 token id。既定 `248046`（`<\|im_end\|>`）。未設定なら既定、設定時は parse 結果。負値や範囲外は「該当なし」として NAN 列になる（`src/core/verify.cpp:2460`）。
- `STRATA_LOGPOS_TOPK` — `std::atoi` 後 `max(0, min(256, ·))` に clamp。既定 0（追記なし）。`0anything` は 0、`300` は 256。

## 出力フォーマット

window の各行（位置 `pos0 + t`）につき 1 行、tab 区切り。

```
pos  target  logprob  top  top_logprob  hit  extra_logprob  target_logprob_without_extra  [id:logprob × topk]
```

- `pos` は `%lld`、`target`/`hit` は `%d`、log-probability は `%.9f`（top-k 部分是 `%.6f`）。
- `logprob` は `row[t] - lse`（`lse = maxv + log(sum)`、double で計算）。
- `hit` は argmax が target と一致すれば 1。
- `extra_logprob` は `extra_id` の log-probability。`extra_id` が語彙範囲外なら NAN。
- 最終列は `extra_id` を除いて再正規化した分布上の target の log-probability。`extra_id` が範囲外、target が `extra_id` 自身、または `sum_without == 0` の場合は NAN。
- `target` が負または `n_vocab_` 以上ならその位置は **行を書かずに skip** します（`src/core/verify.cpp:2455`）。
- `window_logprobs` の呼び出しごとに、全行を書いた後で `std::fflush(out)` する（`src/core/verify.cpp:2490`）。

## 有効になる条件

`--serve` のリクエスト処理内でのみ呼ばれます。`read_windows` の呼び出し箇所は `src/program/generate.cpp:11053` 1 箇所だけで、その外側は `if (o.serve)`（`src/program/generate.cpp:6859`）です。非 serve の単発実行では効きません。

さらに、次の条件を満たす part だけが logpos 行を出します。

- その part が verify window を通ること。`windows_ok(a, b)` が true である必要がある（`src/program/generate.cpp:10524-10530`）。
  - `b - a <= req_short_read`。`req_short_read` は `--short-read`（既定 64、`0` は off。`src/program/generate.cpp:646,2036`）。
  - `sp.embd_rows` に非 null の行がない。画像（multimodal embedding）行は batched path 側へ回るので、**画像 token からは何も出ない**。
  - `STRATA_CKPT_REREAD` が設定されていると `no_short` が true になり、すべての読みが batched path へ回って **logpos 行は出ない**（`src/program/generate.cpp:10522`）。
- batched prompt path（`read_part`）は logpos を呼ばない。したがって長文プロンプトでは、window を通る末尾 `--short-read` token 分だけが計測される。`docs/UNSLOTH_Q4.md:225` が「`--short-read` covering the positions to compare」と書いているのはこのためです。
- `window_logprobs` は `head_logits_ != nullptr`、`n_vocab_ > 0`、`T > 0` を要求し、`run()` が `cs_` を同期して返った後で呼ばれる（`src/core/verify.cpp:2442-2446`）。
- layer split では、head を持つ stage へ転送される（`src/core/verify.cpp:2440`、`include/strata/core/verify.hpp:283`）。
- CUDA ビルドの pipelined 分岐は `pipe && n_stages == 2 && pl_pw >= 1` で、SYCL 写しには `n_stages == 2` 条件がない（`src/program/generate.cpp:10650` と `sycl/src/program/generate.cpp:9966`）。`pl_pw` は `--pipeline-windows`、`STRATA_PIPELINE_SWITCH` のファイル内容 `pw=` でリクエストごとに上書きされ得ます（`src/program/generate.cpp:10534,10543-10552`）。

## 実行時の詳細

`read_windows` は window ごとに次を行います。

1. `set_head_sampling(false)` — 全 token を commit し pick は破棄する（teacher-forced）。`src/program/generate.cpp:10653-10657`。
2. `ver.run(T, win, q, ...)` — 失敗すれば logpos 書込み前に戻る。
3. CUDA では `nonfinite_hit(ver, "prompt")` 検査後（`src/program/generate.cpp:10675-10678`）、SYCL ではこの検査がない。
4. `logpos != nullptr` なら `ver.window_logprobs(nxt, T, q, logpos_extra, logpos, e)`。`nxt[t]` はプロンプト自身の `pos0+t+1` の token（`src/program/generate.cpp:10666`）。
5. 失敗すると `read_windows` が false を返し、serve は stderr に `strata serve: <err>`、stdout に `ERR <err>` 出してリクエストを失敗させる（`src/program/generate.cpp:11065-11076`）。CUDA fault 時は `_Exit(1)`。
6. その後に `ver.commit(T, e)` と MTP prefill が続く。

コスト: window ごとに `T × n_vocab` の float を device から host へコピーし、語彙全体に対して softmax 分母（`sum`）を 2 回計算します。`topk > 0` なら語彙全体の index 配列を作り `partial_sort` します。`--short-read` を大きくして計測する際に効く部分です。

ログ: 環境変数自身の開封失敗や無効値に関する警告は実装されていません。stdout に出る関連ログは `PP <b> <total> <ms> <tok/s>` 行（`src/program/generate.cpp:10700-10702`）と、`STRATA_PIPELINE_SWITCH` 使用時の `strata pipeline switch: pw=... short_read=...`（`src/program/generate.cpp:10553-10554`）、`STRATA_TRACE` による `strata trace: read N tokens (windows|batched) in X ms`（`src/program/generate.cpp:11055-11059`）で、この行は logpos が効いた経路（windows か batched か）を判別する手掛かりになります。

## 資料中の測定

`docs/UNSLOTH_Q4.md:190-226` はこのフックを使った比較結果です（llama.cpp pinned commit `3cf0325`、CPU build、GGUF mmap、Strata engine 0.1.32、RAM budget 40 GiB、MTP on、greedy、`--adapt-every 100000`、`STRATA_LOGPOS_TOPK=20`）。Argmax agreement は code 99.0%、thinking 97.5%、16K prompt 後 90.2% など、条件と測定環境が示された範囲の値として記載されています。

`bench/results/2026-10-03-v100-prompt-attn/README.md:63-74` と `bench/results/2026-10-04-rdna2-fp16-prompt/README.md:67-68` は `STRATA_LOGPOS_TOPK=256`、`--short-read 640`、`--max-context 204800` での KL 比較（617 positions per prompt）です。`bench/results/2026-10-09-rope-yarn-long-context/probe.py:65` はこのフックを子プロセスの環境から明示的に除去しています。これらは資料中の測定であり、他機種の性能や一致率の保証ではありません。

## 根拠

- `src/program/generate.cpp:10650`（pipelined read の分岐）、`10683-10691`（fopen、extra id、呼び出し）
- `src/core/verify.cpp:2438-2492`（行フォーマット、skip、clamp、flush）
- `include/strata/core/verify.hpp:278-285`（列の定義）
- `src/program/generate.cpp:6859`（`--serve` のみ）、`10522-10530`（`windows_ok`、`--short-read`）、`11053`（唯一の呼び出し箇所）、`11065-11076`（失敗時の出力）
- SYCL 写し: `sycl/src/program/generate.cpp:9966,9993-10001`、`sycl/src/core/verify.cpp:2558-2612`
- 関連変数: `STRATA_LOGPOS_EXTRA`（`src/program/generate.cpp:10687-10690`）、`STRATA_LOGPOS_TOPK`（`src/core/verify.cpp:2476-2479`）

確認できていない点: `fopen` 失敗時の警告がないため、パスが無効な場合に「効いていない」ことと「開けなかった」ことを区別する手段はソース上にありません。テスト専用コード（`src/core/arch_defaults_test.cpp`）は `STRATA_LOGPOS` を参照していないため、値域に関する追加の根拠はありません。
