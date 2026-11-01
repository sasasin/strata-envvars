# `DPCT_EXTRA`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 同梱の CUDA から SYCL への移行スクリプト `sycl/tools/migrate.sh` が、`dpct` の固定オプションに追加の引数を渡すための変数です。エンジンやサーバーの実行時設定ではありません。スクリプトの説明では、移行処理は `strata-sycl-dev` 内で実行する開発用の手順です（`sycl/tools/migrate.sh:1-6,41-47`）。

## 値と判定

値を数値や真偽値として parse せず、シェルの `${DPCT_EXTRA:-}` 展開を使います。

| 環境値 | スクリプトが渡す追加引数 |
|---|---|
| 未設定 | なし |
| 空文字 | なし |
| 空でない文字列 | 展開後の内容を Bash の通常の未クォート展開に従って分割・glob 展開した語を `dpct` の引数として渡す |

したがって `DPCT_EXTRA='--option value'` のように複数語を置けば、それぞれが追加引数になります。値の許可リスト、数値変換、範囲制限、無効値時の fallback はスクリプトにありません。内容が有効な `dpct` オプションか、またそのオプションが何をするかは Strata のコードでは判定しません（`sycl/tools/migrate.sh:41-47`）。

## 有効になる条件

`sycl/tools/migrate.sh` を実行した場合に限り、`dpct` 起動時の引数列へ反映されます。スクリプトは `set -euo pipefail` を指定しており、空でない値は `dpct` の固定引数 `--stop-on-parse-err=false` の後ろに置かれます（`sycl/tools/migrate.sh:7,41-47`）。Strata の通常の CUDA/HIP/SYCL エンジン、CLI、サーバーの実行経路がこの変数を読む箇所はありません。

## 実行時の詳細

スクリプト実行中にシェルが環境値を展開し、`dpct` の引数に組み立てます。Strata 側に値のキャッシュや再読み取り、別プロセスへの明示的な環境転送はありません。`dpct` の標準出力と標準エラーは `tee` で `$out/migrate.log` に記録され、画面には末尾 40 行が流れます。`dpct` が成功すればスクリプトは `MIGRATE EXIT 0` と出力ファイル数を表示します。失敗時は `pipefail` と `errexit` によりパイプラインが失敗し、通常は後続の表示へ進まずスクリプトが終了します（`sycl/tools/migrate.sh:7,41-50`）。

この文書は、`dpct` が追加引数を解釈した後の動作を説明しません。

## 根拠

- `sycl/tools/migrate.sh:1-6` — 同梱移行スクリプトであることと用途。
- `sycl/tools/migrate.sh:7-13` — Bash のエラー設定、スクリプト引数・環境の初期化。
- `sycl/tools/migrate.sh:41-50` — `DPCT_EXTRA` の展開位置、ログ出力、成功後の表示。
