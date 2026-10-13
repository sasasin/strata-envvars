# `STRATA_PIPELINE_SWITCH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` のパイプライン処理をリクエストごとに切り替える、テスト・比較用のファイルパスです。環境変数自体に `pw=...` などを設定するのではなく、その値が指すファイルの本文に `pw=0|1|2`、`theta=...`、`force_miss=...`、`short_read=...` を記述します。これらを用いて同一サーバー内で pipeline の段階、投機開始閾値、意図的な不一致、短い prompt を verify window で読む上限を変えられます。

変数は `STRATA_PIPELINE_DEBUG` を介して読む診断用フックです。通常の利用者向け設定として文書化されたものではありません。

## 値と判定

| 条件 | 動作 |
|---|---|
| `STRATA_PIPELINE_DEBUG` が unset、空文字、または先頭文字が `0` | helper が `nullptr` を返すため、この変数を読まない。 |
| `STRATA_PIPELINE_DEBUG` の先頭文字が `0` 以外 | `STRATA_PIPELINE_SWITCH` を取得する。値はファイル名として使う。 |
| `STRATA_PIPELINE_SWITCH` が unset | 切替ファイルを開かず、起動時設定と既定値を使う。 |
| 値が設定されている | そのパスを開けたリクエストで、最大255 byteの本文から設定項目を検索する。 |

`STRATA_PIPELINE_DEBUG` は `v != nullptr && v[0] != 0 && v[0] != '0'` で判定され、先頭文字だけを見ます。`1` だけでなく `true` や `2` も有効、空文字と `0anything` は無効です。この判定は `pipe_dbg_env()` の最初の呼び出し時に `static const bool` として保存されます。

ファイル本文は文字列全体の形式検証をせず、`strstr` で各キーの最初の出現を探します。値は `atoi` / `atof` / `atoll` で変換され、数値の後ろは検証されません。該当キーがない項目はそのリクエストの初期値を保ちます。

| ファイル項目 | 変換と範囲 | 項目がない場合 |
|---|---|---|
| `pw=` | `atoi` 後に 0〜2 へ clamp | `pipe` が有効なら起動時の `--pipeline-windows` 値、そうでなければ0 |
| `theta=` | `atof` を `float` に変換。コード上の追加 clamp なし | `0.2` |
| `force_miss=` | `atoi` 後に0以上へ clamp | `0` |
| `short_read=` | `atoll` 後に0以上へ clamp | `--short-read` の値（既定64） |

設定ファイルを開けない場合はそのリクエストの値を変更せず、切替ログも出しません。正常に開けた場合は、項目が空でも次の形式で stderr に出力します: `strata pipeline switch: pw=%d theta=%.3f force_miss=%d short_read=%lld`。

## 有効になる条件

- `--pipeline-windows` により起動時に `pipe` が構成済みであることが必要です。これは `--serve`、別々の GPU 上にある複数段の layer split などを要します。切替ファイルの `pw=` は、起動時に pipeline を有効化したり必要な GPU 資源を追加確保したりしません。
- 起動時 `--pipeline-windows 0` などで `pipe` が無効なら、switch ファイル条件の `&& pipe` が偽になり、ファイルは開かれません。起動時の値が1で2を要求しても、decode 用 snapshot などがなければ decode pipeline は動きません。
- `pw=1` は prompt の短い部分を verify window で読む経路に関係します。標準実装では `--pipeline-windows` の有効な2段構成で `STRATA_LOGPOS` が unset の場合に `read_windows_pl()` へ進みます。`pw=2` はこれに加え decode window の重ね合わせを要求しますが、snapshot の用意など追加条件が必要です。
- `short_read=` は各 prompt 範囲について `b-a <= req_short_read` かを判定する値です。ただし `STRATA_CKPT_REREAD` が設定されていれば短い読み込みは無効です。また `sp.embd_rows` に画像等の埋め込み行が含まれる範囲は verify window 経路に入りません。
- decode pipeline は、少なくとも `penalty_last_n` を使うリクエストや coupled draft sampling では serial に戻ります。実装は理由ごとに `strata serve: --pipeline-windows: a request with ... decodes serially` を stderr に一度出します。

## 実行時の詳細

各リクエストの prompt 読み込み処理で `pl_pw`、`pl_theta`、`pl_force_miss` と `req_short_read` を初期化し、`STRATA_PIPELINE_SWITCH` のパスを開きます。環境変数から得るパスは switch 判定箇所の `static const char*` に保存され、プロセス起動後に環境変数を差し替えても再取得されません。一方、ファイルはリクエストごとに `fopen` されるため、同じパスの本文変更は次のリクエストで読み直されます。

読み込みバッファは256 byteで、NUL終端を含めて本文の先頭最大255 byteを読みます。キーは区切りや行頭を要求せず、本文中で最初に見つかった `pw=` 等を使います。従って、無関係な文字列の一部にキー表記が含まれていても値として解釈され得ます。`force_miss=k` は投機窓の連番が `k` の倍数のとき、その窓の最初の予測 token を意図的に変え、rollback 経路を試す用途です。`theta` は投機窓を開始する確率推定値のしきい値として使われます。

`pw=0` は pipeline window を要求せず、`pw=1` は対応する短い prompt 読み込みの pipeline、`pw=2` は decode の投機 window も要求します。これらは既に設定済みの pipeline 能力の範囲でだけ作用し、条件不足では直列経路になります。

## 文書との照合

`docs/MULTI_GPU.md` は `STRATA_PIPELINE_*` の試験・tuning 変数が `STRATA_PIPELINE_DEBUG=1` のときだけ読まれる点を記載していますが、`STRATA_PIPELINE_SWITCH` のファイル形式、本文サイズ、キー変換の細則は説明していません。この報告の値判定と効果は、調査対象 commit の実装を根拠にしています。性能値や品質の測定値はこの変数固有の資料で確認できないため記載していません。

## 根拠

- `src/program/generate.cpp:251-257`: `STRATA_PIPELINE_*` helper と `STRATA_PIPELINE_DEBUG` 判定。
- `src/program/generate.cpp:3391-3431,7470-7478`: 起動時の pipeline 適用条件と実際の `pipe` 条件。
- `src/program/generate.cpp:10646-10679`: prompt 短読み込み判定、switch ファイル読み取り・値変換・ログ。
- `src/program/generate.cpp:10772-10775,11313-11325,11458,11722-11757`: `pw`、`force_miss`、`theta` の利用と pipeline 経路。
- `sycl/src/program/generate.cpp:293-298,9896-9929`: SYCL 側の helper と switch 読み取り。値変換・ログの扱いは標準実装と同じ。
- `docs/MULTI_GPU.md:311-313`: tuning / test 用 `STRATA_PIPELINE_*` 変数と debug gate の文書記述。
