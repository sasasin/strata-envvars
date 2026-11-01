# `PUSH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。Strata の Git 状態は `main...origin/main` で、未コミット変更は表示されなかった。

## 役割

`PUSH` は Strata の実行ファイルやサーバーの実行時設定ではなく、GitHub Actions の Docker image workflow が一時的に設定する step 環境変数です。workflow_dispatch の `push` boolean 入力を `--push` 引数に変換し、`docker/publish.sh` に渡します。既定は push しないビルドです。

## 値と判定

workflow は `inputs.push && '--push' || ''` で値を作ります。入力は必須の boolean で既定値は `false` なので、通常の workflow 実行で `PUSH` に入るのは次の二値です。

| workflow `push` 入力 | step の `PUSH` 値 | シェル展開・スクリプト引数 |
|---|---|---|
| `false`（既定） | 空文字 | `$PUSH` は引数なしに展開され、ビルドのみ |
| `true` | `--push` | `--push` 引数が渡され、ビルド後に push |

この workflow では任意の文字列や `1` / `0` を `PUSH` に直接渡す入力はありません。`PUSH` を数値や真偽文字列として parse する処理もありません。

## 有効になる条件

- workflow は自動起動されず、`workflow_dispatch` から手動実行します。
- 公開は入力 `push` が `true` のときだけ有効です。`false` の場合、`docker/publish.sh` は Docker push を行わず、`built <image> (not pushed; add --push)` を出します。
- `latest` 入力が `true`（既定）の場合はバージョン付きタグに加えて `latest-<flavor>` タグも作成・push します。`latest=false` ならそのタグの作成・pushを省きます。
- push 有効時は先行する `Log in to ghcr.io` step も実行され、`GITHUB_TOKEN` と `github.actor` でログインします。ログイン失敗時はその後の build/push step に進みません。

## 実行時の詳細

workflow の Docker job は各 flavor ごとに step 環境 `PUSH` を設定し、未引用の `$PUSH` を含むコマンド行で `docker/publish.sh` を起動します。値が空ならシェルの unquoted expansion によって引数がなく、`--push` ならその一語が引数になります。ここで workflow expression が決定した値を引数へ転送するだけで、Strata エンジンへ環境変数を渡す処理はありません。

`publish.sh` は `--push` を受け取るとローカル変数 `push=1` にし、各イメージの build と起動確認が済んだ後に、`docker push <image>:<version>-<flavor>` を実行します。`latest` が有効なら `docker push <image>:latest-<flavor>` も実行し、`pushed ...` を出力します。push が無効なら `built ... (not pushed; add --push)` を出力します。スクリプトは `set -eu` で動作するため、ログイン後の build / 起動確認 / push コマンドが失敗すると、その失敗でスクリプトが終了し、後続処理へ進みません。ビルド対象 flavor が一つもなければエラーを stderr に出して終了コード 3 になります。

この名前への参照は workflow の環境設定とシェル展開のみです。Strata のアプリケーションコード内で `PUSH` を `getenv` / `os.environ` 等から読む箇所、キャッシュする箇所、またはその値を別プロセスへ環境変数として継承させる箇所は見つかりませんでした。したがって、アプリ起動時に `PUSH` を設定しても Strata のアプリ挙動は変わりません。

## 根拠

- `.github/workflows/docker-images.yml:12-28` は手動起動と `push` boolean の既定値 `false` を定義する。
- `.github/workflows/docker-images.yml:91-104` は `push` 時だけ registry login を行い、`PUSH` を `--push` / 空文字へ変換して公開スクリプトを呼ぶ。
- `.github/workflows/docker-images.yml:109-110` は workflow summary に入力値を表示する。
- `docker/publish.sh:27-28,32-47` は環境変数として `STRATA_DOCKER_BUILD_OPTS` のみを記載し、`--push` 引数を `push=1` に変換する。`.github/workflows/docker-images.yml` と `docker/publish.sh` 以外に `PUSH` の完全一致参照は見つからなかった。
- `docker/publish.sh:74-91` はイメージの build・起動確認後の push と、push しない場合の出力、全 flavor がスキップされた場合の終了経路を示す。
