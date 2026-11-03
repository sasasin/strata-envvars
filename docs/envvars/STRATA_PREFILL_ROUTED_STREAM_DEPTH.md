# `STRATA_PREFILL_ROUTED_STREAM_DEPTH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_PREFILL_ROUTED_STREAM=1` で有効にした routed prompt stream が、コピー完了を待たずに先行して発行できるコピー数の上限を指定します。値が大きいほど issuer はコピーを先まで発行でき、小さい値ほどコピー完了を細かく待ちます。この変数だけでは routed stream を有効にしません。

## 値と判定

`src/prefill/prefill.cpp` は `std::getenv()` の値を `routed_stream::depth_from()` に渡します。未設定または空文字列なら既定値 `16` です。それ以外は `std::atoi()` で整数に変換し、`1..256` に clamp します。`atoi` は文字列全体の妥当性を検査しないため、数値の後ろにある文字は変換を止める位置まで無視されます。無効な先頭や数値 `0`、負数は `atoi` の結果が `0` 以下となり、下限の `1` になります。

| 設定値 | `depth_from()` の結果 |
| --- | ---: |
| unset / 空文字列 | 16 |
| `1`、`16`、`256` | その整数 |
| `0`、負数、数値として読めない文字列 | 1 |
| `257` 以上 | 256 |
| `12tail` のように整数の後ろに文字がある値 | 12（数値 prefix を変換） |

整数型で表せないほど大きい値に対する `atoi` の結果は規格上保証されないため、この文書ではその変換結果を定めません。CLI 引数や設定ファイルによる上書き経路はこの読み取り箇所にはありません。

## 有効になる条件

深さは routed stream の適格条件を満たした場合にだけコピー発行へ作用します。

- `STRATA_PREFILL_ROUTED_STREAM` が有効である。これは別の opt-in 変数であり、unset・空文字・`atoi` 結果 0 は off、その他の整数値は on です（`include/strata/prefill/routed_stream.hpp:33-40`）。
- 現在の chunk が `stream_all` である。条件は `m.ring > 8`、`T >= stream_all_min()`、`m.src != nullptr`。`stream_all_min()` は通常 1024 token で、`STRATA_PREFILL_STREAM_MIN` または CPU share の設定で変わり得ます（`src/prefill/prefill.cpp:211,250-260,3565-3570`）。
- threaded issuer が使われる。`STRATA_PREFILL_ISSUER=0` では routed walk は選ばれません（`src/prefill/prefill.cpp:3697-3701,3748`）。
- peer prompt ring がない（単一 GPU の routed walk）。
- `STRATA_PREFILL_COPY_EVENT_EVERY` が 1 で、`STRATA_PREFILL_COPY_WAIT_DEDUPE` が無効である。これらの設定時は routed walk の issuer ではなく通常の issuer を使います（`include/strata/prefill/routed_stream.hpp:42-57`, `src/prefill/prefill.cpp:3702-3721`）。

標準 CMake の prefill 実装は CUDA/HIP backend 条件内にある `src/prefill/prefill.cpp` です（`CMakeLists.txt:431,838-844`）。SYCL 用のコピー `sycl/src/prefill/prefill.cpp` には同じ stream-all 判定はありますが、この環境変数の読み取りも routed walk もありません（同ファイル `2792-2798`）。調査対象では対象名の実読み取りは CUDA/HIP 用実装の 1 箇所だけでした。

## 実行時の詳細

環境値は chunk 処理中の function-local `static const int rs_depth` の初回初期化時に読み取られ、そのプロセス内で再利用されます。したがって、初期化後にプロセス環境を変更しても深さは再評価されません。値は `rs_env`（別の static cache）と独立に読み取られますが、`rs_on` が false なら `rs_depth` は動作に使われません（`src/prefill/prefill.cpp:3718-3721`）。

適格な chunk では、issuer が各 entry を ring slot にコピー発行する前に、ring に空きがあり、かつ直近 `depth` 件のうち最も古いコピーが完了したかを確認します。完了前なら issuer は yield して待ちます。routing の結果は各 layer の router と host grouping の後に `RouteGate` へ公開され、未発行かつ pinned arena から直接コピーする entry のうち、その chunk の token が一つも route しない expert は発行せずに進めます。stager 経由の entry は drop 対象ではありません。深さの制限により変わるのはコピー発行の先行幅で、drop 判定や ring slot の順番を変える値ではありません（`include/strata/prefill/routed_stream.hpp:116-157`, `src/prefill/prefill.cpp:3776-3802,4781-4789`）。

適格な routed walk を初めて使うと stderr に `strata: STRATA_PREFILL_ROUTED_STREAM=1: a streamed prompt chunk drops the experts no token routes to before they are copied (at most %d copies queued ahead of the link)\n` が一度出て、`%d` に clamp 後の深さが入ります。`STRATA_TRACE` が設定されている場合は chunk ごとに copied / dropped 件数と depth の trace が stderr に出ます。routed stream の opt-in が有効で stream-all chunk があっても issuer 条件などを満たさない場合は、stderr の format string `strata: STRATA_PREFILL_ROUTED_STREAM=1 is not used: %s\n` に、該当する理由が入ったメッセージが一度出ます。深さの値自体が不正でもエラー・終了にはならず、変換後 clamp した値を使います（`src/prefill/prefill.cpp:3724-3736,6024-6029`）。

## 根拠

- 値の既定値・変換・範囲制限: `include/strata/prefill/routed_stream.hpp:30-40`。
- 実環境からの読み取り、cache、opt-in との合成: `src/prefill/prefill.cpp:3718-3721`。
- stream-all と threaded issuer の条件: `src/prefill/prefill.cpp:3565-3570,3748`。
- routed walk における発行上限、drop と slot の扱い: `include/strata/prefill/routed_stream.hpp:116-157`; 発行 callback は `src/prefill/prefill.cpp:3776-3802`。
- routing の公開と stderr trace: `src/prefill/prefill.cpp:4781-4789,6024-6029`。
- 現行の設計説明: `docs/DETAILS.md:1119-1127`。ここでは routed stream 自体の要約を確認し、深さの値判定はソース実装を根拠にした。
