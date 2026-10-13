# `STRATA_SYCL_NAME`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 同梱のソースコード。外部の Docker 自体の挙動は対象外。

## 役割

SYCL エンジンを oneAPI runtime の Docker コンテナ内で動かす起動ラッパー `sycl/serve/strata-sycl.sh` が、コンテナ名を決めるために使います。エンジンの実行オプションや Strata の計算処理は変更しません。

## 値と判定

Bash の `${STRATA_SYCL_NAME:-strata-sycl-serve}` で読み取ります（`sycl/serve/strata-sycl.sh:18`）。この演算子は変数が未設定、または値が空文字の場合に既定値を使います。

| ホスト側の値 | `docker rm` / `docker run --name` に使う名前 |
|---|---|
| 未設定 | `strata-sycl-serve` |
| 空文字 | `strata-sycl-serve` |
| 空でない文字列 | その文字列をそのまま使用 |

値の trim、文字種チェック、長さチェック、大小文字変換はスクリプトにありません。空白を含む値も変数展開後に `"$name"` として渡されます。

## 有効になる条件

この変数を参照するのは `sycl/serve/strata-sycl.sh` です。SYCL ビルド済みエンジンをサーバーの `exe` として起動するラッパー経路で使われます。通常のエンジン実行や別の serve 経路には、この名前を読む実装は見つかりませんでした。

## 実行時の詳細

スクリプトは決定した名前を使って、まず `docker rm -f "$name"` を実行します。この削除コマンドの出力は捨てられ、失敗しても無視されます。その後の `docker run --rm -i --name "$name" ...` にも同じ名前が渡されます（`sycl/serve/strata-sycl.sh:19,37`）。したがって、既定値では起動のたびに `strata-sycl-serve` という名前が使われ、値を指定すればその名前に置き換わります。

`STRATA_SYCL_*` で始まる変数は、ラッパー環境からコンテナへ転送する環境変数の収集対象から除外されています（`sycl/serve/strata-sycl.sh:26-31`）。このため `STRATA_SYCL_NAME` 自体はコンテナ内のエンジンには渡されず、ホスト側の Docker 起動時にだけ使われます。コンテナ内へ渡す他の環境変数やイメージ、実行バイナリは同じスクリプトで別途処理されます（同: 7-13, 25-41）。

設定値が他の起動中コンテナと重複した場合の結果は、このスクリプトでは扱っていません。起動前の `docker rm -f` は同じ名前を指定しているため、その名前のコンテナを削除対象として Docker に渡します。Docker 側での名前の制約や詳細な結果は説明対象外です。

## 根拠

- `sycl/serve/strata-sycl.sh:9,18-19,37` — 既定値、空値を含む Bash 展開、削除と起動時の名前指定。
- `sycl/serve/strata-sycl.sh:26-31` — `STRATA_SYCL_*` をコンテナへの環境変数転送から除外。
- `docs/INTEL.md:377-389` — `serve/server.py --engine strata` からこのラッパーを `exe` として使う説明。
