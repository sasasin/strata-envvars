# `TAG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`TAG` は Strata の実行バイナリやサーバーの設定ではなく、手動起動する GitHub Actions の `Docker images` workflow 内だけで使われる step 環境変数である。workflow_dispatch の `release_tag` 入力をこの名前で step に渡し、Docker イメージ作成用スクリプトの `--release-tag` 引数へ橋渡しする。workflow は `release_tag` を必須の文字列入力として宣言している（`.github/workflows/docker-images.yml:12-18`）。

## 値と判定

workflow の両 step は `TAG: ${{ inputs.release_tag }}` と設定するため、利用者が `TAG` 環境変数で workflow 入力を上書きする仕組みではない（`.github/workflows/docker-images.yml:55-64,97-104`）。workflow 内で値の parse、大小文字変換、空白除去、範囲検証は行わず、そのまま shell 展開して CLI に渡す。例として `v0.2.7` は入力例として受け渡される。空文字は必須入力として想定されないが、渡された場合は下記の引数検査で失敗する。その他の文字列について tag 形式を検証するコードはここでは確認できず、存在する release/feed の確認へ進む。

| 条件 | 未設定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| workflow の flavor 計画 step | 通常は `release_tag` 入力から設定される。shell は `set -eu` で未設定をエラーにする（`.github/workflows/docker-images.yml:57-64`）。 | 例: `v0.2.7`。入力文字列が `$TAG` として `fetch-engines.py --release-tag` に渡る。 | 例: 空文字。`--release-tag` の値が欠け、`fetch-engines.py` が `--release-tag` と `--source` の一方だけを要求して argparse error にする（`.github/workflows/docker-images.yml:62-64`; `tools/docker/fetch-engines.py:122-140`）。 |
| flavor ごとの publish step | workflow では同じ入力から設定される（`.github/workflows/docker-images.yml:97-104`）。 | 空でない値が引用付き `--release-tag "$TAG"` として `publish.sh` に渡る。 | 空値はスクリプトの `tag` が空のままとなり、`--source` も指定されないため `publish.sh:48` の検査でエラー終了する。 |

`fetch-engines.py` は `--release-tag` を文字列引数として受け、値の真偽で `--source` と排他確認する。release tag 固有の形式検証はこの箇所にはない（`tools/docker/fetch-engines.py:122-140`）。`publish.sh` は空でない tag から先頭の `v` だけを `${tag#v}` で取り除いて既定の image version にし、`--version` が別途指定されればそちらを使う（`tools/docker/publish.sh:32-52`）。workflow 自身は `--version` を渡していない（`.github/workflows/docker-images.yml:97-104`）。

## 有効になる条件

- workflow_dispatch で `Docker images` workflow を手動実行し、必須の `release_tag` 入力を渡すこと（`.github/workflows/docker-images.yml:12-18`）。
- 計画 step は `TAG` を `fetch-engines.py --release-tag` に展開して利用可能な flavor を列挙し、その flavor がなければメッセージを出して終了する（`.github/workflows/docker-images.yml:55-68`）。
- 各 flavor の publish step も同じ入力を `publish.sh --release-tag` に渡す。そこで tag は release の取得元として `fetch-engines.py` に再度引き渡される（`.github/workflows/docker-images.yml:97-104`; `tools/docker/publish.sh:32-48,64-73`）。
- Strata の通常の CLI、サーバー、モデル処理にはこの環境変数を読む箇所が見つからず、これらの実行経路では効果がない。

## 実行時の詳細

workflow の各 step 起動時に GitHub Actions が入力値を `TAG` として設定し、各 step の shell が `$TAG` を展開する。値の取得や cache は Strata プロセス内では行われない。計画 step では未引用の `$TAG` が `args` 文字列に入り、後で word splitting されて Python の引数になる（`.github/workflows/docker-images.yml:57-64`）。publish step では `"$TAG"` として一つの引数に渡す（`.github/workflows/docker-images.yml:97-104`）。

publish スクリプトは `--release-tag` を受けると、特に `--source` がなければ GitHub release download URL の基底値を組み立てる。workflow は `--source` を指定しない（`tools/docker/publish.sh:32-52,64-70`; `tools/docker/fetch-engines.py:124-140`）。値の誤りや release 側の問題に対する取得・検証失敗の詳細は各スクリプトの処理によるものであり、`TAG` 自体に別の Strata 実行時効果はない。

## ログと測定値

性能測定は該当しない。計画 step の `fetch-engines.py` は標準エラーに `feed: <source>` を出す。空の値などで引数検査に失敗すると argparse error で終了する（`tools/docker/fetch-engines.py:45-46,131-146`）。publish script は tag と source の両方が空なら標準エラーに `publish.sh: give --release-tag or --source` を出して status 2 で終了する（`tools/docker/publish.sh:48`）。

`docs/DETAILS.md` に `TAG` の記載はなく、この workflow 用の値について測定値もない。

## 根拠

- `.github/workflows/docker-images.yml:12-18,55-68,97-114` — 手動 workflow 入力、`TAG` の設定と shell 展開。
- `tools/docker/publish.sh:32-53,64-73` — `--release-tag` の解析、必須条件、version 既定値、fetch への引き渡し。
- `tools/docker/fetch-engines.py:122-146` — `--release-tag` 引数と source 排他判定、URL 生成、ログと引数エラー。
