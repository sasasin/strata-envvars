# `SYCL_CACHE_PERSISTENT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata のエンジン本体はこの名前を直接参照していない。SYCL サーバー起動経路では、`sycl/serve/strata-sycl.sh` が環境変数名の接頭辞 `SYCL_` を見て値を Docker 起動環境へ転送する。そのため、この変数の Strata 側で確認できる役割は起動ラッパーを通じた転送であり、値によって Strata 内の計算やモデル設定を分岐させる処理ではない（`sycl/serve/strata-sycl.sh:13-16,33-52`）。

既定イメージを作る `sycl/tools/Dockerfile` は `SYCL_CACHE_PERSISTENT=0` を `ENV` に設定している（`sycl/tools/Dockerfile:1-9`）。この設定はイメージの環境値であり、Strata エンジンが読み取って設定するものではない。キャッシュの意味や GPU driver 側の動作はこの文書の対象外。

## 値と判定

Strata の SYCL ラッパーは文字列を boolean や数値として parse しない。サーバーの engine 子プロセス環境にある値を `${!k}` で取り込み（`sycl/serve/strata-sycl.sh:33-38`）、Docker 引数を作る際に値全体が空文字または厳密に `0` の場合だけ除外する（同 `:39-43`）。

| 条件 | unset | ラッパーが転送する値 | ラッパーが転送しない値 |
|---|---|---|---|
| `strata-sycl.sh` 経由で Docker を起動 | 変数が未設定なら走査対象に現れず、明示的な `-e` は追加されない。標準イメージでは Dockerfile の既定値 `0` が残る | 空文字・`0` 以外の文字列。例: `1`, `true`, `false`, `00`, `0anything`, ` 0` | 空文字と厳密な `0`。例: 空文字、`0` |
| SYCL バイナリを直接起動 | Strata による読み取り・既定値設定なし | 該当なし | 該当なし |

比較はシェルの `case` による文字列全体の一致で、大文字小文字変換、空白除去、数値妥当性検査はない（`sycl/serve/strata-sycl.sh:39-43`）。したがって `false` や `0anything` もラッパーからは転送対象になる。転送されなかった場合に `0` という値が残ることは、既定 `strata-sycl-dev` イメージについて `sycl/tools/Dockerfile:8` が根拠となる。別の `STRATA_SYCL_IMAGE` を指定した場合、そのイメージの既定値はこのリポジトリからは確定できない（`sycl/serve/strata-sycl.sh:46-52`）。

## 有効になる条件

- 転送が行われるのは `sycl/serve/strata-sycl.sh` を engine として使う SYCL サーバー経路である。同スクリプトが `docker run` を実行してコンテナ内で SYCL バイナリを起動する（`sycl/serve/strata-sycl.sh:46-52`）。
- サーバー設定の `env` は `serve/server.py` の `child_env` が親環境を複製した後に適用するため、同名の設定値はホストから継承した値より優先される（`serve/server.py:4428-4441`）。その環境で起動されたラッパーが `SYCL_*` の値を拾う（`sycl/serve/strata-sycl.sh:33-38`）。
- ラッパーに値が渡されても、その値が空文字または厳密な `0` なら Docker の `-e` には含まれない。標準イメージではその結果 `Dockerfile` の `0` が使われる（`sycl/serve/strata-sycl.sh:39-52`; `sycl/tools/Dockerfile:8`）。
- 直接 `build-sycl-aot/strata` を起動する経路では、この値を特別扱いする Strata コードはない。呼び出し元のプロセス環境を Strata が変更・転送するラッパー処理も通らない。

## 実行時の詳細

サーバー起動時に `child_env` が環境を作り、エンジンの実行ファイルとして設定されたラッパーを起動する（`serve/server.py:4428-4441,1160-1165`）。ラッパーは起動時に環境変数名を列挙し、`STRATA_*`, `ONEAPI_*`, `UR_*`, `IGC_*`, `SYCL_*`, `ZES_*` などを `setting` に取り込み、空文字と `0` 以外の値を `docker run -e` に追加する（`sycl/serve/strata-sycl.sh:33-52`）。この値の判定を行う関数内 cache やリクエストごとの再読み込みはない。ラッパー起動後に親プロセスの環境を変更しても、すでに作られたプロセス環境やコンテナ起動引数には反映されない。

CLI 引数との優先順位を Strata が設ける処理はない。サーバー経路では設定 `env` が親環境より優先し、Docker 引数に追加された値はコンテナイメージの同名 `ENV` を上書きする。ラッパーが値を除外したときはイメージ側の環境値が残る（`serve/server.py:4431,4440-4441`; `sycl/serve/strata-sycl.sh:39-52`; `sycl/tools/Dockerfile:8`）。

## ログと測定値

この変数を読み取ったことや転送したことを示す Strata 固有のログ、警告、測定値は確認できない。ラッパーに `set -euo pipefail` があるため、失敗したコマンドでスクリプトはエラー終了するが、この変数専用のエラー処理や文言はない（`sycl/serve/strata-sycl.sh:17,46-52`）。

## 根拠

- `sycl/serve/strata-sycl.sh:13-16,33-52` — 環境名の接頭辞による取り込み、値の除外規則、Docker への転送。
- `sycl/tools/Dockerfile:1-9` — SYCL 開発用イメージにおける `SYCL_CACHE_PERSISTENT=0` の設定。
- `serve/server.py:4428-4441,1160-1165` — 親環境と設定 `env` から engine 子プロセス環境を作り、ラッパーを起動する処理。
