# `STRATA_QSA_DUMP_LAST`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点、HEAD の commit 日付は 2026-10-12）。外部ライブラリの環境変数は対象外。

## 役割

QSA の prompt prefill で、各 layer が選んだセル ID をダンプする位置範囲の末尾を指定します。これは診断用データ出力の範囲指定で、QSA の選択や attention の計算方法は変えません。

この変数だけではダンプは始まりません。`STRATA_QSA_DUMP` が設定されている場合に限り、ダンプ対象の判定に使われます。CUDA/HIP 側の `src/prefill/prefill.cpp` と SYCL 側の `sycl/src/prefill/prefill.cpp` に同じ処理があります。

## 値と判定

| `STRATA_QSA_DUMP_LAST` | 判定結果 |
|---|---|
| unset | `4096` |
| 設定あり | `std::atoll()` で変換した `long long` 値 |

文字列全体の妥当性検査や範囲 clamp はありません。`atoll` の変換規則に従い、先頭の空白と符号は受け付け、数字列の後ろに続く文字は数値変換に使われません。空文字や数字で始まらない文字列は `0` になります。負値も正値と同様に比較へ使われます。

ダンプするかは `p0 + T > pos0 + n - last` で判定します。`last` は「必ず最後の N 位置だけを切り出す」上限ではありません。条件に合った chunk の全 `T` 行を出力するため、境界が chunk の途中にあれば境界より前の行も含まれます。`last` が 0 または負数なら通常この条件を満たさず、正数が prompt 全体より大きい場合は全 chunk が対象になり得ます。

## 有効になる条件

- QSA を含む prompt prefill 経路を実行すること。
- `STRATA_QSA_DUMP` が環境に設定されていること。空文字も「設定あり」として扱われますが、空のファイル名は通常 `fopen` に失敗します。
- 判定対象の chunk が上記の位置条件を満たすこと。

`STRATA_QSA_DUMP` が unset なら、この変数の値は読み取られません。CUDA/HIP 実装では CUDA stream の同期と device-to-host copy、SYCL 実装では queue の待機と device-to-host copy を行ってからファイルへ出力します。そのため、対象 chunk では診断用の同期・転送・ファイル I/O が追加されます。

## 実行時の詳細

`STRATA_QSA_DUMP` と `STRATA_QSA_DUMP_LAST` は、prefill 中の該当コードに初めて到達したとき `static` 変数へ保存されます。設定をプロセス起動後に変更しても、そのプロセスでは再評価されません。先に `STRATA_QSA_DUMP` が unset の状態で初期化されると、後から設定してもダンプは有効になりません。

ファイルは `STRATA_QSA_DUMP` の値をパスとして `ab`（追記・バイナリ）で開きます。各対象 QSA layer / chunk について、先頭に int32 4 個（QSA layer index、chunk の `p0`、行数 `T`、capacity `cap`）、続けて `T * cap` 個の int32 cell ID を書きます。ID 配列は GPU から host へコピーされます。既存ファイルの形式確認や初期化はせず、そのまま追記します。

ファイルを開けない場合はそのレコードを書きませんが、この箇所から警告やエラーは出ません。`fwrite` の戻り値も確認されていません。設定が出力先として意図したファイルに書けたかは、このコードだけでは利用者に通知されません。

コメントは `tools/qsa_locality.py` 用のデータとしていますが、調査対象 HEAD にはそのツールも `STRATA_QSA_DUMP_LAST` の説明も見つかりませんでした。`docs/DETAILS.md` にもこの診断変数の説明や測定値はありません。

## 根拠

- `src/prefill/prefill.cpp:2844-2860`: 環境変数の読み取り、既定値、位置判定、CUDA 側の copy / append 出力。
- `sycl/src/prefill/prefill.cpp:3131-3155`: SYCL 側の同じ判定と出力。
- `src/prefill/prefill.cpp:2142`: `p0` は `pos0 + c0`、`T` は現在の prompt chunk の行数。
- `CMakeLists.txt:589-592`: CUDA/HIP の `strata_prefill` が `src/prefill/prefill.cpp` を含む。
- `sycl/CMakeLists.txt:233-235`: SYCL の `strata_prefill` が対応する prefill 実装を解決して含める。
