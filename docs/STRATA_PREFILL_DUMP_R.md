# `STRATA_PREFILL_DUMP_R`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

プロンプト prefill の各 chunk から、絶対位置が 64 の倍数となる token の最終 residual 行をバイナリファイルへ書き出します。ソースコメント上の目的は、この経路の A/B 品質比較用です。通常の生成結果を変える設定ではありませんが、該当 chunk ごとに device queue/stream の完了を待ってホストへコピーするため、prefill の実行時間や同期タイミングには影響します。

読み取り箇所は CUDA 系 prefill 実装と SYCL prefill 実装に各 1 箇所あります。Metal の `Prefill::run` は Metal 用 `prompt_run` を呼んで戻るため、この `run_impl` 内の読み取りには入りません。

## 値と判定

値を真偽値や数値として parse せず、`std::getenv()` が null かどうかだけを判定します。設定値そのものを `fopen` のパスとして渡します。

| 環境変数の状態 | 処理 |
|---|---|
| 未設定 | ダンプ処理を行わない。 |
| 設定あり（空文字を含む） | ダンプ処理へ進み、値をファイルパスとして開こうとする。`0`、`false` なども特別扱いせず、その文字列のパスとして使う。 |
| パスを開けない | 何も書かず、その場でエラーを返さない。明示的な警告ログもない。空文字もこのケースになる。 |

## 有効になる条件

- `Prefill::run_impl` が実行され、chunk の処理が `next_ == nullptr` の末尾 stage まで到達すること。layer split の中間 stage は successor に hand-off して `continue` するため、その stage ではこの環境変数を読まない。単一 stage の prefill は末尾 stage に当たる。
- CUDA 系では `src/prefill/prefill.cpp`、SYCL では `sycl/src/prefill/prefill.cpp` の該当実装が対象。リポジトリ全体の完全一致検索では、この2箇所以外に `STRATA_PREFILL_DUMP_R` の読み取りは見つからない。
- 絶対位置 `p0 + t` が 64 の倍数となる行だけを出力する。chunk 内に該当位置がなければ、その chunk からのデータ行はない。ただしファイルを開く処理は行われる。

## 実行時の詳細

判定は static cache されず、末尾 stage の各 chunk で `getenv()` を再実行します。CUDA 実装では `cudaStreamSynchronize(m.cs)`、SYCL 実装では `m.cs->wait()` の後、chunk 内の行をホストにコピーします。したがって、環境変数をプロセス起動時に一度だけ読む設定ではありません。

出力はヘッダーなしのレコード列です。各レコードは、まず位置 `p0 + t` の `int64_t` を1個、その後に `D` 個の `float`（各4 byte）を書きます。現在の実装定数は `N=2560`、`HC=4`、`D=N*HC=10240` です。値はホストのネイティブな整数・浮動小数点表現で書かれます。行の間やファイル先頭に追加の区切り・メタデータはありません。

各 `run_impl` 呼び出しの最初の chunk は `c0 == 0` なので `fopen(path, "wb")` でファイルを新規作成または切り詰め、その呼び出し内の後続 chunk は `"ab"` で追加します。よって後続 chunk は同じ prefill 呼び出し中では追記ですが、新しい `run_impl` 呼び出しの最初の chunk では既存内容を消します。`fopen` の失敗や `fwrite` の戻り値は明示的に報告されません。

この変数名の記載と測定値は `docs/DETAILS.md` では見つかりませんでした。動作の説明は現行ソースの分岐に基づきます。

## 根拠

- `src/prefill/prefill.cpp:118` — residual 行幅 `D=N*HC` と各定数。
- `src/prefill/prefill.cpp:2087-2090,2178-2182` — `run_impl` と chunk offset / 絶対位置の設定。
- `src/prefill/prefill.cpp:4173-4189` — 中間 stage の hand-off、末尾 stage の環境変数判定、同期、位置選択、ファイル形式と open mode。
- `src/prefill/prefill.cpp:4338-4359` — Metal 用 `prompt_run` への分岐と、それ以外の `run_impl` 呼び出し。
- `sycl/src/prefill/prefill.cpp:2101-2105,2217-2221,4455-4475` — SYCL 実装の呼び出し、chunk 設定、同等のダンプ処理。
