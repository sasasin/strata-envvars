# `STRATA_QSA_DUMP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

CUDA と SYCL の prompt prefill 中に、QSA の各層で選択した cell ID をバイナリファイルへ追記する診断用フックです。生成や attention の選択方法を切り替える設定ではなく、選択後の ID をホストへコピーして記録します。用途は `tools/qsa_locality.py` 向けの選択 locality 調査とソースコメントに記されています。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | dump 処理を行わない。 |
| 設定あり（空文字を含む） | 値を出力ファイルパスとして扱い、対象 chunk の選択 ID を記録しようとする。文字列の parse や空文字検査はない。 |

パスは `std::getenv` の戻り値を `static const char*` に保持し、`std::fopen(path, "ab")` で開きます。したがって既存ファイルにはバイナリ append し、存在しないファイルは通常の `fopen` の動作で作成を試みます。空のパスなど fopen に失敗する値では記録されません。失敗時のエラー表示や別パスへの fallback はありません。

記録対象範囲の長さは関連変数 `STRATA_QSA_DUMP_LAST` で決まります。これは `STRATA_QSA_DUMP` が設定されている経路で一度だけ読み、未設定なら `4096`、設定時は `std::atoll` の戻り値です。文字列全体の厳密な数値検証や clamp はなく、空文字・数値に変換できない先頭なら 0、先頭の空白と符号および数値の後ろの文字は `atoll` の変換規則に従います。負値も拒否されません。

## 有効になる条件

- QSA 層を含む CUDA (`src/prefill/prefill.cpp`) または SYCL (`sycl/src/prefill/prefill.cpp`) の prompt batched prefill が実行され、QSA の選択 ID が得られること。
- 現在の chunk が `p0 + T > pos0 + n - last` を満たすこと。`pos0` は prefill 開始位置、`n` は入力 token 数です。

条件判定は chunk 単位です。条件を満たした chunk の全 `T * cap` 個の ID を記録するため、指定した末尾範囲に入った部分だけを切り出す動作ではありません。chunk の境界により、指定範囲より前の query の ID も同じレコードに含まれることがあります。`last=0` では通常、末尾範囲に該当する chunk はありません。`last` に範囲外の大きな値を指定しても値は制限されず、範囲比較にそのまま使われます。

これは QSA prefill の記録フックです。デコードのみの選択や QSA を使わない prefill から記録する経路は、この読み取り箇所にはありません。

## 実行時の詳細

各 QSA 層の block top-k 選択後、対象 chunk なら選択 ID を GPU から `std::vector<int32_t>` へコピーし、CUDA stream または SYCL queue を同期してからファイルへ書きます。各レコードは 32-bit 整数列で、先頭に `{qsa layer index, p0, T, cap}` の4個の `int32`、続いて `T * cap` 個の選択 ID を格納します。実装は `fwrite` の戻り値を検査しません。ファイルを開けない場合もログは出しません。

環境変数値は関数内 static としてキャッシュされます。パスはこの分岐が初めて評価されたときに取得され、その後プロセス内で環境を書き換えても更新されません。末尾長 `last` も dump パスが設定されている場合の初回評価で固定されます。後から `STRATA_QSA_DUMP` を設定しても、初回時に未設定としてキャッシュされていれば有効になりません。

## 根拠

- `src/prefill/prefill.cpp:2046` は `Prefill::run_impl(tokens, n, pos0, ...)` を定義し、`src/prefill/prefill.cpp:2739-2775` でQSA indexer append と block selection を行います。`src/prefill/prefill.cpp:2844-2860` が末尾条件、GPU からのコピー、ヘッダーと ID の append を実装します。
- 対応する SYCL 実装は `sycl/src/prefill/prefill.cpp:3131-3155` です。
- レコード形式と用途は両 prefill 実装のコメント `src/prefill/prefill.cpp:2844-2846`、および `sycl/src/prefill/prefill.cpp:3131-3133` にあります。QSA parity ツール側の `QA_DUMP` は別の環境変数であり、この変数を読み取るコードではありません（`src/kernels/qsa_prompt_attn_parity.cpp:151-167`）。
