# `STRATA_SYCL_IMAGE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

SYCL エンジン起動用ラッパー `sycl/serve/strata-sycl.sh` が `docker run` に渡すランタイムイメージ名を指定します。SYCL エンジン本体が読む設定ではなく、Strata のシェルスクリプトが環境から値を展開し、Docker CLI のイメージ引数として渡します。通常の Intel Arc サーバー構成では、このスクリプトがエンジンの `exe` として起動されます。

## 値と判定

| 環境の状態 | `docker run` に渡すイメージ引数 |
|---|---|
| 未設定 | `strata-sycl-dev` |
| 空文字 | `strata-sycl-dev` |
| 空でない文字列 | その文字列をそのまま渡す |

スクリプトは Bash の `${STRATA_SYCL_IMAGE:-strata-sycl-dev}` を使います。これは未設定と空文字の両方で既定値を選びます。文字列の形式や値域の検証、正規化、数値変換、CLI 引数による上書きはありません。したがって、無効なイメージ名を指定した場合も Strata 側で fallback や警告を行わず、その値を `docker run` に渡します。

## 有効になる条件

この値は `sycl/serve/strata-sycl.sh` が実行された場合にだけ使われます。`docs/INTEL.md` はこのラッパーを SYCL エンジンの `exe` として設定するサーバー構成を示しています。CUDA/HIP の通常のエンジン起動や、イメージをビルドする設定値として使われるものではありません。`sycl/setup_intel.py` にも `SYCL_IMAGE = "strata-sycl-dev"` という定数がありますが、この環境変数を読む箇所ではなく、対象スクリプトの Docker ビルド設定ではありません。

## 実行時の詳細

スクリプト起動時に環境変数をシェル展開し、その値を `docker run` のイメージ位置引数として使用します。プロセス内キャッシュはありません。Docker がそのイメージ引数をどう解釈するか、イメージ取得や起動に失敗する条件は Docker 側の動作であり、Strata の挙動としては扱いません。Strata スクリプトはイメージ引数に関する専用ログや事前検査を出しません。`docker run` が失敗すれば `exec` によりそのコマンドの終了結果がラッパーの終了結果になります。

## 根拠

- `sycl/serve/strata-sycl.sh:6-9` は、この変数をランタイムイメージ名、既定値を `strata-sycl-dev` と説明しています。
- `sycl/serve/strata-sycl.sh:42-48` は `docker run` を実行し、47行目で `${STRATA_SYCL_IMAGE:-strata-sycl-dev}` をイメージ引数として渡します。
- `docs/INTEL.md:118-123` は、SYCL サーバー構成で `sycl/serve/strata-sycl.sh` を engine の `exe` にする例を示します。
- `sycl/setup_intel.py:40-43` の `SYCL_IMAGE` は固定文字列で、`STRATA_SYCL_IMAGE` の読み取りではありません。
