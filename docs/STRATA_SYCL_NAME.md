# `STRATA_SYCL_NAME`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリや Docker 自身の挙動は対象外。

## 役割

同梱 SYCL 起動スクリプト `sycl/serve/strata-sycl.sh` が Docker コンテナ名として使います。このスクリプトは SYCL engine をコンテナ内で実行する server 用ラッパーです。変数はホスト側のスクリプトでのみ使われ、engine やコンテナ内の環境には転送されません。

## 値と判定

シェルの `${STRATA_SYCL_NAME:-strata-sycl-serve}` で値を選びます。

| 状態 | 使用される名前 |
|---|---|
| 未設定 | `strata-sycl-serve` |
| 空文字 | `strata-sycl-serve` |
| 空でない値 | 指定された文字列をそのまま使用 |

値の trim、大小文字変換、形式検査はスクリプト内にありません。値に空白などがあっても引用して Docker の引数に渡します。

## 有効になる条件

`sycl/serve/strata-sycl.sh` が起動されたときに使われます。変数を設定するだけではコンテナ操作は発生しません。通常の CUDA/HIP 実行経路でこのスクリプトが呼ばれる処理は、この実装からは確認できません。

## 実行時の詳細

スクリプトの起動ごとに値を読み、同じ名前を使ってまず `docker rm -f "$name"` を実行します。既存コンテナが残っている場合の掃除を意図した処理で、削除コマンドの失敗は `|| true` により無視します。その後 `docker run --rm -i --name "$name" ...` を実行し、SYCL engine を起動します。従って名前の変更は、掃除対象と新たに起動するコンテナの識別名を変えます。値はシェル変数 `name` に入り、コンテナ内へ渡す `envs` の生成では `STRATA_SYCL_*` が対象外になるため、子 engine には引き継がれません。

## 根拠

- `sycl/serve/strata-sycl.sh:2-5`: server 用の SYCL engine 起動ラッパーであること。
- `sycl/serve/strata-sycl.sh:9,21`: 文書上の既定値と実際の unset/空文字 fallback。
- `sycl/serve/strata-sycl.sh:22,42`: 名前を使う既存コンテナ削除と `docker run --name`。
- `sycl/serve/strata-sycl.sh:29-38`: `STRATA_SYCL_*` を子コンテナの環境変数転送から除外。
