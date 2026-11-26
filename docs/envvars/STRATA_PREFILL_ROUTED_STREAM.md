# `STRATA_PREFILL_ROUTED_STREAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

ストリーミングする prompt chunk の issuer を routed walk に切り替える opt-in 変数。各 layer の router が chunk 内で使われる expert を確定した後、まだコピーしていない非 resident expert のうち、その chunk の token が一つも割り当てられないものをコピー対象から外す。対象のコピーは従来と同じ ring slot に入り、consumer の walk は変わらない。通常経路では無効である（`engine/include/strata/prefill/routed_stream.hpp:2-18,33-34`、`engine/src/prefill/prefill.cpp:4777-4780,6008-6010`）。

## 値と判定

`std::getenv` の結果を `routed_stream::enabled_from` に渡し、未設定ポインター、空文字、または `std::atoi` の結果が 0 なら無効、それ以外なら有効とする。文字列全体の検証や真偽語の比較はしない。`atoi` が読む先頭の整数部分で決まり、先頭空白は許容され、整数の後ろの文字は判定されない（`engine/src/prefill/prefill.cpp:4777`、`engine/include/strata/prefill/routed_stream.hpp:33-34`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| すべての当該実行経路 | 無効 | `1`、`2`、`-1`、`1xyz`、` 1` | 空文字、`0`、`0anything`、`true`、`false`、`xyz1` |

`atoi` が数値として読めない先頭は 0 になる。範囲外の整数文字列はコードで検査・処理していないため、その値を有効・無効の規則として保証できない。無効値を理由とする警告や fallback ログはありません。

## 有効になる条件

- この読み取りは `engine/src/prefill/prefill.cpp` の GPU prefill 実装にあり、CUDA/HIP GPU engine が同じソースを組み込む。SYCL は別の `engine/sycl/src/prefill/prefill.cpp` を使い、候補名の読み取りは見つからないため、この変数による routed walk は適用されない（`engine/cmake/strata_gpu_engine.cmake:482`、`engine/cmake/hip_backend.cmake:109`、`engine/sycl/src/prefill/prefill.cpp`）。
- `stream_all` が真であること。実装上は chunk token 数 `T` が `stream_all_min()` 以上、ring サイズ `m.ring` が `STAGE`（8）より大きく、expert source `m.src` がある場合に限る。通常の floor は 1,024 tokens だが、`STRATA_PREFILL_STREAM_MIN` や CPU share により `stream_all_min()` は変わり得る（`engine/src/prefill/prefill.cpp:321,648-658,4628-4629`）。
- threaded issuer が有効であること。`STRATA_PREFILL_ISSUER=0`（`atoi` が 0）なら routed walk は使わず、全 expert をコピーする inline issuer に戻る（`engine/src/prefill/prefill.cpp:4757-4760,4807-4807`、`engine/include/strata/prefill/routed_stream.hpp:48-54`）。
- peer prompt ring を使わないこと。`m.pp != nullptr`（peer device を使う経路）では独自の walk を保つ（`engine/src/prefill/prefill.cpp:4779-4780`、`engine/include/strata/prefill/routed_stream.hpp:48-54`）。
- `STRATA_PREFILL_COPY_EVENT_EVERY` の判定値が 1 で、かつ `STRATA_PREFILL_COPY_WAIT_DEDUPE` が有効でないこと。疎な copy event または重複 wait の省略が有効なら、routed walk が記録しない event を consumer が待つ可能性を避けるため既定 issuer に戻す（`engine/src/prefill/prefill.cpp:4761-4767,4779-4780`、`engine/include/strata/prefill/routed_stream.hpp:42-57`）。
- drop 対象は、まだ issuer が発行していない entry で、layer の route 情報が公開済みかつその expert に token がなく、さらに pinned arena から直接コピーする entry（`en.job < 0`）に限る。stager の job を使う entry は drop しない（`engine/src/prefill/prefill.cpp:4697-4717,4841-4841`、`engine/include/strata/prefill/routed_stream.hpp:72-85,138-155`）。

## 実行時の詳細

環境変数と `STRATA_PREFILL_ROUTED_STREAM_DEPTH` は、prompt chunk の処理が読み取り箇所に初めて到達した時に関数内 `static` として読み取られ、そのプロセス内で cache される。起動後、初回読み取りより前の環境変更は反映され得るが、初回読み取り後の変更は反映されない。CLI 引数による上書きはこの分岐にありません（`engine/src/prefill/prefill.cpp:4777-4778`）。

`STRATA_PREFILL_ROUTED_STREAM_DEPTH` は routed walk 中に link へ先行して queue できる copy 数を決める関連変数で、未設定または空文字は 16、その他は `atoi` 後に 1〜256 へ clamp される（`engine/include/strata/prefill/routed_stream.hpp:30-40`）。この数は本変数を有効化しません。

有効時、各 layer の routing 集計後に `RouteGate` へ expert ごとの token 有無を公開する。issuer は次の entry をコピーする前に route を確認し、未発行かつ drop 可能な unrouted entry を飛ばす。コピーする場合は ring に空きがあり、depth 内の先行 copy が着地済みであることを確認してから、通常と同じ `k % ring` slot へ発行する。drop した entry も `a_issued` の進行対象なので consumer 側の順序は保たれる（`engine/src/prefill/prefill.cpp:4835-4860,6008-6010`、`engine/include/strata/prefill/routed_stream.hpp:116-157`）。

## ログと測定値

- routed walk が有効になると、プロセス内で一度、stderr に `strata: STRATA_PREFILL_ROUTED_STREAM=1: a streamed prompt chunk drops the experts no token routes to before they are copied (at most %d copies queued ahead of the link)` を出す（`engine/src/prefill/prefill.cpp:4783-4789`）。
- 変数が有効で `stream_all` も真だが、issuer・peer ring・copy event/wait 条件で routed walk を使わない場合、理由付きで stderr に `strata: STRATA_PREFILL_ROUTED_STREAM=1 is not used: %s` を一度出す。理由文字列は `engine/include/strata/prefill/routed_stream.hpp:48-54` にあり、判定順は issuer、peer ring、copy event/wait 条件の順（`engine/src/prefill/prefill.cpp:4790-4795`）。`stream_all` 自体が偽ならこの抑止ログは出ない。
- `STRATA_TRACE` が設定されている場合は routed chunk ごとに stderr へコピー数、drop 数、depth を出す。形式は `strata trace: routed stream: chunk from token %lld (%lld tokens): %lld of %zu ring entries copied, %zu dropped (no token routes to them), depth %d`（`engine/src/prefill/prefill.cpp:7730-7739`）。
- `docs/DETAILS.md:1322-1334` は対象条件や RTX 3090 での測定値を記載している。ここでは再測定していないため、測定値を現行 checkout で検証した結果としては扱わない。

## 根拠

- `engine/include/strata/prefill/routed_stream.hpp:33-58` — 有効値の判定、既定 depth、routed walk を止める条件。
- `engine/include/strata/prefill/routed_stream.hpp:63-85,116-157` — route 公開、drop 条件、ring slot と queue depth を使う issuer walk。
- `engine/src/prefill/prefill.cpp:4628-4629,4691-4717,4757-4780` — stream 条件、entry 構築、関連設定と有効判定。
- `engine/src/prefill/prefill.cpp:4830-4860,6002-6010` — issuer の routed walk と layer ごとの route 公開。
- `engine/src/prefill/prefill.cpp:4783-4795,7730-7739` — 有効・抑止・trace ログ。
