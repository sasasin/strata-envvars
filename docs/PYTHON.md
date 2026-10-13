# `PYTHON`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリ自身の環境変数の動作は対象外。

## 役割

`PYTHON` は、SYCLomatic が CUDA ソースを解析するための CUDA SDK ヘッダーを NVIDIA の pip wheel から取得・展開する開発用スクリプト `sycl/tools/get-cuda-headers.sh` が使う Python コマンドを指定します。Strata のエンジンやサーバーが参照する設定ではありません。スクリプトは wheel のダウンロード後、wheel 内の `include/` 以下を出力先へ展開します（`sycl/tools/get-cuda-headers.sh:2-23`）。

## 値と判定

スクリプトは `py=${PYTHON:-python3}` と代入します。シェルの `:-` 展開により、`PYTHON` が未設定または空文字なら `python3` を使い、空でない値ならその文字列を使います。数値や真偽値としての検証、実行ファイルの事前確認、無効値に対する別の fallback はありません（`sycl/tools/get-cuda-headers.sh:5`）。

| `PYTHON` | 選ばれるコマンド値 |
|---|---|
| 未設定 | `python3` |
| 空文字 | `python3` |
| 空でない値 | 設定した文字列 |

`$py` は引用符なしでコマンド位置に展開されるため、シェルの単語分割と pathname expansion の対象です。したがって値に空白が含まれる場合は複数の単語に分割され、ワイルドカード文字も展開され得ます。パスに空白を含む単一の実行ファイルを安全に指定する形にはなっていません。この変数を含む文字列の妥当性や、各単語の意味をスクリプトは検査しません（`sycl/tools/get-cuda-headers.sh:5,7,10`）。

## 有効になる条件

この変数の参照は `sycl/tools/get-cuda-headers.sh` 内だけです。スクリプトが実行されなければ効果はありません。スクリプト先頭は `set -euo pipefail` で、選ばれたコマンドを `-m pip download` と wheel 展開用 Python コードの実行に使います。コマンドが見つからない、または処理が失敗した場合は、その失敗を受けてスクリプトが終了します。スクリプト独自の代替 Python 探索やエラー回復はありません（`sycl/tools/get-cuda-headers.sh:3-10`）。

`docs/INTEL.md` は、このスクリプトが NVIDIA pip wheel から CUDA 12.8 ヘッダーを用意する手順の一部であり、dpct が CUDA ソースを解析するために使うものと説明しています（`docs/INTEL.md:166-170`）。この文書は用途の照合に使い、`PYTHON` の値の挙動はスクリプト本体を根拠にしています。

## 実行時の詳細

値はスクリプト起動時に一度シェル変数 `py` に代入されます。`py` は pip wheel のダウンロード（`$py -m pip download ...`）と、各 wheel を展開するインライン Python プログラム（`$py - "$w" "$out/include"`）の両方に使われます。出力先は第1引数、または既定の `$PWD/cuda-headers` です。`PYTHON` をプロセス起動後に変更して再評価する処理、子プロセス用環境への設定、Strata エンジンへの転送はこのスクリプトにありません（`sycl/tools/get-cuda-headers.sh:4-10`）。

## 根拠

- `sycl/tools/get-cuda-headers.sh:2-10` — スクリプトの用途、既定コマンド、wheel ダウンロード。
- `sycl/tools/get-cuda-headers.sh:10-23` — 同じコマンドでインライン Python を実行し、ヘッダーを展開。
- `docs/INTEL.md:166-170` — SYCL 移植手順におけるヘッダー取得スクリプトの用途。
