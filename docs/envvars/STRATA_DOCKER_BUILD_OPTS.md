# `STRATA_DOCKER_BUILD_OPTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ツールの環境変数の解釈は対象外。

## 役割

Strata 同梱の Docker image build script `docker/build.sh` が、ホスト環境から受け取った値を `docker build` の追加引数として渡します。Strata の CLI、サーバー、エンジンの実行時設定ではありません。直接 `docker/build.sh` を実行する場合と、同スクリプトを呼び出す `docker/publish.sh` の各 flavor build で使われます（`docker/build.sh:20,105-109`、`docker/publish.sh:27,74-75`）。

## 値と判定

スクリプトは値を個別に parse・検証しません。`${STRATA_DOCKER_BUILD_OPTS:-}` を引用符なしで展開するため、unset と空文字は同じく追加引数なしになります。非空値はシェルの field splitting と pathname expansion を受け、結果の各語が `docker build` の引数として挿入されます。たとえば `--network host` は通常2引数になります。値全体を一つの引数として渡す仕組みではなく、引用符を値に含めてもその引用符はシェル構文として再解釈されません。glob 文字がある場合は、スクリプト実行時のカレントディレクトリに合うパスへ展開されることがあります（`docker/build.sh:105-109`）。

| 環境値 | Strata スクリプトの処理 |
|---|---|
| unset / 空文字 | `${...:-}` が空になり、追加引数なし |
| 空白を含む値 | shell の field splitting によって複数語に分かれ得る |
| glob 文字を含む値 | pathname expansion の対象になり得る |
| その他の値 | Strata 側で値域・形式を検証せず、展開後の語をそのまま渡す |

## 有効になる条件

- `docker/build.sh` が `--flavor` と `--engine` などの必須引数を通過し、build context を準備した後に、`--ctx-only` による早期終了をせず `docker build` に到達することが必要です。`--ctx-only` の場合は context を作成した時点で終了し、この環境変数は展開されません（`docker/build.sh:28-46,53-57,99-109`）。
- `docker/publish.sh` は flavor ごとに `build.sh` を起動します。環境変数を置き換えたり専用引数へ変換したりせず、子スクリプトへ通常のプロセス環境として引き継ぎます。`--push` の有無は build 引数の受け渡しに影響しません（`docker/publish.sh:24-27,32-46,74-88`）。
- `docker/build.sh --no-cache` はこの変数とは別に `--no-cache` を追加します。両方を使った場合、`--no-cache`、環境値から展開した語、スクリプトが指定する `--build-arg` 群、tag、context の順で `docker build` に渡ります（`docker/build.sh:26,38,105-109`）。
- `docker/build.sh` は Linux x86_64 と Docker を前提とする説明を持ちますが（`docker/build.sh:2-3`; `docs/DOCKER.md:287-300,346-349`）、この変数自体を読むコードに OS、CUDA/HIP/SYCL flavor、Docker build macro による条件分岐はありません。

## 実行時の詳細

`docker/build.sh` は `#!/bin/sh` のスクリプトで、`set -eu` を設定しています。引数検証、context の用意、`--ctx-only` 判定の後、`docker build` の起動時に環境値を一度展開します。値のキャッシュや後続の Strata プロセスへの転送はありません。`docker/publish.sh` 経由では各 flavor の `build.sh` 起動時にその子プロセスが値を展開します（`docker/build.sh:1,22,53-57,99-109`; `docker/publish.sh:63-75`）。

この環境変数専用の Strata ログや警告はありません。展開後の語が `docker build` の引数列に加わり、Docker CLI の出力を通じて結果が観測されます。`docker build` が非ゼロで終了すれば `set -e` により `build.sh` はそこで終了し、後続の `docker image inspect` と成功メッセージには進みません（`docker/build.sh:22,105-111`）。どの追加引数が受理されるか、受理された Docker オプションが build に及ぼす意味は Docker CLI 側の仕様であり、この文書では Strata の挙動として扱いません。

## 根拠

- `docker/build.sh:20` — この環境変数を Docker build 追加オプションとして説明。
- `docker/build.sh:22,28-46,53-57,99-111` — shell 設定、CLI 検証と context-only 経路、環境値を含む `docker build` 呼び出し、および失敗時・成功時の後続処理。
- `docker/publish.sh:27,63-75` — publish script から flavor ごとに `build.sh` を起動する経路。
- `docs/DOCKER.md:287-300,312-343,346-349` — Docker image の build と publish の用途、対応する実行環境の説明。
