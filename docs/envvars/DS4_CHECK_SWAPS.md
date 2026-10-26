# `DS4_CHECK_SWAPS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 エンジン `strata-dsv41` の expert cache が重みを swap した後、VRAM に入った expert と、swap 元のモデルファイルにあるデータを照合します。モデル読み込みや通常の cache 動作を切り替える設定ではなく、swap のコピー結果を検査して stderr に結果を出す診断用フックです。検査を有効にすると、ファイル読み出し、VRAM からの読み戻し、比較処理が加わります。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 設定あり（空文字を含む） | 有効 |

値の内容は parse せず、`std::getenv("DS4_CHECK_SWAPS") != nullptr` だけで判定します。`1` 以外の文字列や空文字でも有効です。既定値は無効です。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` で DeepSeek V4.1 エンジンをビルドした場合に、この読み取り箇所が実行ファイルに含まれます。通常の Strata エンジンではなく、独立した `strata-dsv41` の実装です。
- エンジンの `--expert-cache` による expert cache が有効な場合に限り、cache worker thread が起動し、実際の swap が処理されます。expert cache が無効ならこの検査は実行されません。

## 実行時の詳細

`DS4_CHECK_SWAPS` はモデル実装の `Impl` インスタンス生成時に一度読み取られ、`check_swaps` に保持されます。プロセス起動後に環境変数を変更しても、既に作成されたインスタンスには反映されません。

cache worker が通常の expert を swap した場合、モデルファイルの expert を再度読み、VRAM に移した入力側のデータ、およびファイルを使わず出力側のコピーを保持する構成ではホスト側コピーも、再配置後の該当領域について `memcmp` で比較します。ファイルから CPU lane が読み直す構成では出力側コピーがないため、入力側だけを検査します。

MXFP4 の swap では、VRAM に移した入力 expert の trellis 3領域をファイルから読み直したデータと比較します。`sw.ram >= 0` の場合は、VRAM から RAM slot に移した出力 expert もモデルファイルと比較します。

検査結果は stderr に出ます。通常の expert では `ds4 cache: layer … expert … in, … out: both match the model file` または末尾が `MISMATCH` の行、MXFP4 では `ds4 cache: layer … expert … in, … out…: matches the model file` または `MISMATCH` の行です。検査不一致を検出しても、この分岐はログを出すだけで swap を取り消したり、処理を終了したりしません。MXFP4 の場合、コピー失敗も `MISMATCH` 側に含まれます。

## 根拠

- `CMakeLists.txt:797-810`: `STRATA_BUILD_DSV41` は既定 OFF で、ON のとき独立実行ファイル `strata-dsv41` に `src/dsv41/ds4_model.cu` を含めます。
- `src/dsv41/ds4_model.cu:1124`: 環境変数の設定有無を `Impl` の `check_swaps` に保存します。
- `src/dsv41/ds4_model.cu:2795-2809`: expert cache 有効時に swap worker を起動します。
- `src/dsv41/ds4_model.cu:6040-6124`: 通常形式の swap と、モデルファイルとの byte 比較および結果ログです。
- `src/dsv41/ds4_model.cu:6131-6182`: MXFP4 の swap、VRAM/RAM コピー比較および結果ログです。
- `docs/DEEPSEEK41.md:67-69`: DeepSeek 用の別エンジンと `STRATA_BUILD_DSV41=ON` によるビルド方法を説明しています。`DS4_CHECK_SWAPS` の値や検査動作を説明する製品文書は確認できませんでした。
