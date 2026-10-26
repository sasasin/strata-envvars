# `QA_LAYER`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`qsa_prompt_attn_parity` 検証プログラムが `QA_DUMP` のバイナリ記録から読み込む layer を選びます。通常の Strata エンジンが読む環境変数ではなく、CUDA/SYCL の prompt attention parity 検証用です。`QA_DUMP` が未設定なら `QA_LAYER` は参照されず、挙動に影響しません。

## 値と判定

| 状態 | 選択される layer |
|---|---|
| `QA_DUMP` 設定、`QA_LAYER` unset | `3` |
| `QA_DUMP` 設定、`QA_LAYER` 設定 | `std::atoi()` の結果 |
| `QA_DUMP` unset | 読み取られず、適用なし |

文字列全体の検証はありません。`atoi` は先頭の空白と符号を許し、数値として読める先頭部分を整数に変換します。したがって `4xyz` は `4`、空文字や数字で始まらない文字列は `0` になります。負数も整数として扱われます。大文字小文字による判定はありません。コードに範囲制限や無効値時の fallback はありません。

## 有効になる条件

- `QA_DUMP` が設定され、検証プログラムが dump ファイルを読む経路に入ること。
- CUDA では `qsa_prompt_attn_parity` は `STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` が有効で、CUDA が有効なビルドで作られます。
- HIP では同じソースから `hip_prompt_attn_wmma` がテストビルド内に作られます。SYCL では `qsa_prompt_attn_parity` として作られます。
- `QA_LAYER` に合う記録は、さらに query 数 `nq`、`pos0 + nq == ctx`、selection capacity `cap` も一致する必要があります。一致する記録がなければエラー終了します。

この変数は `QA_DUMP` のファイルパスや検証プログラムのコマンドライン引数（context、queries、repetitions）を置き換えません。

## 実行時の詳細

`run()` 内で `QA_DUMP` を確認した後に `QA_LAYER` を読みます。よって読み取りは検証プログラムの実行時で、`QA_DUMP` の経路に入るたびに行われます。dump ファイルをバイナリ読み込みで走査し、layer 番号が選択値と等しく、query 数・context 終端・capacity も一致した記録を探します。同じ条件の記録が複数あれば、走査中に最後に一致した記録位置を使います。

該当記録が見つかると selection ID を読み込み、2/4/8/16 query 群について重複を除いた読み込み cell 数を計算し、`QA_DUMP overlap: ...` の行を stdout に出します。dump ファイルを開けない場合は `QA_DUMP: cannot open`、一致する記録がない場合は `QA_DUMP: no record for layer ...` を stderr に出して終了コード 2 で終了します。

## 根拠

- `src/kernels/qsa_prompt_attn_parity.cpp:151-182` — `QA_DUMP` の有無、`QA_LAYER` の `atoi` 読み取りと既定値 3、記録の layer/query/context/capacity 条件。
- `src/kernels/qsa_prompt_attn_parity.cpp:184-206` — 条件に合う最後の記録の選択、ID 読み込み、重複 cell の集計と stdout 出力。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:176-207` — SYCL 側にも同じ環境変数読み取りと処理がある。
- `CMakeLists.txt:444-450` — CUDA parity 実行ファイルのビルド条件。
- `CMakeLists.txt:989-994` — HIP テスト内の parity 実行ファイル。
- `sycl/CMakeLists.txt:376-380` — SYCL parity 実行ファイル。

通常のエンジン実行コードには `QA_LAYER` の読み取りはありません。リポジトリ全体での参照は上記 CUDA/SYCL parity ソースの各1箇所です。
