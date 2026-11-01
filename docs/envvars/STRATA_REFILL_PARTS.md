# `STRATA_REFILL_PARTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーの batched prompt 経路で expert-cache の slot を prompt 用に一時貸出しした後、slot を戻す方法を切り替えます。値が有効で、コピーが非同期で、expert source が GGUF の mmap から expert を in-place で読んでいる場合、expert 全体を組み立てた staging buffer 経由で戻す代わりに、GGUF mapping 上の tensor piece を slot の対応位置へ直接キューします。slot の residency を戻し、コピー完了後に residency table を各 device へ再 upload する処理はどちらの方法でも行います。

この変数は、prompt 用に cache slot を貸し出す設定そのものではありません。貸出しがない場合は refill がなく、効果もありません。単発 generate の別 refill 経路は、この変数を参照しません（`src/program/generate.cpp:17685-17815`）。

## 値と判定

設定値は `std::atoi` で整数へ変換し、0 以外なら有効です。文字列全体の検証はありません。

| 値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字、数値に変換できない文字列（例: `true`） | `atoi` が 0 を返すため無効 |
| `0`、または整数変換結果が 0 になる文字列（例: `0abc`） | 無効 |
| 0 以外に変換される文字列（例: `1`, `-1`, `2tail`） | 有効 |

値は関数内の `static const bool` に初回評価結果が保存されます。サーバー処理中に環境を書き換えても再評価されません。加えて `STRATA_REFILL_BLOCKING` が**設定されているだけで**（空文字も含む）piece 直接コピーは使われず、従来の blob 経路になります。これは値を parse するのではなく `getenv(...) != nullptr` で判定されます（`src/program/generate.cpp:454-457,14962-14968`）。

## 有効になる条件

- prompt path が cache slot を借りる設定で、cache と residency table が存在すること。コード上の基本条件は `!o.no_prefill_borrow && !o.expert_profile.empty()` と `d_res != nullptr` です。`--no-prefill-borrow` や `STRATA_PREFILL_BORROW` 等による設定が借用可否を変えます（`src/program/generate.cpp:3427-3440,5228,9454-9462`）。
- 貸し出された slot の refill が発生すること。サーバーの request loop は window を読む前に refill を行います（`src/program/generate.cpp:15914-15932`）。
- `STRATA_REFILL_PARTS` の parse 結果が true で、`STRATA_REFILL_BLOCKING` が未設定であること（`src/program/generate.cpp:454-457,14962-14970`）。
- source が piece を提供すること。`FileExpertSource::blob_parts()` は、GGUF の mapping が開いており、direct/role source・I/O prefetch・unmapped source ではなく、該当 expert が RAM resident copy や override で置き換わっていない場合に、expert の span を返します。piece が得られない場合も通常の `blob_stable()` による blob refill に戻ります（`src/core/expert_source.cpp:4619-4635`）。

したがって、変数を有効にしても、借用がない、blocking refill が指定されている、または source が piece を出せない場合には piece 直接コピーは行われません。実装に OS・GPU 世代によるこの変数自体の追加値判定はありません。Strix Halo `gfx1151` 以外を含む性能上の有効性はソースからは断定できません。

## 実行時の詳細

refill ごとに lent slot を走査し、piece 直接コピーを選んだ場合は `blob_parts()` の戻り値が正なら `fill_slot_queued_parts()` に渡し、residency table の該当行を slot に戻します。piece が得られない場合は `blob_stable()` で通常 blob を取得して `fill_slot_queued()`（blocking 指定時は `fill_slot_blocking()`）へ渡します。非 blocking の通常 blob 経路では `note_async_read()` も呼びます。複数 stage がある場合は、serial 設定がなければ各 stage のコピーを先に queue してから各 cache を同期します。その後、貸し slot があれば residency table を upload します（`src/program/generate.cpp:14963-15024`）。

piece の device 転送は piece ごとの非同期 host-to-device copy で、slot 内の `parts[i].at` 位置へ書き込みます。piece の合計サイズが slot より大きい、slot/piece が不正、CUDA/HIP runtime copy が失敗した場合はエラー文字列を返します。同期失敗も同様に refill 失敗になります（`src/core/expert_cache.cpp:839-869`）。サーバー経路では `ERR refilling a lent slot failed: ...` を stdout に出して処理を終了コード 1 で返します。環境変数専用の有効化・無効化ログはありません。`trace` が有効な場合に限り refill slot 数と所要時間が stderr に出ます（`src/program/generate.cpp:15018-15024,15914-15919`）。

## 根拠

- 候補名の実際の読み取りと parse、refill 分岐: `src/program/generate.cpp:14953-14982`。ソース全体の完全一致検索では、この `std::getenv("STRATA_REFILL_PARTS")` が唯一の読み取り箇所です。
- blocking 条件と初回評価 cache: `src/program/generate.cpp:454-457,14962-14970`。
- 借用条件と server refill 呼び出し: `src/program/generate.cpp:5228,9454-9462,15914-15932`。
- GGUF mapping の piece 提供条件: `src/core/expert_source.cpp:4619-4635`。
- slot への piece copy と同期エラー: `src/core/expert_cache.cpp:839-869`。
- Strata の資料 `docs/STRIX_HALO.md:230,312` は、HIP/CUDA の GGUF in-place 読み込み時にこの切替を説明し、gfx1151 での測定値（UD-Q4_K_XL / UD-IQ4_XS、4K-8K prompt +2.3%〜+3.5%、32K +1.1%）を掲載しています。これは資料記載の測定条件に限る値で、他の GPU やモデルへの一般化はしません。
