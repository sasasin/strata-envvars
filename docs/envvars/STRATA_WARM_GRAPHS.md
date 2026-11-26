# `STRATA_WARM_GRAPHS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL エンジンの非 serve `generate` が投機デコードに進むとき、Verifier の各窓サイズの graph と、MTP が使われていれば Drafter の graph をループ前に capture するかを切り替える。既定では capture し、`0` で事前 capture を飛ばす。無効時も後続の `Verifier::run()` が窓を初めて実行するときに `capture()` を呼ぶため、Verifier の graph を使わなくなる設定ではない（`engine/sycl/src/program/generate.cpp:13961-13975`、`engine/sycl/src/core/verify.cpp:2384-2398`）。

この読み取りは `engine/sycl/src/program/generate.cpp` にだけある。CUDA/HIP/Metal など他の実装に同名の読み取りは見つからなかった。`--spec` が有効で、生成処理が投機デコード分岐に到達する場合に評価される（`engine/sycl/src/program/generate.cpp:13719-13720,13962-13975`）。

## 値と判定

`std::getenv` の結果について、値全体を parse せず、先頭 byte が文字 `'0'` かだけを見る。したがって未設定または先頭が `'0'` 以外なら有効（事前 capture を実行）、先頭が `'0'` なら無効。大文字小文字、数値形式、真偽語、後続文字の妥当性は検査しない（`engine/sycl/src/program/generate.cpp:13963-13966`）。

| 条件（build / 実行経路） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL の非 serve `generate` が投機デコードに到達 | 有効 | 空文字、`1`、`true`、`false`、` 0`、`x`（先頭が `0` 以外の任意文字列） | `0`、`00`、`0anything` |

空文字は `getenv` が非 null のポインターを返しますが、その先頭 byte は `'0'` ではないため有効です。先頭の空白は除去されず、` 0` も有効です。`0anything` は数値としての妥当性にかかわらず無効です。CLI 引数や別の環境変数による上書き・fallback はありません。`--spec` と `--mtp` はこの機能の有効値を変える設定ではなく、後述の分岐や MTP capture の有無を決めます（`engine/sycl/src/program/generate.cpp:13719-13720,13764-13768,13963-13967`）。

## 有効になる条件

- SYCL 実装であること。同名の実行時読み取りは `engine/sycl/src/program/generate.cpp` にのみ存在する（同 commit の候補名全参照を確認）。
- 非 serve 経路で `spec_pos > 0`、生成済み token 数が `max_new` 未満、かつ EOS 終了でないこと。これらを満たさなければ環境変数の読み取り位置に到達しない（`engine/sycl/src/program/generate.cpp:13717-13720,13963-13965`）。
- 事前 capture を実行するには値が未設定か、設定値の先頭 byte が `'0'` 以外であること。
- `--mtp` を指定していない場合も Verifier の capture は行うが、MTP Drafter の capture は行わない（`engine/sycl/src/program/generate.cpp:13764-13768,13967`）。DFlash2 の場合、その準備・capture はこの判定より前に `df2.prepare()` で行われるため、この変数による抑止対象ではない（`engine/sycl/src/program/generate.cpp:13769-13779`）。
- `STRATA_VERIFY_EAGER` が設定されていると `Verifier::capture()` は graph を作らず `true` を返す。このとき本変数が事前 capture を有効にしていても Verifier graph は作られず、`mtp.warm()` は別途呼ばれる（`engine/sycl/src/core/verify.cpp:2098-2108`、`engine/sycl/src/program/generate.cpp:13965-13973`）。
- `--serve` は別分岐で要求を処理し、終了処理へ進む。`STRATA_WARM_GRAPHS` の読み取りはその分岐を抜けた後にあるため、現行ソースでは serve の要求処理には適用されない（`engine/sycl/src/program/generate.cpp:7168-7180,13283-13298,13962-13965`）。行 13962 のコメントには「A server pays this once per process, not per request」とあるが、同じ `main` の制御フロー上、serve 分岐はこの読み取り位置より前に終わる。従ってそのコメントを serve での適用根拠にはできない。

## 実行時の詳細

値は投機デコード部分へ入った後、関数ブロック内の `static const bool warm_on` 初期化子で最初に一度だけ読み取られる。実行中に環境を変更しても再評価されない。初期化子が真なら、まず `ver.warm(err)` が `T=1..max_t_` の Verifier graph を capture する（`engine/sycl/src/program/generate.cpp:13963-13967`、`engine/sycl/src/core/verify.cpp:3272-3278`）。

さらに `--mtp` がある場合は `mtp.warm(err)` が、`T=1..max_t_` の各値について round と prefill の capture を行い、その後 `j=1..min(max_t_-1,max_drafts_)-1` の step graph を capture する（`engine/sycl/include/strata/core/mtp.hpp:52-59`）。`--mtp` がない場合はこの処理を飛ばす。

値が先頭 `'0'` なら warm 処理を省略し、Verifier の graph は `Verifier::run()` から `capture(T, err)` が必要時に呼ばれる経路に委ねられる（`engine/sycl/src/core/verify.cpp:2384-2398`）。このフラグは token の選択や生成内容を直接変更するコードではなく、capture を先に行うかの分岐である（`engine/sycl/src/program/generate.cpp:13965-13975`）。`STRATA_VERIFY_EAGER` が設定されている場合はその遅延経路でも Verifier graph を作らず、queue 上で body を実行する（`engine/sycl/src/core/verify.cpp:2101-2108`）。

## ログと測定値

warm 処理が成功すると stderr に `strata generate: window and draft graphs captured in %.0f ms` が出る。`STRATA_VERIFY_EAGER` が設定されている場合、Verifier 側は capture を行わず成功を返すため、このログは Verifier graph が実際に作られたことを保証しない（`engine/sycl/src/program/generate.cpp:13966-13973`、`engine/sycl/src/core/verify.cpp:2098-2108`）。capture に失敗すると `strata generate: warm-up capture: %s` を出力して `1` を返す。`%s` は `ver.warm` または `mtp.warm` が設定した `err` で、Verifier の例では `verify: begin capture failed` などがある（`engine/sycl/src/program/generate.cpp:13966-13973`、`engine/sycl/src/core/verify.cpp:2098-2108`）。

無効値で事前 capture を飛ばした場合、この成功・失敗ログはこの分岐からは出ない。`docs/DETAILS.md` にこの変数固有の測定値は見つからなかったため、性能差は記載しない。

## 根拠

- `engine/sycl/src/program/generate.cpp:13717-13720,13759-13779,13961-13975` — 投機デコード条件、Verifier/MTP/DFlash2 の順序、環境値判定、ログと返り値。
- `engine/sycl/src/core/verify.cpp:2098-2108,2384-2398,3272-3278` — Verifier graph の capture と遅延経路。
- `engine/sycl/include/strata/core/mtp.hpp:52-59` — MTP の capture 対象と範囲。
- `engine/sycl/src/program/generate.cpp:7168-7180,13283-13298` — serve 分岐とその終了位置。
