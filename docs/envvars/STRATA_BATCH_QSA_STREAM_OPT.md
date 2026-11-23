# `STRATA_BATCH_QSA_STREAM_OPT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP の `Verifier::record_window` が batch window を記録するとき、QSA 層の block score 計算、top-k、KV resolve、attention を複数 slot の row にまとめる最適化を有効にする opt-in です。既定では無効です。`kv_mode==1` の streamed KV と `kv_mode==0` の resident KV の両方を対象にします。単独 decode の QSA 経路を切り替えるものではありません。`engine/src/core/verify.cpp:365-369,2140-2145`。

batch 最適化が使われる場合、連続する同一 slot の row を group 化し、slot ごとに indexer score をまとめて計算し、window の row を一括 top-k し、streamed KV の resolve group と複数 slot attention を使います。group 化できない状態では既定の per-slot/per-row 処理へ戻ります。`engine/src/core/verify.cpp:2145-2189,2200-2216,2420-2447`。

## 値と判定

本体の `env_on` は `std::getenv` の値が存在し、かつ先頭文字が NUL と `'0'` のどちらでもないとき true です。文字列全体や数値としての妥当性は調べません。大文字小文字・空白も比較しません。`engine/src/core/verify.cpp:336-339,369`。

| 読み取り経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| batch QSA 本体 (`env_on`) | OFF | `1`, `true`, `false`, ` 0`, `-1`（先頭文字が `0` 以外） | 空文字、`0`, `0anything`, `00` |
| pre-75 slot attention の既定連動 (`pre75_slots_on`; 対応 build のみ) | `STRATA_BATCH_QSA_STREAM_OPT` を `atoi` で判定 | `1`, `2`, `1tail`（`atoi` が非 0） | 空文字、`0`, `0tail`, `false`（`atoi` が 0） |

後者は同じ名前を直接 `getenv` し、`atoi` の結果が非 0 かで判定します。`STRATA_ATTN_PRE75_SLOTS` が設定されていれば、空文字を含め、その `atoi` 判定が優先されます。したがって値が `true` などの場合、本体の batch 最適化は ON でも、pre-75 slot attention の連動判定は OFF になります。これは pre-75 attention の選択条件に限る別経路です。`engine/src/kernels/cuda/qsa_decode_attn.cu:978-989`。

## 有効になる条件

- batch window の記録中であること（`batch_rec_` が true）。batch graph の capture で `record_window` を呼びます。`engine/src/core/verify.cpp:4677-4690`。
- QSA 層で対象の row 区間が複数行あること（`te > tb`）。最初の条件式は `batch_rec_ && batch_qsa_stream_opt_on() && te > tb` です。`engine/src/core/verify.cpp:2140-2145`。
- 各 slot group が最大 group 数以内、同一 slot が最大 8 row、indexer の pooled/dead buffer が存在し、group 間で pooled pointer が重複しないこと。条件を満たさなければその層では最適化をやめ、後続処理は既定の batch 経路を使います。`engine/src/core/verify.cpp:2145-2164`。
- streamed KV (`kv_mode==1`) の slot では、`n_slots >= max(ntok * max_pages_per_q, 1024)` であり、page table/control buffer があり、同時 resolve group 間で map が重複しないこと。満たさないときは最適化を無効化し、通常の slot ごとの resolve に戻ります。resident KV (`kv_mode==0`) はこの resolve 容量条件を通りません。`engine/src/core/verify.cpp:2165-2189,2534-2562`。
- 最適化経路は「複数 row」が条件ですが、関数内の QSA 層処理ごとに判定します。row 数が 1 の batch window ではこの変数によるまとめ処理は選ばれません。`engine/src/core/verify.cpp:2142`。
- CUDA/HIP attention で `STRATA_ATTN_PRE75_BUILT` が定義され、かつ `pre75_attn()` が選ばれた場合、複数 slot attention の pre-75 variant もこの変数に連動します。ただし明示的な `STRATA_ATTN_PRE75_SLOTS` があればそちらが優先されます。該当 build macro は CUDA、HIP の gfx906 以外、または実験的 SM60 build で定義されます。`engine/src/kernels/cuda/qsa_decode_attn.cu:492-505,926-964,978-989,1167-1172`。

## 実行時の詳細

本体 helper は関数内 `static const bool` で初回評価時に値を保存し、その後は同じプロセス内で再読込しません。従って初回評価後の環境変更は反映されません。CUDA/HIP attention 側にも独立した `static` 判定があり、pre-75 slot attention が必要になったときにその経路の値を保存します。`engine/src/core/verify.cpp:369`; `engine/src/kernels/cuda/qsa_decode_attn.cu:981-989`。

最適化時は group score が失敗した場合に group ごとの score 計算へ戻り、group top-k の後に streamed KV resolve groups を実行して複数 slot attention を試します。slot attention が対象条件を満たさず `false` を返した場合は、row ごとに `qsa_decode_attn_batch` を実行します。group の事前条件を満たさず `stream_opt_ok` が false の場合は、既存の slot run ループで score/top-k、必要な KV resolve、attention を処理します。`engine/src/core/verify.cpp:2200-2216,2420-2447,2470-2562`。

この変数自体に CLI 引数による上書きはありません。batch window が作られるかどうかは呼び出し側の実行経路に依存し、環境変数は batch window 内の QSA 分岐を決めます。pre-75 attention variant の選択だけは別環境変数 `STRATA_ATTN_PRE75_SLOTS` が優先されます。`engine/src/core/verify.cpp:2142`; `engine/src/kernels/cuda/qsa_decode_attn.cu:981-987`。

## ログと測定値

この変数専用の有効・無効ログや、Strata 資料に記載された本変数の測定値は確認できませんでした。`docs/SETTINGS.md:37` は on/off と NVIDIA/AMD の対象表記に留まり、`docs/BATCHING.md` と `docs/DETAILS.md` に本変数の説明や測定値はありません。最適化が成立しない条件は内部で既定経路へ戻り、理由ログを出す実装は確認できません。選択された attention kernel で一般的な入力・起動エラーがあれば `qsa_decode_attn_slots: unsupported geometry or missing buffers`、`qsa_decode_attn_slots: <CUDA/HIP error>` などを stderr に出し、実装によっては `exit(1)` しますが、本変数専用のエラーではありません。`engine/src/kernels/cuda/qsa_decode_attn.cu:1150-1165,1217-1223`。

## 根拠

- `engine/src/core/verify.cpp:336-339,365-369` — 真偽値の判定と初回評価キャッシュ。
- `engine/src/core/verify.cpp:2140-2189` — batch window 条件、QSA slot group の作成と fallback 条件。
- `engine/src/core/verify.cpp:2200-2216,2420-2447,2470-2562` — group 処理、KV resolve、複数 slot attention、row 単位への fallback。
- `engine/src/core/verify.cpp:4677-4690` — batch graph capture から `record_window` を呼ぶ経路。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:492-505,926-989,1150-1223` — build 条件、pre-75 attention の選択、補助環境変数の優先、slot attention の fallback とエラー。
