# `STRATA_KEY_FILE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Docker イメージ内で、Strata が使う API キーを保存・再利用するファイルのパスを指定します。コンテナの entrypoint は起動後にこのファイルへ現在の preset の API キーを書き、同梱の `strata` ラッパーと health check はそこからキーを読みます。これは Docker スクリプトの設定であり、C++ エンジンや通常のホスト実行の設定ではありません。

## 値と判定

3つの Docker シェルスクリプトすべてで、`KEY_FILE="${STRATA_KEY_FILE:-/data/state/api-key}"` と設定します。このシェル展開では変数が未設定または空文字なら既定値 `/data/state/api-key`、それ以外なら指定文字列がパスになります。数値や真偽値としての parse、正規化、相対パスの拒否はありません。

| `STRATA_KEY_FILE` | 選ばれるパス |
|---|---|
| unset または空文字 | `/data/state/api-key` |
| 空でない値 | その値をそのまま使用 |

## 有効になる条件

`docker/Dockerfile` が entrypoint、health check、ラッパーをイメージに配置します。変数の読み取り箇所はこれらのスクリプトだけです。entrypoint は `strata` 以外の任意コマンドを実行する分岐でも最初にパスを変数へ代入しますが、その分岐後に保存処理へは進みません。別の Strata 起動方法には適用されません。

指定したディレクトリが存在しない、または書き込み不可の場合に entrypoint は親ディレクトリを作成しません。保存のリダイレクトは失敗を抑制され、その後ファイルが空または存在しなければ削除されます。その場合もキー保存の失敗自体では entrypoint を終了しません。既定パスの親 `/data/state` は通常の起動時に作られます。

## 実行時の詳細

entrypoint は `API_KEY` が空で、かつ `API_KEY_FILE` が指定されている場合、そのファイルを読みます。ここで得たキー（またはキー未指定時に launch が生成したキー）は `strata launch` に `--api-key-env STRATA_LAUNCH_KEY` を渡して設定します。launch が成功した後、entrypoint は `umask 077` の subshell で `strata launch --show-key --preset "$PRESET"` の出力を `KEY_FILE` に保存します。コマンドの標準エラーと失敗は抑制され、出力が空なら `KEY_FILE` を削除します。キー未指定の場合は、生成キーを作った旨と `docker exec ... strata launch --show-key ...` で表示する方法をログに出します。子プロセスに値を渡す環境変数ではなく、コンテナ内のファイルパスを変える設定です。

同梱 `strata` ラッパーは、`STRATA_API_KEY` が未設定または空で、ファイルが読み取り可能な場合に限り、その内容を `STRATA_API_KEY` に読み込んで export してから CLI を起動します。既に `STRATA_API_KEY` が非空ならファイルを読みません。ラッパーは `STRATA_URL` が空の場合に `http://127.0.0.1:${PORT:-8080}` も設定します。

health check は `API_KEY` が空なら読み取り可能な `KEY_FILE` の内容を使い、`http://127.0.0.1:${PORT:-8080}/v1/models` へ Bearer 認証付きで問い合わせます。HTTP 200 かつ応答 JSON の `data` が空でない場合のみ成功終了します。例外時は stderr に `not healthy: <例外>` を出して失敗します。ファイルが読めない場合も空キーで要求を試みます。

`STRATA_KEY_FILE` 自体は3スクリプトの開始時に一度展開されます。実行中に環境変数を変更しても、既に起動した各スクリプトが使うパスは切り替わりません。entrypoint がキーを保存できなかったとき、以後のラッパーや health check はそのファイルからキーを得られません。

## 根拠

- `docker/entrypoint.sh:27-33` は既定パスとの選択、`docker/entrypoint.sh:41-44` は非標準コマンドの早期 exec を定義します。
- `docker/entrypoint.sh:150-155,212-213,256-268` は入力キーの優先順位、launch 用環境変数名、子プロセスへのキー受け渡しを示します。
- `docker/entrypoint.sh:280-286` は preset からのキー取得、ファイル保存、失敗時の削除と案内ログを示します。
- `docker/strata-wrapper.sh:1-10` は CLI ラッパーのファイル読み込み条件と URL の既定値を示します。
- `docker/healthcheck.sh:1-17` はキーの選択、`/v1/models` の要求、成功条件と失敗ログを示します。
- `docker/Dockerfile:87-89,126-133` は各スクリプトのイメージ配置、health check と entrypoint の登録を示します。
- `docs/DOCKER.md:126,158-169` は `API_KEY` / `API_KEY_FILE` と既定のキー保存を説明していますが、`STRATA_KEY_FILE` の override は列挙していません。上記のパス override はソースから確認した挙動です。
