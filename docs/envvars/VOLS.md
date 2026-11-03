# `VOLS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`VOLS` は Strata アプリ本体の設定ではなく、`docker/smoke-test.sh` が `docker run` に追加するホスト側の Docker CLI 引数列です。使用例では `-v $HOME/dt/data:/data -v /m:/models:ro` が示されています。Strata の C++/Python アプリケーションから `VOLS` を読む箇所はありません。

## 値と判定

スクリプトは `VOLS` を parse せず、`${VOLS:-}` で展開します。

| 状態 | スクリプトの処理 |
|---|---|
| 未設定 | 空に展開され、追加引数はありません。 |
| 空文字 | 未設定と同じく空に展開され、追加引数はありません。 |
| 非空文字列 | 引用符なしの展開結果がシェルの語分割とパス名展開を受け、できた各語が `docker run` の引数になります。 |

値の検証、型変換、許可リスト、長さ制限、無効値時の fallback はありません。値を単一引数として保持したり、展開後に引用符を構文として再解釈したりする処理もありません。

## 有効になる条件

- `docker/smoke-test.sh` を実行し、コンテナ作成の `docker run` に到達したときに限り使われます。通常の Strata CLI やサーバーを直接起動しても参照されません。
- `docker run` の固定引数と `ENVS` の後、`RUN_FLAGS` とイメージ名 `IMAGE` の前に追加されます。スクリプトは `VOLS` と他の追加引数との優先順位を調整しません。
- 値の意味や受理可否はこのスクリプトでは判断されません。Docker CLI に渡された引数の扱いは Docker 側の動作です。

## 実行時の詳細

スクリプトは `set -u` を有効にしますが、`${VOLS:-}` は未設定でもエラーにならず空へ展開されます。変数は `docker run` を呼ぶ時点で評価され、値を保存する cache や、コンテナ起動後に `VOLS` を読む処理はありません。2回目の起動は既存コンテナに対する `docker start` であり、`VOLS` は再展開されません。

`docker run` が失敗すると、スクリプトは `FAIL: docker run` を記録して終了コード 1 で終了します。標準出力と標準エラーは `$OUT/test.log` に追記されるため、コマンドの出力もそのログで観測できます。スクリプト自身は展開後の `VOLS` や、Docker がその引数をどう処理したかを個別に記録・検査しません。

## 根拠

- `docker/smoke-test.sh:1-6` は Bash スクリプトであることと、`VOLS` の使用例を示します。
- `docker/smoke-test.sh:10-17` は `set -u` と標準出力・標準エラーを `$OUT/test.log` に追記する設定です。
- `docker/smoke-test.sh:27-30` は `docker run` の引数列で `${VOLS:-}` を展開する位置と、失敗時に `FAIL: docker run` を記録して終了コード 1 で終了する処理です。
- `docker/smoke-test.sh:94-105` は2回目の起動に `docker start` を用い、`VOLS` を再展開しないことを示します。
- Strata ソース全体の `VOLS` 完全一致検索では、参照は `docker/smoke-test.sh:5,30` のみでした。候補一覧には `VOLS` が `docs/envvars/000_envvers.md:2147` にあります。
