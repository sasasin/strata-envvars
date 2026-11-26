# `STRATA_PREFILL_ROUTED_STREAM_DEPTH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_PREFILL_ROUTED_STREAM=1` で有効になる routed stream の issuer が、コピー済みイベントの完了を待つ間に先行してキューへ積むコピー数を指定する。既定値は 16、実効値は 1〜256 である。対象の routed walk はコピー前にその layer の routing 情報が公開されると、chunk 内のどの token も使わない未発行 expert entry を飛ばす。通常の expert streaming 全体や routed stream の opt-in 自体をこの変数単独では有効化しない（`engine/src/prefill/prefill.cpp:4777-4780`、`engine/include/strata/prefill/routed_stream.hpp:30-40, 125-155`）。

## 値と判定

読み取り値を `depth_from` が `std::atoi` で整数化し、1〜256 に clamp する。未設定（`getenv` が null）または空文字だけは 16。空文字以外は変換後に clamp するため、数値として読めない文字列や `0` は 1 になる。`atoi` は先頭の空白と符号を許し、先頭の整数部分だけを読む。文字列全体の妥当性検査や独自エラー処理はない（`engine/include/strata/prefill/routed_stream.hpp:30-40`）。

| 条件 | unset | 設定時に有効になる値 | clamp される値の例 |
|---|---:|---|---|
| 全てのビルド | 16 | 1〜256。例: `1`, `16`, `+8`, ` 8`, `8tail` はそれぞれ 1, 16, 8, 8, 8 | 空文字は 16。`0`, `-4`, `true`, `0anything`, `abc` は 1。`257` や `100000` は 256 |

10 進の整数変換結果を対象にしており、小数・後続文字を含む文字列も全体を拒否しない（例: `3.5` は先頭整数 `3`）。変換不能時は `atoi` の結果 0 が下限 1 に clamp される。`atoi` で表現できない範囲の入力に対する Strata 独自の検査はない（同 `:37-40`）。

## 有効になる条件

- 値が routed walk に適用されるのは、別変数 `STRATA_PREFILL_ROUTED_STREAM` が空でなく `atoi(value) != 0` の場合だけ。これは同じ関数内の static 値で判定される（`engine/include/strata/prefill/routed_stream.hpp:33-34`、`engine/src/prefill/prefill.cpp:4777-4780`）。
- chunk が streamed walk の条件 `m.ring > STAGE`、`T >= stream_all_min()`、`m.src != nullptr` を満たす必要がある。`STAGE` は 8。したがって token 数の固定閾値ではなく、実行時の `stream_all_min()` 以上が条件（`engine/src/prefill/prefill.cpp:321, 4628-4629`）。
- issuer thread が必要なので、`STRATA_PREFILL_ISSUER` が設定され `atoi(value) == 0`（未設定なら issuer は on）で inline issuer になっている経路では使われない。`STRATA_PREFILL_COPY_EVENT_EVERY` が 1 より大きい場合、または `STRATA_PREFILL_COPY_WAIT_DEDUPE` が非ゼロの場合も routed walk は使われない（`engine/src/prefill/prefill.cpp:4757-4767, 4779-4780`、`engine/include/strata/prefill/routed_stream.hpp:42-57`）。これらは depth の値を上書きするのではなく、routed walk 自体を既定 issuer に戻す条件である。
- peer prompt ring（`m.pp != nullptr`）がある場合は routed walk の対象外（同 `engine/include/strata/prefill/routed_stream.hpp:48-57`）。
- `engine/cmake/strata_gpu_engine.cmake` は同じ `prefill.cpp` を GPU prefill library に含め、HIP build ではその library に HIP runtime target をリンクする（`engine/cmake/strata_gpu_engine.cmake:482-488`）。`docs/SETTINGS.md:267` の一覧は NVIDIA と AMD を挙げる。一方、Metal と SYCL の CMake source list にも同じ `prefill.cpp` がある（`engine/metal/CMakeLists.txt:136-146`、`engine/sycl/CMakeLists.txt:304-308`）。この関数内に depth 用の backend / OS / GPU 世代 / build macro 分岐はないため、これらの build で routed walk が実際に実行可能かは、この環境変数の読み取り箇所だけからは断定しない。

## 実行時の詳細

値は `prefill.cpp` 内の function-local `static const int rs_depth` 初期化で `getenv` される。最初にこの箇所へ到達した時点で一度だけ評価され、以後の chunk では cache された値を使うため、実行中に環境を変更しても反映されない。routed stream が有効でない場合もこの static 初期化自体は行われるが、値は walk に渡されない（`engine/src/prefill/prefill.cpp:4777-4780`）。

routed walk は未発行 entry の layer/expert を参照し、router の集計結果でその layer が公開済みかつ expert に routing された token がない場合に限って drop する。drop 判定は entry のコピー発行前に繰り返されるため、発行待ち中に routing が公開された entry も対象になる。コピーする場合は従来と同じ `k % ring` slot へ発行する。depth は直近の最大 `q` コピーについて、`q` 個前のコピーが landed するまで次の発行を待つ上限として使われ、内部でも 1〜256 に clamp される（`engine/include/strata/prefill/routed_stream.hpp:116-155`）。

drop 可能なのは `StreamEntry.job < 0` の entry だけである。`job >= 0` は transient source または非 pinned source の stager job として組み立てられ、routed walk 側では drop 対象にしない。layer ごとの routing 集計後に `RouteGate::publish` される（`engine/src/prefill/prefill.cpp:4688-4718, 4835-4860, 6002-6010`）。

## ログと測定値

depth が有効に使われると、stderr に一度 `strata: STRATA_PREFILL_ROUTED_STREAM=1: a streamed prompt chunk drops the experts no token routes to before they are copied (at most %d copies queued ahead of the link)` が出力され、`%d` は clamp 後の depth になる。routed stream が opt-in されていても条件を満たさない streamed chunk では `strata: STRATA_PREFILL_ROUTED_STREAM=1 is not used: ...` の理由行を一度出すが、depth 自体についての理由・警告はない（`engine/src/prefill/prefill.cpp:4781-4795`）。

有効中に `STRATA_TRACE` が設定されていると（空文字も含め `getenv` が非 null）、chunk ごとにコピー数・drop 数・depth を stderr に出す: `strata trace: routed stream: chunk from token ... (... tokens): ... of ... ring entries copied, ... dropped (no token routes to them), depth ...`（同 `:7730-7739`）。この環境変数の値による性能測定値はソースから確認できないため記載しない。

## 根拠

- `engine/include/strata/prefill/routed_stream.hpp:30-40` — 既定値、整数変換、範囲 clamp。
- `engine/include/strata/prefill/routed_stream.hpp:42-57` — routed walk の適用条件。
- `engine/include/strata/prefill/routed_stream.hpp:116-155` — queue depth、drop 判定、ring slot の walk。
- `engine/src/prefill/prefill.cpp:4628-4629, 4777-4789` — streamed chunk 条件、環境読み取り、cache、有効ログ。
- `engine/src/prefill/prefill.cpp:4688-4718, 4835-4860, 6002-6010` — entry 作成、stager entry の扱い、routing 公開と issuer walk。
- `engine/src/prefill/prefill.cpp:4790-4795, 7730-7739` — 不使用理由と trace 出力。
- `engine/cmake/strata_gpu_engine.cmake:482-488`、`docs/SETTINGS.md:267` — GPU build と設定一覧の backend 表記。
