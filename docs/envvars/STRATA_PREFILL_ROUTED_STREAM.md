# `STRATA_PREFILL_ROUTED_STREAM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

prompt prefill の streamed chunk で、専用 issuer thread が全 expert を順番にコピーする代わりに、各 layer の router が出した routing 情報を見ながら expert をコピーします。chunk 内の token が一つも route しない expert は、まだコピーを発行しておらず、安定した pinned blob を直接コピーする entry なら転送を省きます。コピーは既存の staging ring の同じ entry 番号 `k % ring` の slot に発行されます。これは Strata の prompt prefill 経路の設定で、外部ライブラリや GPU driver が読む変数ではありません。

環境変数を読むのは `Prefill::run_impl()` 内の streamed prompt chunk issuer 経路です。通常は unset が OFF です。`STRATA_PREFILL_ROUTED_STREAM_DEPTH` はこの設定とは別の環境変数で、ON 時に issuer が先行して queue に置けるコピー数を指定します。

## 値と判定

値は `enabled_from()` が `std::atoi()` に渡し、結果が 0 以外なら ON とします。文字列全体の妥当性検査はありません。

| 値 | 判定 |
|---|---|
| 未設定 | OFF（`getenv()` が null） |
| 空文字 | OFF（helper が空文字を先に除外） |
| `0` または `0` で始まる数値文字列 | OFF（`atoi()` の結果が 0） |
| `1` など 0 以外の整数として読める値 | ON |
| `-1` など負の非ゼロ整数 | ON |
| `1tail`、` 1`、`+1` など `atoi()` が先頭から非ゼロ値を変換できる文字列 | ON |
| `true`、`false`、`x1` など数値変換できず 0 になる文字列 | OFF |

したがって `=1` だけが有効値ではありません。大文字小文字の比較や真偽語の解釈はせず、`atoi()` の変換結果だけで判定します。根拠: `include/strata/prefill/routed_stream.hpp:33-34`。

値判定は `static const bool` に保存されます。`Prefill::run_impl()` の最初の chunk で初期化された後、同じプロセス中に環境を変更しても再評価されません。関連する depth も同時に `static const int` へ保存されます。根拠: `src/prefill/prefill.cpp:3718-3719`。

## 有効になる条件

値が ON でも、chunk ごとの `rs_on` は次をすべて満たす場合だけ true です。

- `stream_all` が true。これは `m.ring > STAGE`、chunk token 数 `T >= stream_all_min()`、expert source が存在することを要求します。`STAGE` は 8、`stream_all_min()` の既定値は 1,024 tokens です。`STRATA_PREFILL_STREAM_MIN` または CPU share 用の実行時設定により閾値は変わり得ます。根拠: `src/prefill/prefill.cpp:211,250-260,3570`。
- threaded issuer が使われる。`stream_all` かつ `STRATA_PREFILL_ISSUER` が未設定または `atoi()` が非ゼロのときです。明示的な 0 は inline issuer になり、この設定は使われません。根拠: `src/prefill/prefill.cpp:3697-3701,3748`。
- peer prompt ring context がない（`m.pp == nullptr`）。`--peer-device` の peer ring は独自の issuer walk を使います。根拠: `include/strata/prefill/routed_stream.hpp:48-53,56-58`; `src/prefill/prefill.cpp:3720-3721`。
- `STRATA_PREFILL_COPY_EVENT_EVERY` が 1 で、`STRATA_PREFILL_COPY_WAIT_DEDUPE` が無効。疎な copied event または deduplicated release wait では routed walk が必要とする copy event を発行しないため、既定 issuer に戻ります。根拠: `src/prefill/prefill.cpp:3702-3709,3718-3721`; `include/strata/prefill/routed_stream.hpp:42-58`。

この実装箇所には CUDA runtime 呼び出しがあり、CMake は `src/prefill/prefill.cpp` を `strata_prefill` に含め、CUDA/HIP backend の GPU target から使います。SYCL は CMake 上で別 backend とされ、GPU prefill target のこの実装経路には入りません。OS・GPU 世代・モデル形状による追加の routed-stream 固有判定は見つかりません。根拠: `src/prefill/prefill.cpp:90,3173,3570`; `CMakeLists.txt:16-17,838-844`。

