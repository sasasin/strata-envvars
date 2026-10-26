# `QA_DUMP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

`qsa_prompt_attn_parity` 診断プログラムが、Strata エンジンの `STRATA_QSA_DUMP` 出力から QSA の選択セルを読み込むための入力ファイル名です。読み込んだ選択について、隣接 query 間で重複する KV cell 数を集計して標準出力に表示します。Strata エンジン本体は `QA_DUMP` を参照しません。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | ファイルを開かず、この追加の overlap 集計を行わない。 |
| 空文字を含む設定値 | `getenv()` は非 null なので `fopen("", "rb")` を試す。開けなければ stderr に `QA_DUMP: cannot open` を出して終了コード 2 で終了する。 |
| パスが設定され、ファイルを開ける | バイナリ形式として走査し、実行引数から得た query 数・context 長・選択幅に合う選択記録を読み込む。 |

値は文字列のまま `fopen` に渡されます。数値変換、空白除去、大小文字判定、既定パスはありません。相対パスはプロセスの作業ディレクトリ基準です。

同じプログラムで、読み込む QSA layer は別変数 `QA_LAYER` で選びます。`QA_LAYER` が未設定なら 3、設定されていれば `atoi` の結果です。`atoi` のため、先頭の空白と符号は受け付け、数値として解釈できない先頭部分は 0 になり、数値以降の文字列は無視されます。空文字も 0 です。

## 有効になる条件

- CUDA ビルドでは `STRATA_BUILD_TESTS` が有効、または `STRATA_PARITY_PROMPT_ATTN=ON` の場合に `qsa_prompt_attn_parity` がビルドされます。実行ファイルは合成入力で prompt attention を比較・計測する診断用で、通常の `strata` 実行経路ではありません。
- SYCL 側にも同名ソース由来の parity 実行ファイルがあります。SYCL CMake では `STRATA_SYCL_PARITY=ON`（既定）の構成でビルドされますが、テストとしては登録されません。
- CUDA と SYCL の両ソースで読み取り条件は同じです。GPU 世代などによる `QA_DUMP` の parse 差はありません。
- エンジン側の `STRATA_QSA_DUMP` が記録した値を読む設計です。記録ヘッダーの layer、query 数 `T`、`pos0 + T` と context 長、selection capacity の各値が実行中の診断プログラムと一致する記録を探します。最後に見つかった一致記録の cell 配列を使います。

## 実行時の詳細

`QA_DUMP` は `run()` の合成 selection を作った後に一度読み取られます。処理は次のとおりです。

1. ファイルを `rb` で開き、4 個の `int32`（layer、開始位置 `pos0`、query 数 `T`、capacity）のヘッダーを順に読む。
2. `QA_LAYER`（未設定時 3）、実行引数の query 数 `nq`、context `ctx`、selection capacity `cap` が一致し、さらに `pos0 + T == ctx` となる記録を候補にする。
3. 記録の `T * cap` 個の `int32` cell ID を `ids` に読み込む。複数一致した場合、最後に走査された一致記録が使われる。
4. 2、4、8、16 query のグループについて重複を集計し、`QA_DUMP overlap: ...` を stdout に表示する。

ファイルを開けない場合は `QA_DUMP: cannot open`、条件に合う記録がない場合は `QA_DUMP: no record for layer ...` を stderr に出して終了コード 2 になります。記録後半の cell 配列を完全に読めない場合もコード 2 で終了しますが、その経路には追加メッセージがありません。

記録形式はエンジン側で `STRATA_QSA_DUMP` が追記する `{layer, pos0, T, cap}` と `T*cap` 個の cell ID です。エンジン側で `STRATA_QSA_DUMP_STEPS` も有効にすると各記録に step 配列も続きますが、この parity reader はその配列分を読み飛ばさず、次のヘッダーとして解釈します。そのため、steps 付きの記録が続くファイルでは後続記録の走査が崩れます。単独の一致記録が先頭にある場合は、記録の cell ID を読む位置自体は一致します。

## 根拠

- `src/kernels/qsa_prompt_attn_parity.cpp:1-11,151-182` — 診断実行ファイルの目的、合成入力での実行、`QA_DUMP`/`QA_LAYER` の読み取り、ファイル走査、集計、エラー処理。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:176-207` — SYCL 版の同等処理。
- `CMakeLists.txt:444-450` — CUDA parity 実行ファイルのビルド条件。
- `sycl/CMakeLists.txt:278-281,376-380` — `STRATA_SYCL_PARITY` の有効範囲と、SYCL parity 実行ファイルの登録（ビルドされるがテスト登録はしない旨のコメント）。
- `src/prefill/prefill.cpp:3472-3495` — エンジン側 `STRATA_QSA_DUMP` の追記形式と、任意の steps 配列。
- `rg -n 'QA_DUMP'` による対象 HEAD の全体検索では、実装参照は CUDA/SYCL parity ソースのみです。
