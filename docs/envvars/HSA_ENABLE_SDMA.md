# `HSA_ENABLE_SDMA`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリや GPU ドライバー自身による環境変数の解釈は対象外。

## 役割

Strata がこの変数を読む箇所は、HIP ビルドで verifier の診断 trace を開始したときに、環境に設定されている値を stderr に表示する処理です。Strata のソースでは、この値によってコピー方式、検証処理、SDMA の有効・無効を切り替えていません。CUDA ビルドではこの値を表示しません。

## 値と判定

| 状態 | Strata のログ表示 |
|---|---|
| 未設定 | `HSA_ENABLE_SDMA=-` |
| 空文字を設定 | `HSA_ENABLE_SDMA=`（値部分は空） |
| その他の文字列 | `HSA_ENABLE_SDMA=<設定された文字列>` |

真偽値や数値への変換、空白除去、大文字小文字の判定はありません。`getenv()` が返した文字列を `%s` でそのまま表示します。したがって、たとえば `0` と `1` はログ上の文字列として区別されるだけです。

## 有効になる条件

値がログに現れるには、HIP 用にコンパイルされた verifier で `STRATA_VERIFY_TRACE` による trace が有効になり、verifier 初期化中に trace 用領域をまだ確保していないことが必要です。trace 設定は共通 helper が判定し、未設定または空文字、先頭文字が `0` の値では無効、それ以外の非空文字列では有効です。`HSA_ENABLE_SDMA` 自体はこの条件判定には使われません。

## 実行時の詳細

`STRATA_VERIFY_TRACE` の判定結果 `g_trace` はファイルスコープの `const bool` として初期化されるため、一度判定された後にプロセス内で環境を書き換えても trace の有効・無効は変わりません。一方、`HSA_ENABLE_SDMA` は trace 初期化時の `fprintf` 内で `getenv()` されます。未設定のときだけ代替文字列 `-` を渡し、空文字なら空文字を渡します。同じ引数式で値を複数回取得しています。

ログの先頭は `strata verify trace (#649): on; coherent words ...` です。HIP の場合に限り、続けて `HIP_HOST_COHERENT`、`HSA_ENABLE_SDMA`、`GPU_MAX_HW_QUEUES` の現在値を表示します。この変数だけを設定しても trace は有効にならず、設定値を変更しても Strata のログ以外にソース上の動作変更はありません。

`src/program/generate.cpp` とその SYCL 側コピーには、別の `STRATA_HIP_ADAPT_KERNEL_COPY` の説明コメント中で `HSA_ENABLE_SDMA=0` に言及があります。しかし、同コメントは外部ランタイムの動作に関する背景説明であり、Strata が `HSA_ENABLE_SDMA` を設定・解釈する実装ではありません。コメント中の性能値は条件が記載されていないため、本調査では性能効果として断定しません。`docs/DETAILS.md` にこの変数の個別説明は見つかりませんでした。

## 根拠

- `src/core/verify.cpp:220-231` — trace 用 env helper と `g_trace` の初期化。
- `src/core/verify.cpp:918-933` — verifier trace 初期化時のログ。`STRATA_USE_HIP` 条件内で `HSA_ENABLE_SDMA` を表示。
- `sycl/src/core/verify.cpp:90-101,621-635` — SYCL 側の同じ helper とログ実装。
- `src/program/generate.cpp:267-271`、`sycl/src/program/generate.cpp:196-200` — 値への言及は別変数の説明コメント内のみ。