## 実行時の詳細

`run_impl()` は chunk ごとに全非 resident expert の `seq` を layer / expert 順で構成します。各 layer の router が動き、host grouping で expert ごとの token 数を集計した後、`RouteGate::publish()` が「この chunk のいずれかの token がその expert に route したか」を公開します。issuer はその layer の entry を処理するとき、routing が公開済みで、token が route せず、かつ entry が stager job を必要としない場合に限りコピーを省略します。routing がまだ公開されていない entry や、stager job を使う entry はこの条件では drop しません。根拠: `include/strata/prefill/routed_stream.hpp:60-93,136-157`; `src/prefill/prefill.cpp:3633-3658,3776-3801,4781-4789`。

コピーする場合は既存と同じ copy stream に enqueue し、entry `k` に対応する slot `k % ring` の使用完了を待ってから、同 slot の copied event を記録します。consumer 側は既存の `wait_issued` / `wait_copied` を使います。issuer は ring の空きと `depth` 件未満の未完了コピーを守り、直近 `depth` 件の slot のコピー完了も確認してから先行します。根拠: `include/strata/prefill/routed_stream.hpp:116-157`; `src/prefill/prefill.cpp:3780-3801,3861-3885`。

未設定時の fallback は既定 issuer の通常 walk です。CLI 引数による直接の上書きはこの読み取り箇所にはありません。`strata launch --set` 等で環境変数自体を設定する経路の優先順位は、本調査では追跡対象の prefill 実装からは確認していません。

## ログと失敗経路

有効になった最初の chunk で stderr に `strata: STRATA_PREFILL_ROUTED_STREAM=1: ...` を一度出します。値が ON でも `stream_all` の chunk があり、issuer / peer / copy-event 条件により使えない場合は、stderr に `strata: STRATA_PREFILL_ROUTED_STREAM=1 is not used: ...` と理由を一度出します。`STRATA_TRACE` が設定されている場合、有効な chunk の後に copied / dropped entry 数と depth を `strata trace: routed stream: ...` として stderr に出します。根拠: `src/prefill/prefill.cpp:3724-3736,6024-6028`。

このフラグ固有の無効値警告・終了コード・エラー文はありません。issuer の停止は chunk teardown 時の join によるもので、`issue_walk()` が返す stopped 状態を別のエラーとして報告する処理もありません。prefill 自体の他の失敗は既存の呼び出し経路で処理されます。根拠: `include/strata/prefill/routed_stream.hpp:110-114,136-157`; `src/prefill/prefill.cpp:3743-3747,3801`。

`docs/DETAILS.md:1119-1131` は、既定 stream threshold 1,024 tokens、単一 GPU の threaded issuer、ring コピー数の既定 16、no-route expert の省略と、RTX 3090 上の測定結果を記載しています。測定値は資料記載の Swift IQ3_XXS pack、PCIe 3.0 x16、v0.2.6 release defaults 等の条件付き結果であり、本調査では再測定していません。ソースの値変換は資料上の例 `=1` より広く、`atoi()` の非ゼロ結果を有効として扱います。

## 根拠

- 全参照と環境からの読み取り: `src/prefill/prefill.cpp:3710-3721`; helper: `include/strata/prefill/routed_stream.hpp:28-58`。
- streamed chunk の条件と threshold: `src/prefill/prefill.cpp:211,250-260,3570-3571`。
- issuer 条件と depth-limited walk: `src/prefill/prefill.cpp:3697-3721,3748-3758,3771-3802`; `include/strata/prefill/routed_stream.hpp:116-157`。
- layer ごとの route 公開と consumer の grouping: `src/prefill/prefill.cpp:4781-4789`。
- ログと資料: `src/prefill/prefill.cpp:3724-3736,6024-6028`; `docs/DETAILS.md:1119-1131`。
