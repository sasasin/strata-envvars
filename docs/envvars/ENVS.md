# `ENVS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリと Docker 自身の挙動は対象外。

## 役割

`ENVS` は `docker/smoke-test.sh` が `docker run` に追加のコマンドライン引数を渡すための補助変数です。使用例では `-e MODEL=...` などのコンテナ環境指定を入れています。Strata のエンジンやサーバーが `ENVS` を設定として読む実装は見つかりませんでした。値を解釈するのは smoke-test スクリプトの Bash で、その後の引数の意味は Docker CLI に渡されます。

## 値と判定

| 状態 | スクリプトの処理 |
|---|---|
| 未設定 | `${ENVS:-}` は空に展開される。`set -u` の未設定変数エラーにはならず、追加引数はない |
| 空文字 | 未設定と同様に空に展開され、追加引数はない |
| 非空文字列 | 引用符なしの展開結果がシェルの語分割とパス名展開を受け、できた各語が `docker run` の引数になる |

値の検証、型変換、許可リスト、長さ制限、無効値時の fallback はありません。展開後の文字列を `eval` で再解釈する処理もありません。したがって値の中に書いた引用符は、展開後の語を再びグループ化する構文にはなりません。例の `ENVS="-e MODEL=IQ3_S -e MODEL_PATH=/models"` は、空白で分かれた語をそのまま追加します。

## 有効になる条件

`docker/smoke-test.sh` を Bash で実行して `docker run` の段階に到達した場合に限り使われます。これは実カード上で Docker image を smoke test するためのスクリプトで、通常の Strata CLI/サーバー設定ではありません。スクリプトは最初のコンテナ作成で `ENVS` を展開します。後段の再起動は `docker start "$NAME"` を呼ぶだけで、`ENVS` を再展開しません。

## 実行時の詳細

スクリプトは `set -u` を有効にした後、`docker run` の引数に固定の `-e API_KEY="$KEY"` を置き、その後に `${ENVS:-}`、`VOLS`、`RUN_FLAGS` の順で展開します。`ENVS` によって生成された語は、ほかの引数とともに `$DOCKER run` に渡ります。スクリプト側では `ENVS` を子プロセス環境へ転送する処理や、コンテナ起動後に読む処理はありません。

`docker run` が失敗した場合、スクリプトは `bad "docker run"` を呼んで `FAIL: docker run` を出し、終了コード 1 で終了します。標準出力と標準エラーは `tee` で `$OUT/test.log` に追記されるため、Docker の出力もこのログ経由で観測できます。失敗理由の具体的な意味や、重複したオプションの扱いは Docker CLI 側の挙動なので、ここでは Strata の動作として説明しません。

## 根拠

- `docker/smoke-test.sh:1-6` は Bash スクリプトと使用例を示し、`ENVS` の例として `-e MODEL=...` 等を記載しています。
- `docker/smoke-test.sh:10-17` は `set -u`、必須変数の確認、および標準出力・標準エラーを `$OUT/test.log` へ追記する設定です。
- `docker/smoke-test.sh:27-30` はコンテナ削除後、固定の `API_KEY` 引数に続けて `${ENVS:-}` を展開し、`docker run` の失敗時に `FAIL: docker run` と終了コード 1 を返します。
- `docker/smoke-test.sh:94-105` は2回目の起動に `docker start` を使い、`ENVS` を再展開しません。
- `docs/DOCKER.md:301` は smoke-test スクリプトを実カード上のチェックとして案内しています。
