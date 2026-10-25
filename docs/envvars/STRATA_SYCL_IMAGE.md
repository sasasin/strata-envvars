# `STRATA_SYCL_IMAGE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリと Docker 自身の環境変数の動作は対象外。

## 役割

SYCL エンジンを serve プロトコル用に起動するラッパー `sycl/serve/strata-sycl.sh` が、`docker run` に渡す実行イメージ名を指定します。これはコンテナ内のエンジン設定ではなく、ホスト側のラッパーが使う値です。同スクリプトは `STRATA_SYCL_*` をコンテナへ転送しないため、この変数もコンテナ環境には渡しません。

## 値と判定

| 状態 | `docker run` に渡すイメージ引数 |
|---|---|
| 未設定 | `strata-sycl-dev` |
| 空文字 | `strata-sycl-dev` |
| 空でない値 | 設定された文字列をそのまま1個の引数として渡す |

`${STRATA_SYCL_IMAGE:-strata-sycl-dev}` というシェルの parameter expansion を使い、数値化、文字列比較、許可リスト検証、前後空白の除去は行いません。したがって、`custom/image:tag` のような値もそのまま使われます。空文字は未設定と同じ既定値になります。

## 有効になる条件

`sycl/serve/strata-sycl.sh` を実行してその `docker run` 呼び出しに到達した場合に使われます。スクリプトは SYCL エンジンを Docker コンテナ内で起動するラッパーとして用意されており、通常の CUDA/HIP エンジン経路には適用されません。値が空でない場合でも、Docker がそのイメージを利用できるかどうかはこのスクリプトでは事前検証しません。

## 実行時の詳細

スクリプトは `/work` への bind mount、デバイスや共有メモリなどの引数を構成した後、`exec docker run ...` のイメージ引数にこの値を置きます。よって実行ごとにホスト環境から評価され、イメージ選択に Strata 独自のキャッシュやフォールバックはありません。`STRATA_SYCL_IMAGE` が未設定または空なら既定の `strata-sycl-dev` を使います。

`docs/INTEL.md` も SYCL エンジンの実行に `strata-sycl-dev` を使うと説明しています。これは既定値と一致します。独自イメージを指定した場合のイメージ内容や Docker 側の取得・実行動作は、Strata ソースからは確定しません。

## 根拠

- `sycl/serve/strata-sycl.sh:6-9`: この変数の用途と既定値を説明するコメント。
- `sycl/serve/strata-sycl.sh:13-16,29-38`: `STRATA_SYCL_*` を転送対象から除外する処理と、他の環境変数をコンテナへ渡す仕組み。
- `sycl/serve/strata-sycl.sh:42-48`: `docker run` の最終引数として `${STRATA_SYCL_IMAGE:-strata-sycl-dev}` を使用。
- `docs/INTEL.md:62-63,88-90`: SYCL ビルドの実行イメージとして `strata-sycl-dev` を記載。
