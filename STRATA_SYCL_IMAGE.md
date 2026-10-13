# `STRATA_SYCL_IMAGE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。Strata 所有ソースを対象とし、Docker 自体の環境変数やイメージ解決動作は対象外。

## 役割

SYCL エンジンを oneAPI ランタイム入りのコンテナで起動する `sycl/serve/strata-sycl.sh` が、`docker run` に渡すイメージ名を選びます。既定は `strata-sycl-dev` です。SYCL 用サーバーでこのラッパーが実行される場合の設定であり、通常の CUDA/HIP 実行ファイルが読む設定ではありません。

## 値と判定

シェルの `${STRATA_SYCL_IMAGE:-strata-sycl-dev}` 展開を使い、文字列の parse や検証はしません。

| 環境変数の状態 | `docker run` に渡すイメージ引数 |
|---|---|
| 未設定 | `strata-sycl-dev` |
| 設定値が空文字 | `strata-sycl-dev` |
| 空でない文字列 | 設定値そのもの |

空白を含む非空値もダブルクォートされた一つの引数として渡されます。値の妥当性、イメージの存在、タグ形式はこのスクリプトでは検査しません。

## 有効になる条件

`sycl/serve/strata-sycl.sh` を起動したときに使われます。スクリプトは `docker run` を直接実行するため、イメージ引数がコンテナ作成に使われます。`STRATA_SYCL_IMAGE` はこのラッパー自身の設定であり、コンテナに転送する環境変数の列挙対象からは `STRATA_SYCL_*` として除外されています。

## 実行時の詳細

変数はスクリプト実行時に `docker run` のコマンドを組み立てる箇所で展開されます。値をキャッシュする処理や、子のエンジン環境へ同名変数を渡す処理はありません。スクリプトのコメントもこの変数をランタイムイメージ指定として説明しています。

`sycl/setup_intel.py` にある `SYCL_IMAGE = "strata-sycl-dev"` は Python の定数です。この名前の環境変数を読み取るものではなく、`STRATA_SYCL_IMAGE` の別の読み取り箇所でもありません。

## 根拠

- `sycl/serve/strata-sycl.sh:6-9` — ラッパーの設定説明と既定値。
- `sycl/serve/strata-sycl.sh:25-35` — コンテナへ渡す設定の収集。`STRATA_SYCL_*` はこのスクリプト固有設定として除外。
- `sycl/serve/strata-sycl.sh:37-42` — `docker run` のイメージ引数としての展開。
- `sycl/setup_intel.py:37-40` — `SYCL_IMAGE` は定数で、環境からは取得していない。
- `docs/INTEL.md:62-63,72-75,377-384` — SYCL ビルドを `strata-sycl-dev` イメージ上でラッパー経由で実行する説明と serving 設定例。
