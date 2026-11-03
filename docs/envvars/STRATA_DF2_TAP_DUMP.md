# `STRATA_DF2_TAP_DUMP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DFlash2 が prompt 処理中に受け取る tap batch を、指定ファイルへバイナリで追記する研究・診断用フックです。コメントでは layer-major / chunk-major の同値性検証（DF-08）用とされています。通常の DFlash2 推論設定を切り替える変数ではなく、tap の記録だけを追加します。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | 記録しない |
| 空文字 | 記録しない |
| 空でない文字列 | その文字列をファイルパスとして使用し、tap batch を追記する |
| ファイルを開けない、または device-to-host copy に失敗 | その batch の記録を行わず、エラー表示もしない |

値を数値や真偽値として parse しません。`"0"` や `"false"` も空でないためパス名として扱います。相対パスの場合の基準はプロセスの作業ディレクトリです。ファイルは `"ab"`（追記・バイナリ）で開きます。

記録は各 batch について `int64 pos0`、`int64 rows`、続いて `rows * floats_per_row` 個の `float32` の順です。`floats_per_row` は呼び出し側で `tap layer 数 * n_embd` として渡されます。実装コメントは値部分を `[rows][taps][n_embd]` と記述しています。レコード間の追加区切りやヘッダーは書きません。

## 有効になる条件

- 実行ファイルに DFlash2 が含まれること。CMake は DFlash2 を CUDA または HIP backend のビルドで定義し、Metal / SYCL では定義しないとしています。
- prompt 処理で DFlash2 が使われ、該当する tap callback が設定されること。`strata serve` の callback は multi-GPU の layer split ではなく単一 GPU の経路で設定されます。通常の `strata generate` の prompt 経路にも DFlash2 使用時の callback があります。
- 環境変数が callback 内の最初の読み取り時点で空でないこと。

DFlash2 を使わない実行、対応 backend でない build、または serve の multi-GPU layer-split 経路では、この記録 callback は通りません。CLI 引数によるパス上書きや他の環境変数との優先順位は実装にありません。

## 実行時の詳細

関数内の `static const char*` として `std::getenv` の結果を一度保持します。最初の `df2_tap_dump` 呼び出しで値が固定され、その後プロセス内で環境を書き換えても再評価しません。未設定・空文字・`rows <= 0` の場合は直ちに戻ります。

記録対象 batch は GPU から host vector へ `cudaMemcpyDeviceToHost` でコピーされてからファイルへ追記されます。コピー失敗と `fopen` 失敗は戻り値を確認して何も書かずに戻るだけで、警告や終了にはつながりません。`fwrite` の戻り値も確認しません。callback はその後 `df2.context(...)` の結果を返すため、dump の失敗そのものは DFlash2 context の成否を変更しません。実装には専用ログや CLI 出力はありません。

## 根拠

- `src/program/generate.cpp:192-206`: 研究用途との説明、環境値の取得と cache、空値・行数判定、device-to-host copy、追記形式、失敗時の無言 return。
- `src/program/generate.cpp:11170-11175`: serve で単一 GPU の tap callback に dump を組み込み、multi-GPU 時は別の stage tap 経路を使う条件。
- `src/program/generate.cpp:19353-19358`: 通常の generate prompt 処理で DFlash2 利用時に callback を設定。
- `CMakeLists.txt:429-436`: GPU backend 時に `strata_core` を作り、DFlash2 を CUDA / HIP で定義し、Metal / SYCL build では含めない旨。
- `docs/DETAILS.md`: DFlash2 の関連記述を確認しましたが、この環境変数固有の追加仕様・ログ・測定値は見つかりませんでした。
