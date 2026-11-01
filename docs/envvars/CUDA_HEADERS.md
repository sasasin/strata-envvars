# `CUDA_HEADERS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`CUDA_HEADERS` は、CUDA ソースを SYCLomatic (`dpct`) で移行する同梱開発スクリプト `sycl/tools/migrate.sh` が CUDA SDK ヘッダーの場所を指定するために読む変数です。Strata エンジンの実行時設定ではありません。通常のエンジン実行、サーバーモード、モデル処理がこの値を読む箇所は確認できませんでした。

## 値と判定

スクリプトは Bash の `${CUDA_HEADERS:-/cuda-headers/include}` で値を設定します。

| 状態 | `hdr` の値 |
|---|---|
| 未設定 | `/cuda-headers/include` |
| 空文字 | `/cuda-headers/include` |
| 空でない値 | 指定された文字列をそのまま使用 |

空白除去、パス正規化、存在確認、ヘッダー内容の検査はこの値の代入時には行いません。CLI の位置引数は移行元リポジトリと出力先を指定しますが、ヘッダーパスを上書きしません。`CUDA_HEADERS` の範囲制限や無効値向け fallback はなく、空でない文字列はパスとして後続コマンドへ渡されます。

## 有効になる条件

この変数が使われるのは Bash で `sycl/tools/migrate.sh` を実行する場合です。CUDA/SYCL のエンジン実行時、OS 分岐、ビルド macro、サーバー起動や通常の CLI による有効化条件はありません。Strata の Intel/SYCL 開発資料は、同スクリプトが CUDA ソース用の compilation database を作り `dpct` を実行する移行工程であると説明しています（`docs/INTEL.md:334-339`）。

## 実行時の詳細

スクリプト起動時に一度 `hdr` を決めます。その値は Python に位置引数として渡され、各コンパイルコマンドの `-I` include path として compilation database に記録されます。また `dpct` の `--cuda-include-path` にも同じ値を渡します。従って、Strata が行うのは値の既定化と移行ツールへの引き渡しです。実際にヘッダーを解析する処理は `dpct` 側です（`sycl/tools/migrate.sh:8-10,17-19,29-35,41-43`）。

このスクリプトは `set -euo pipefail` を有効にしていますが、`CUDA_HEADERS` 専用の警告、ログ、独自のエラー処理はありません。空でない不正なパスを指定した場合に後続ツールがどう失敗するかは Strata のコードでは定義されていないため、ここでは断定しません。変数を実行中に変更して再評価する処理や、エンジン子プロセスへの転送もありません。

## 根拠

- 候補一覧には `CUDA_HEADERS` が記載されています（`docs/envvars/000_envvers.md:84`）。全リポジトリを対象とした完全一致検索では、実参照は `sycl/tools/migrate.sh:10` のみでした。
- `sycl/tools/migrate.sh:2-5` はこのスクリプトを CUDA から SYCL への移行用と説明し、`sycl/tools/migrate.sh:8-10` で未設定・空文字時の既定値を選びます。
- `sycl/tools/migrate.sh:17-35,41-43` は `hdr` を compilation database の include path と `dpct` の CUDA include path に渡します。
- `docs/INTEL.md:336-339` は CUDA ヘッダーを `dpct` の解析用に用意し、`migrate.sh` が compilation database の生成と移行を行う手順を記載しています。
