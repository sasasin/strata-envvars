# `GITHUB_OUTPUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の通常の実行コードではなく、手動起動の Docker images GitHub Actions workflow が、後続 job に渡す `flavors` step output を出力するために使います。workflow は `GITHUB_OUTPUT` の値を追記先ファイルのパスとして shell に展開し、`flavors=[...]` を書き込みます。その値は `plan` job の output に渡され、`image` job の matrix の flavor 一覧に使われます。

## 値と判定

Strata 側で値の内容を parse、比較、変換する処理はありません。`.github/workflows/docker-images.yml` の `run` script が `set -u` を有効にした後、`>> "$GITHUB_OUTPUT"` のリダイレクト先として値を展開します。したがって値はファイルパスとして扱われます。未設定時は未定義変数の展開で shell script が失敗し、空文字の場合は空のリダイレクト先となり出力を書けません。いずれも workflow は後続の output を生成できません。実際の値は GitHub Actions runner が workflow 実行時に供給する前提で、Strata ソースは fallback を設けていません。

追記する内容は環境変数の値からではなく、先行処理で得た `list.tsv` から生成します。`awk` が `SKIP` 行を除いた flavor 名を JSON 配列要素として連結し、空なら明示的なエラーを出して終了します。

## 有効になる条件

- `.github/workflows/docker-images.yml` の `workflow_dispatch` による手動実行で、`plan` job の「Which flavors does the release have a package for」step に到達した場合に使われます。
- 対象 release の engine package を列挙した結果、少なくとも 1 flavor が必要です。0 件なら `the release has no engine package for any requested flavor` を標準出力へ出して `exit 1` し、`GITHUB_OUTPUT` への書き込みに進みません。
- workflow は Ubuntu 24.04 runner を指定しています。Strata の CLI、server mode、backend、モデル状態による分岐はこの参照にはありません。

## 実行時の詳細

workflow の `plan` job は `steps.list.outputs.flavors` を job output `flavors` に設定します。後続の `image` job は `fromJSON(needs.plan.outputs.flavors)` を matrix として使い、各 flavor について Docker image の処理を実行します。`GITHUB_OUTPUT` はこの step 内で一度だけ shell に展開されます。Strata が値を cache したり、子プロセスへ引き渡したりする実装はありません。追記コマンドは `set -e` の下にあるため、リダイレクトまたは書き込みが失敗すれば step は成功しません。

## 根拠

- `.github/workflows/docker-images.yml:1-4,12-13,46-68`: 手動起動の workflow、`plan` job、shell の `set -eu`、flavor 一覧生成、空一覧時のエラー、`GITHUB_OUTPUT` への追記。
- `.github/workflows/docker-images.yml:49-50,70-81`: step output を job output に渡し、JSON を `image` job の matrix に使う定義。

リポジトリ全体（無視対象を含む）の完全一致検索では参照は `.github/workflows/docker-images.yml:68` のみでした。アプリケーション実行コードや env helper での読み取りは確認できていません。この候補は環境変数名一覧には載っていますが、確認できた用途は GitHub Actions workflow の step output ファイルへの書き込みに限られます。
