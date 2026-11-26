# `STRATA_LOGPOS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_LOGPOS` は serve の prompt 読み込みで verify window を通った各位置について、実際の prompt の次 token を teacher-forced target とする head logits の対数確率などをファイルへ追記する診断・測定用フックです。設定値を数値や `true` / `1` として解釈するのではなく、その文字列を出力パスとして `fopen(path, "ab")` に渡します。CUDA/HIP 系の生成経路と SYCL 経路の `read_windows` で記録し、Metal では同名変数の設定有無により head logits の実行も有効にします（`engine/src/program/generate.cpp:20415-20425,20438-20467`、`engine/sycl/src/program/generate.cpp:11278-11317`、`engine/metal/src/engine/window.cpp:3650-3656`）。

この記録処理は prompt の verify window に限られます。通常の batched prompt read はこの記録箇所を通らず、decode の全 logits を記録するものでもありません。記録対象の window は prompt token を commit し、sampling は無効化して出力を破棄する経路です（`engine/src/program/generate.cpp:20419-20425,20438-20467`）。環境変数の設定はモデルの sampling 設定値を直接変更しませんが、下記のとおり prompt の処理経路と最適化選択には影響します。

## 値と判定

| 条件 | unset | 設定値の例 | 無効・失敗例 |
|---|---|---|---|
| CUDA/HIP・SYCL の serve prompt window | 出力ファイルを開かず、`window_logprobs` を呼ばない | `/tmp/logpos.tsv` のようなパス。文字列全体をそのまま append-binary open に渡す | 空文字、存在しない親ディレクトリ、権限のないパスなどで `fopen` が失敗すると記録しない。失敗を検査・警告するコードはない |
| Metal window | head を通常の `head` 引数に従って実行 | 空文字を含め、環境変数が存在すれば `head || logpos` を true にする | 空文字や開けないパスでも、Metal の head 実行強制は設定有無だけで有効になる |

`getenv` の結果が null かどうかだけで有無を判定します。値が `1`、`true`、大文字小文字、空白、数値として妥当かどうかの検査・変換はありません。パスは `fopen` が受け取る文字列どおりです。ファイルは初回の対象 window で一度だけ静的初期化され、`"ab"` で開くため追記モードです。環境変数の変更を実行中に読み直しません。`fopen` が null でもその null がキャッシュされ、以後再試行しません（`engine/src/program/generate.cpp:20457-20460`、同じ処理の SYCL 版 `engine/sycl/src/program/generate.cpp:11307-11310`、Metal の有無キャッシュ `engine/metal/src/engine/window.cpp:3653-3655`）。

## 有効になる条件

- serve の prompt 区間が verify windows 経由で読み込まれる必要があります。区間長が要求された `short_read` を超える場合、prompt に埋め込み row が含まれる場合、または `STRATA_CKPT_REREAD` が設定されている場合は `windows_ok` が false となり、batched prompt read に進むため、その区間の `STRATA_LOGPOS` 行は出ません（`engine/src/program/generate.cpp:20223-20243`）。
- `STRATA_LOGPOS` が設定されると、二段 pipeline window が有効な場合も `read_windows_pl` へ分岐せず直列 window loop を使います。SYCL も pipeline window 経路を避けます（`engine/src/program/generate.cpp:20415-20425`、`engine/sycl/src/program/generate.cpp:11278-11284`）。設定値が空、または出力ファイルを開けない場合にも、この設定有無による分岐は起きます。
- serve の prompt window 統合（`merge_from`）は `STRATA_LOGPOS` が設定されていると不許可になります（`engine/src/program/generate.cpp:21533-21549`）。
- Metal では window 実行時に設定有無を静的に記憶し、sampling 用 `head` が false の場合も `Window::run` に true を渡して head logits を実行します（`engine/metal/src/engine/window.cpp:3650-3656`）。
- ファイルを開けなかった場合、CUDA/HIP・SYCL の記録呼び出しはスキップされます。コード上、ログやエラーを出す fallback はありません。Metal での head 強制はパスの open 成否と無関係です。

## 実行時の詳細

CUDA/HIP 系と SYCL 系では、各 verify window で `win` に prompt token、`nxt` にその直後の prompt token を用意して `ver.run` します。run 成功後、初回に `STRATA_LOGPOS` を読み、開けた場合に `ver.window_logprobs(nxt, T, q, ...)` を呼んでから window を commit します。そのため、行の position は `q+t`、target は prompt の token `q+t+1` です（`engine/src/program/generate.cpp:20438-20467`、SYCL 対応部 `engine/sycl/src/program/generate.cpp:11292-11317`）。

`window_logprobs` は head logits を host memory にコピーし、target log-probability、argmax token とその log-probability、target/argmax の一致、追加 token の log-probability、追加 token を除いた正規化での target log-probabilityを TSV 行として出力し、flush します。追加 token ID は関連変数 `STRATA_LOGPOS_EXTRA` から `atoi` で読み、未設定時は `248046`。`STRATA_LOGPOS_TOPK` が正のときは上位 token と log-probability も続けて出力します。これらは関連変数の挙動であり、`STRATA_LOGPOS` 自体の値判定ではありません（`engine/src/core/verify.cpp:4435-4466,4482-4521`、SYCL `engine/sycl/src/core/verify.cpp:3105-3158`）。

読み取りは関数内 `static` 初期化で遅延して一度だけ行われます。記録先の `FILE*` も同じく一度だけ開き、各 window の後に flush されます。`fprintf` / `fflush` の戻り値は検査していません。Metal はさらに `window_run` で環境変数の存在を一度だけキャッシュし、head logits の計算を強制します（`engine/metal/src/engine/window.cpp:3650-3656`）。

## ログと測定値

`window_logprobs` が head logits を得られない場合は `window_logprobs: no head logits for this window`、CUDA 系のコピー失敗は `window_logprobs: the head logits copy failed` をエラー文字列にします（Metal コピー失敗も同じ文字列）。呼び出し元は失敗時に serve の stderr へ `strata serve: <error>`、stdout へ `ERR <error>` を出し、通常は当該処理を失敗終了します。SYCL の例外は `window_logprobs: <例外内容>` になります（`engine/src/core/verify.cpp:4441-4465`、`engine/sycl/src/core/verify.cpp:3109-3111,3156-3158`、呼び出し元 `engine/src/program/generate.cpp:21593-21604`）。

ファイルを開けないこと自体については Strata の警告・エラー文言がなく、記録を黙ってスキップします。成功時は TSV を出力するため、標準出力・標準エラーに有効化ログはありません。性能値は記載しません。

## 根拠

- `engine/src/program/generate.cpp:20223-20243` — prompt 区間が window 経由になる条件。
- `engine/src/program/generate.cpp:20415-20425,20438-20467` — 直列経路、prompt target、ファイル open、記録と commit。
- `engine/src/program/generate.cpp:21533-21549,21593-21604` — merge 抑止とエラー観測。
- `engine/sycl/src/program/generate.cpp:11278-11317` — SYCL prompt window 経路。
- `engine/src/core/verify.cpp:4435-4466,4482-4521` — logits 取得、計算、TSV 出力、flush。
- `engine/sycl/src/core/verify.cpp:3105-3158` — SYCL logits 取得、計算、TSV 出力、例外。
- `engine/metal/src/engine/window.cpp:3650-3656` — Metal の head logits 強制。
