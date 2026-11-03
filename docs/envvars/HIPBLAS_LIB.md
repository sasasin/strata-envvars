# `HIPBLAS_LIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`tests/dsv41/build_dq_test.sh` の HIP テスト用ビルドで、`gemm` を追加して `dq_test` をリンクするときに、hipBLAS ライブラリの検索先と実行時検索パスとして指定するディレクトリです。これはテスト用ビルド補助スクリプトだけの用途で、通常の Strata 実行経路による読み取りは見つかりませんでした。

## 値と判定

| 状態 | スクリプトが使う値 |
|---|---|
| 未設定または空文字 | `$HIP_ROOT/lib` |
| 空でない値 | 指定値をそのまま `-L` と `-Wl,-rpath,` の引数に使う |

この選択は HIP 側の `LIBS` を作る行でシェルの `${HIPBLAS_LIB:-$HP/lib}` により行われます。数値変換、パス検証、正規化はありません。値が空でない場合の空白を含むパスの扱いは、後続の非引用 `$LIBS` 展開に依存します。

## 有効になる条件

- `MODE` が `hip` であること。`HIP_ROOT` と `HIP_ARCH` は別途必須です。
- `EXTRA` が空白区切りの要素 `gemm` を含むこと。このときだけ `-lhipblas` とともに `HIPBLAS_LIB` の値（または既定の `$HIP_ROOT/lib`）をリンク指定へ追加します。
- `MODE=cuda` の経路では参照されません。`EXTRA` に `gemm` がなければ、HIP 経路でも参照されません。

## 実行時の詳細

ビルドスクリプトのリンク段階でシェルが変数を展開します。値は Strata エンジンへ渡されず、スクリプト内でキャッシュもされません。リンクコマンドの出力は `$OUT/link.log` に保存され、リンク失敗時はその内容を表示して終了コード 1 で終了します。スクリプト独自の `HIPBLAS_LIB` 警告や値の検証処理はありません。

## 根拠

- `tests/dsv41/build_dq_test.sh:1-6` は、このスクリプトが DSV41 のテスト実行ファイルを CUDA または HIP で手動ビルドするものであること、HIP の `gemm` 用 `HIPBLAS_LIB` を案内しています。
- `tests/dsv41/build_dq_test.sh:47-54` は HIP ビルド経路、`HIP_ROOT` の必須指定、`EXTRA` による GEMM ソース追加を示します。
- `tests/dsv41/build_dq_test.sh:63-65` は `gemm` 条件下で `HIPBLAS_LIB` を `-L` と rpath に使い、`-lhipblas` とともにリンクする処理、およびリンク失敗時のログ表示と終了を示します。
- commit 内の `HIPBLAS_LIB` 全参照は `tests/dsv41/build_dq_test.sh:4,64` のみです。Strata の通常実行コード、サーバー、setup、他の helper からの読み取り・転送は見つかりませんでした。
