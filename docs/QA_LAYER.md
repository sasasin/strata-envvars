# `QA_LAYER`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`qsa_prompt_attn_parity` 診断プログラムが `QA_DUMP` から読む QSA 選択データについて、照合する layer 番号を指定します。通常の Strata engine の推論設定ではありません。この変数だけを設定しても何も起きず、`QA_DUMP` が設定されて診断プログラムの `run()` が呼ばれた場合にのみ参照されます。

## 値と判定

| 状態 | 対象 layer |
|---|---:|
| 未設定 | `3` |
| 設定あり | `std::atoi()` が先頭から変換した整数 |
| 空文字、数字で始まらない文字列 | `0`（`atoi` の結果） |

整数全体の厳密な検証、後続文字の検査、範囲制限はありません。たとえば `5tail` は `5`、`-1` は `-1` として比較されます。値は dump 内の layer 番号と完全一致したときだけ該当記録として扱われます。範囲外の値を指定した場合も、別の layer へ補正されません。

## 有効になる条件

- `QA_DUMP` が未設定でないこと。空文字でも条件自体は成立しますが、空のパスを `fopen()` して開けず、エラー終了します。
- `qsa_prompt_attn_parity` の `run()` 内で `QA_DUMP` の処理に到達すること。
- dump に、指定 layer に加え、実行中の query 数 `nq`、context 終端 `ctx`、選択幅 `cap` が一致する記録があること。

この実行ファイルは本番 engine とは別の診断・性能比較用プログラムです。CUDA 構成ではテストをビルドする場合、または `STRATA_PARITY_PROMPT_ATTN=ON` の場合に target が追加されます。HIP 構成では `STRATA_BUILD_TESTS` が有効な場合に parity target が追加されます。SYCL 側にも同名ソースを解決する target がありますが、該当 CMake コメントでは未登録・未移植の経路として扱われています。

## 実行時の詳細

`run()` ごとに `QA_DUMP` の有無を確認し、設定されていれば `QA_LAYER` を読みます。変数を static cache するコードではなく、各 `run()` 呼び出し時点で評価されます。1プロセスの実行中に環境を変更した場合の挙動は、プロセス環境を変更する別コードがない通常の起動では対象になりません。

選択データの dump を先頭から読み、layer 番号、`nq`、`h[1] + h[2] == ctx`、選択幅 `cap` が一致する記録のデータ位置を覚えます。同じ条件の記録が複数あれば最後の記録を使います。一致記録がない場合は stderr に `QA_DUMP: no record for layer %d, T %lld, ctx %lld` を出して終了コード `2` で終了します。ファイルを開けない場合は stderr に `QA_DUMP: cannot open` を出して同じく `2` で終了します。一致記録が見つかった場合はその選択データを読み込み、2/4/8/16 query グループについて重複の少なさを計算し、stdout に `QA_DUMP overlap: ...` を出します。

## 根拠

- `src/kernels/qsa_prompt_attn_parity.cpp:151-182`: `QA_DUMP` 条件、`QA_LAYER` の既定値 `3`、`atoi`、dump 照合、一致記録読込、出力。
- `src/kernels/qsa_prompt_attn_parity.cpp:346-377`: parity 実行ファイルの引数処理と、複数条件で `run()` を呼ぶ構成。
- `CMakeLists.txt:420-426`: CUDA parity target とビルド条件。
- `CMakeLists.txt:808-813`: HIP parity target がテスト構成で追加される箇所。
- `sycl/CMakeLists.txt:351-355`: SYCL parity target の記述と未登録の説明。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:176-207`: SYCL 側にも同じ `QA_LAYER` 判定と dump 照合処理がある。
- `docs/NVIDIA_V100.md:68-69`: CUDA parity プログラムのビルド・実行例。`QA_LAYER` の追加仕様は記載されていない。
