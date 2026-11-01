# `BUILD_DSV41`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象の Strata 作業ツリーは `main...origin/main` で、未コミット変更はありません。対象は Strata 所有ソースと同梱スクリプトであり、外部ライブラリの環境変数動作は扱いません。

## 役割

DGX Spark 向け CUDA engine を構築する `spark/build_engine.sh` が、DeepSeek-V4.1 用の `strata-dsv41` ターゲットを含めるかを選びます。Strata の実行時環境変数ではなく、このシェルスクリプトの実行中に読み取られるビルド用環境変数です（`spark/build_engine.sh:1-15,50-68`）。

## 値と判定

スクリプトは `${BUILD_DSV41:-1}` を文字列 `1` と完全一致で比較します。シェルの `:-` 展開なので、未設定だけでなく空文字も既定値 `1` になります。空白除去、数値変換、真偽値変換、先頭文字判定はありません。

| `BUILD_DSV41` | 判定値 `want_dsv41` | 結果 |
|---|---|---|
| 未設定 | `ON` | DeepSeek-V4.1 engine を含める（既定） |
| 空文字 | `ON` | 未設定と同様に既定値を使う |
| 正確に `1` | `ON` | DeepSeek-V4.1 engine を含める |
| その他すべて（例: `0`, `true`, `01`, `1 `） | `OFF` | DeepSeek-V4.1 engine を含めない |

根拠: `spark/build_engine.sh:50`。

## 有効になる条件

変数を読むスクリプトは `spark/build_engine.sh` です。スクリプト自体が arm64/aarch64 Linux と CUDA 13 toolkit を要求し、条件不一致や必要な `nvcc` がない場合はエラーを stderr に出して終了コード 2 で終了します。これらの事前条件は `BUILD_DSV41` の値に関係なく適用されます（`spark/build_engine.sh:27-43`）。

値が `ON` でも、CMake 側では `STRATA_BUILD_DSV41` が有効かつ `STRATA_HIP_GFX906` でない場合に `strata-dsv41` ターゲットを追加します。Spark スクリプトは CUDA を有効にして CMake を呼び出します。ビルド変数 `STRATA_BUILD_DSV41` はこの CMake オプションであり、`BUILD_DSV41` とは別の名前です（`spark/build_engine.sh:59-68`; `CMakeLists.txt:909-920`）。

## 実行時の詳細

スクリプト開始時に一度環境から値を評価し、`want_dsv41` に保持します。後続の環境変更を再読込する処理はありません。CLI 引数や他の環境変数との優先順位は実装されていません。評価値は `-DSTRATA_BUILD_DSV41=ON|OFF` として CMake に渡されます（`spark/build_engine.sh:50,58-68`）。

`ON` のときは `strata`、`strata_kq`、`strata-dsv41` をビルドし、生成物があれば `out` フォルダーへコピーします。`OFF` のときは既存の build フォルダー内の `strata-dsv41` を先に削除し、`strata` と `strata_kq` だけをビルドします。出力フォルダーも作り直され、DeepSeek engine はコピーされません（`spark/build_engine.sh:63-83`）。

`ON` で、ソースツリーに `.git` と `BUILD_ID` のどちらもない場合は `COMMIT` が必要です。未設定または空の `COMMIT` なら説明を stderr に出して終了コード 2 で終了し、指定されていれば先頭 9 文字を `BUILD_ID` に書きます。この処理は `BUILD_DSV41` が有効な場合だけ通ります（`spark/build_engine.sh:51-54`）。

同梱ラッパー `packaging/build_cuda_linux_aarch64.sh` は `BUILD_DSV41=1` を明示して `spark/build_engine.sh` を起動するため、ラッパー利用時は呼び出し元の `BUILD_DSV41` 値ではなく `1` が渡ります。ラッパーは DeepSeek engine を必須としてパッケージ化します（`packaging/build_cuda_linux_aarch64.sh:32,36-47`）。一方、直接 `spark/build_engine.sh` を呼ぶ場合は上記の既定値と判定が適用されます。

文書 `docs/DGX_SPARK_LINUX.md` も `BUILD_DSV41=0` で DeepSeek-V4.1 部分を除外できると説明しており、スクリプトの判定と一致します（`docs/DGX_SPARK_LINUX.md:63-66`）。この環境変数により Strata 実行時のログや終了動作が変わる実装は確認できません。観測される結果はビルド対象と生成・コピーされるファイルの違いです。

## 根拠

- 環境変数の読み取り・判定、CMake への転送、対象選択と出力コピー: `spark/build_engine.sh:50-68,77-83`
- プラットフォーム・CUDA toolkit の前提と失敗経路: `spark/build_engine.sh:27-43`
- DeepSeek-V4.1 CMake ターゲットの条件: `CMakeLists.txt:909-920`
- 呼び出し元による値の上書きとパッケージ要件: `packaging/build_cuda_linux_aarch64.sh:32,36-47`
- 利用者向け説明との照合: `docs/DGX_SPARK_LINUX.md:63-66`
