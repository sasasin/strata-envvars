# `RUN_FLAGS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`RUN_FLAGS` は Strata アプリ本体の実行時設定ではなく、Strata リポジトリの `docker/smoke-test.sh` が `docker run` に追加するホスト側の Docker CLI 引数列です。例としてスクリプトの使用例は `--device /dev/dri -p 18080:8080` を示しています。Strata の C++/Python アプリケーションコードから `RUN_FLAGS` を読む箇所は見つかりませんでした。

## 値と判定

スクリプトは値を真偽値や数値として parse せず、`${RUN_FLAGS:-}` で展開します。この shell parameter expansion は変数が未設定または空文字なら空に展開し、値があればその文字列を返します。展開は引用符で囲まれていないため、シェルの field splitting と pathname expansion が行われ、通常は空白区切りで複数の Docker 引数になります。値を一つの引数として保持する処理や、値の検証・範囲制限・無効値 fallback はありません。

## 有効になる条件

- この値を使うのは `docker/smoke-test.sh` を実行する場合だけです。Strata サーバーや CLI を直接起動しても、このスクリプトを介さなければ `RUN_FLAGS` は参照されません。
- `docker run` の固定引数、`ENVS`、`VOLS` の後、イメージ名 `IMAGE` の前に追加されます。値の意味や Docker 側での受け付け可否はこのスクリプトでは判断しません。
- `RUN_FLAGS` と `ENVS` / `VOLS` の間に独自の優先順位処理はありません。競合する Docker オプションがある場合の扱いはこのコードからは定まりません。

## 実行時の詳細

スクリプトは `set -u` を有効にしていますが、`${RUN_FLAGS:-}` は未設定でも安全に空へ展開されます。未設定・空文字なら `docker run` のコマンド行にこの変数由来の引数を加えません。値があれば、スクリプトが `docker run` を実行する時点で展開して引数として渡します。環境変数を読み取って保持する cache はありません。

`docker run` が失敗すると、スクリプトは `FAIL: docker run` を記録して終了コード 1 で終了します。スクリプトは `RUN_FLAGS` の展開後の内容を別途表示・検査しません。`docker run` 成功後の smoke test はコンテナの起動・health check・API 呼び出しなどを続け、途中の失敗も記録します。

## 根拠

- 使用例と想定される値: `docker/smoke-test.sh:4-6`。
- `set -u`、および未設定・空文字を空に展開し、`ENVS` と `VOLS` に続けて `docker run` に渡す処理、失敗時のログと終了: `docker/smoke-test.sh:10-12,27-30`。
- smoke test は手動の実 GPU 環境向けであるとの説明: `docs/DOCKER.md:301,344`。
- 候補一覧には `RUN_FLAGS` がある: strata-envvars `docs/envvars/000_envvers.md:839`。Strata ソース内の全一致検索では `docker/smoke-test.sh:5,30` のみでした。
