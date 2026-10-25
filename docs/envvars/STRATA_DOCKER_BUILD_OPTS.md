# `STRATA_DOCKER_BUILD_OPTS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有ソースにおける環境変数の読み取りと処理。

## 役割

`docker/build.sh` が実行する `docker build` に追加の引数を渡します。たとえば `STRATA_DOCKER_BUILD_OPTS='--network host'` なら、通常は `--network` と `host` が追加引数になります。`docker/publish.sh` 自身は値を読みませんが、子として `build.sh` を起動するため、呼び出し元から継承した値はそのビルドにも使われます。

## 値と判定

シェル文字列としての妥当性検査や、Strata 側での Docker オプション解析はありません。`build.sh` の `docker build` コマンドで `${STRATA_DOCKER_BUILD_OPTS:-}` を引用符なしで展開します。

| 環境変数の状態 | `docker build` に渡る追加引数 |
|---|---|
| 未設定 | なし |
| 空文字 | なし（`:-` の既定値が空文字になる） |
| 空でない値 | 現在のシェルの `IFS` による単語分割と pathname expansion（glob 展開）を経た各語 |

したがって、値に含めた空白は引数の区切りになります。値の中の引用符はシェル構文として解釈されず、引数の空白を保護しません。glob パターンは一致するパス名に展開されることがあります。一方、パラメータ展開の結果をシェルが再度構文解析することはないため、値に `;` や `$(...)` を含めてもコマンド区切りやコマンド置換として実行されません。値が空かどうか以外の境界・数値・大文字小文字の判定はありません。

## 有効になる条件

- `docker/build.sh` が `--flavor` と `--engine` の必須引数を満たし、引数処理とビルドコンテキスト作成を通過すること。
- `--ctx-only` を指定した場合、コンテキストを作成した後、`docker build` より前に終了するため、この変数はその実行では使われません。
- `docker/publish.sh` 経由では、対象 flavor の package があり、同スクリプトが `build.sh` を実行した場合に使われます。`publish.sh` は環境を明示的に書き換えず `build.sh` を呼び出します。

Strata は追加引数を検証・除去・上書きせず、`docker build` の固定引数より前に置きます。追加したフラグと固定引数の組み合わせがどう扱われるか、またそのフラグがビルド結果へ及ぼす意味は Docker CLI 側の仕様に属するため、ここでは Strata の挙動として断定しません。

## 実行時の詳細

`build.sh` の usage コメントには、例として `--network host` が記載されています。実際のコマンドでは、`--no-cache` 用の `$nocache` の後、固定された `--build-arg` 群と tag/context の前に変数を展開します。変数が未設定でも `set -eu` による未設定変数エラーにならないよう `${...:-}` が使われています。

`publish.sh` は各 flavor について `build.sh` を起動し、完了後のイメージ起動確認 (`docker run`) にはこの値を追加しません。環境変数の再読み取りや子プロセスへの明示的なコピーはなく、通常のプロセス環境継承により `build.sh` が参照します。

## 根拠

- `docker/build.sh:1-3,20,22` — 実行シェル、Linux x86_64/Docker の説明、変数の用途、`set -eu`。
- `docker/build.sh:28-43,44-46` — CLI 引数の処理と必須引数チェック。
- `docker/build.sh:98-107` — `--ctx-only` の早期終了、未引用の環境変数展開位置、固定引数を含む `docker build` 呼び出し。
- `docker/publish.sh:27,63-79` — usage 上の説明、flavor ごとの `build.sh` 呼び出しと、その後の `docker run`。
- `docs/DOCKER.md:281-306,322-339` — 手動ビルドと公開用スクリプトの使い方。環境変数の値解析規則や意味は説明していない。
