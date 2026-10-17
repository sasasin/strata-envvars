# `STRATA_REFILL_PARTS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーのバッチ prompt 読み込みで一時的に借りた expert-cache slot を戻すとき、ファイルに mmap された GGUF の expert を一つの blob に組み立ててから転送する代わりに、expert を構成する tensor 片をそれぞれ同じ slot の所定オフセットへ非同期転送します。これにより、Strata のホスト側で行う blob の組み立てと staging buffer への 1 expert 分のコピーを省く経路を選べます。

この設定は `src/program/generate.cpp` のサーバー用 prompt 分割・refill 経路で参照されます。通常の `generate` の単発 batched prefill にある別の lent-slot refill ループ（同ファイル末尾付近）では参照されず、そこでこの変数は効果を持ちません。

## 値と判定

環境変数を `std::atoi` で整数に変換し、変換結果が 0 以外なら有効です。変換対象は文字列全体の厳密な数値検査ではありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（既定） |
| 空文字、数値変換できない文字列、先頭が数値でない文字列 | `atoi` が 0 を返すため無効 |
| `1`、`2`、`-1`、`1suffix` | 変換結果が 0 以外のため有効 |
| `0`、`00`、`0suffix` | 変換結果が 0 のため無効 |

判定結果は `static const bool` に保存されます。サーバー処理中に環境変数を変更しても、最初にこの判定が実行された後は再評価されません。読み取り箇所は `src/program/generate.cpp` の一か所です。

有効判定は最適化の要求にすぎず、実際に tensor 片を転送するには、さらに以下の条件が必要です。

- `STRATA_REFILL_BLOCKING` が未設定である。こちらは値を parse せず、設定の有無で blocking を選ぶ。
- expert source の `blob_parts()` が 1 個以上の片を返す。通常の既定実装は 0 を返す。
- `FileExpertSource` では、GGUF の mapping が残っていて、role ごとの mapping が使え、直接 I/O や I/O prefetch 経路ではなく、対象 layer/expert が有効である。resident complement の実データまたは override がある対象も片を返さない。

条件を満たさず `blob_parts()` が 0 を返した場合は `blob_stable()` で assembled blob を取得し、従来の queued または blocking slot fill を使います。したがって有効値だけでは mmap 片コピーは保証されません。

## 実行時の詳細

サーバー経路では、prompt の batched read に必要な cache slot を借り、その prompt chunk の読み込み後、または verify window を読む前に、借りた slot の内容を戻します。refill 対象ごとに layer/expert 番号を計算し、最適化と非 blocking 条件が成立すれば `blob_parts()` を呼びます。片が返ると各片の `p` から device slot の `at` オフセットへ `cudaMemcpyAsync(..., cudaMemcpyHostToDevice, stream 0)` を投入し、host residency table の当該 entry を元の slot に戻します。片がない場合は assembled blob 全体を同じ slot に queued copy します。

非同期 copy は stage ごとに投入した後、各 stage の cache で `sync_queued()` して完了を待ちます。複数 stage の場合、`STRATA_REFILL_SERIAL` が設定されていなければ、全 stage の copy を先に投入してから順に待機します。refill が終わると residency table を再 upload します。`STRATA_REFILL_PARTS` 自体はログを出しませんが、`--trace` の場合は `strata trace: refilled ...` が stderr に出ます。

片の転送投入が失敗した場合は refill が失敗し、サーバー処理は `ERR refilling a lent slot failed: ...` を stdout に出して終了します。片の長さ合計が slot より大きい場合などは `ExpertCache::fill_slot_queued_parts` がエラー文字列を設定します。片転送に失敗した後で assembled blob 経路へ再試行する処理はありません。

## 適用条件と資料上の範囲

コード上、この分岐に OS/backend 固有の guard はありません。`FileExpertSource` から片を得られる構成かが実質的な条件で、ソースの既定 `blob_parts()` は 0 のため、mapping の片を供給しない source では従来経路になります。`STRATA_REFILL_BLOCKING` を設定すると、こちらは値が空でも設定有無で blocking 扱いとなり、片コピーを試みません。別環境変数の完全な説明は各変数の文書を参照してください。

`docs/STRIX_HALO.md` は、`STRATA_REFILL_PARTS=1` を opt-in とし、HIP/CUDA の GGUF read-in-place 構成で使えると記載しています。同資料は 162 slot で assembled blob と同じ bytes を確認したこと、および gfx1151 の UD-Q4_K_XL / UD-IQ4_XS で測定した prompt 所要時間の差を報告しています。これらは同資料に記載された特定条件の確認・測定値であり、この調査で再測定した値ではありません。実装では `cudaMemcpyAsync` を呼びますが、HIP を含む build での backend API の実体はビルド構成に依存するため、ここでは Strata が要求する転送処理として記述しています。

## 根拠

- `src/program/generate.cpp:12578-12607` — slot を戻す処理、環境値の parse、parts 選択、従来 blob 経路。
- `src/program/generate.cpp:12609-12649,13384-13455` — refill の同期・stage 間順序、window 前と prompt 処理後の呼び出し、失敗時の出力。
- `src/program/generate.cpp:326-329` — `STRATA_REFILL_BLOCKING` の設定有無による判定。
- `include/strata/core/expert_source.hpp:179` — `blob_parts()` の既定実装は 0。
- `src/core/expert_source.cpp:3546-3563` — FileExpertSource が mapping の片を返す条件と read accounting。
- `src/core/expert_cache.cpp:745-775` — 片ごとの device copy と同期処理。
- `src/program/generate.cpp:14981-15006` — 単発 `generate` の別 refill 経路では `STRATA_REFILL_PARTS` を参照しないこと。
- `docs/STRIX_HALO.md:136` — 資料に記載された対象構成、検証・測定条件と値。
