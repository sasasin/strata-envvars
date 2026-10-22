# `STRATA_SET`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Docker イメージの標準 entrypoint から `strata launch` に渡す上級者向け設定のリストです。環境変数そのものをエンジンが読むのではなく、entrypoint が内容を複数の `--set KEY=VALUE` 引数に変換します。その後、launch が設定名をエンジンの CLI オプションまたは設定環境変数として構成に反映します。

## 値と判定

| `STRATA_SET` の状態 | entrypoint の処理 |
|---|---|
| 未設定または空文字 | `--set` を追加せず、これだけを理由に launch の設定ありとは扱わない |
| 空白文字だけ | `-n` は真なのでブロックに入り、shell の field splitting で項目のないループを通る。`--set` は追加されないが、`have` は設定される |
| 空白区切りの項目あり | 各項目を一つずつ `--set` の値として追加する |

entrypoint は `for kv in $STRATA_SET` と非引用の展開を使います。そのため shell の `IFS` による分割と pathname expansion が起きます。値に空白を含む一つの設定を保護する quoting の仕組みはありません。各項目は `KEY=VALUE` として launch に渡します。値中に `=` があれば、launch は最初の `=` だけでキーと値を分けます。値の前後の空白は launch の parser が除きます。

launch の設定 parser は、`KEY` が大文字を少なくとも一つ含む環境変数名形式なら環境変数として扱います。それ以外は小文字の CLI flag 名（必要なら先頭に `--`）として扱い、underscore を hyphen に変換します。空のキーや不正な flag 名は拒否されます。同じキーを複数回指定すると、後の値が前の値を上書きします。値は大文字小文字を区別せず、CLI flag の `off` / `false` / `no` / `none` はその flag を取り除き、`on` / `true` / `yes` または空値は boolean flag を有効にします（値を取る flag の空値は変更として適用されません）。環境変数設定では `off` / `unset` / `none` が削除指定となり、それ以外の値はそのまま設定値です。

## 有効になる条件

- Docker の標準 entrypoint が `run` または `serve` 経路で起動する場合に限り、この変数を展開します。コンテナのコマンドに `strata ...` や別コマンドを指定すると、entrypoint は通常の launch 設定処理を迂回して実行ファイルへ `exec` するため、`STRATA_SET` は適用されません。
- 変数の名前や環境変数設定の内容に対する entrypoint 独自の許可リスト・範囲検査はありません。launch の設定 parser は名前の形式を検査します。対話式の詳細設定画面では engine の一覧にない flag を警告して保持しますが、`--no-tui` で `--set` を受ける経路には同じ画面上の確認はありません。未知の flag は engine 起動時に拒否される場合があります。
- CLI flag と環境変数の実際の意味や値域は、渡された個々の設定と engine に依存します。この変数自体に共通の数値 parse、clamp、既定値はありません。

## 実行時の詳細

entrypoint は標準 Docker 起動時に `STRATA_SET` を確認し、空でなければ空白区切りの各項目を `--set` に変換して `strata launch --no-tui` に渡します。その際、他の Docker 設定と同じく `have` を設定し、既定の `docker` preset が既にあればその preset を指定して保存します。既存 preset がなくても設定項目があれば `docker` preset として保存します。Docker の説明書によると、後続起動で設定値を与えない場合は保存済み preset が再利用され、設定を与えて起動すると preset の設定が置き換わります。

launch は `--set` を繰り返し受け付け、各ペアを `s.extra` に取り込みます。`derive_config()` は CLI flag の値を engine 起動引数へ反映し、環境変数形式の設定を run config の `env` に反映します。設定は launch ごとの run config に保存されます。Docker entrypoint が環境変数を処理するのは起動時なので、稼働中にプロセス環境を変更しても現在の launch には反映されません。値を変える場合は Docker を新しい環境変数で再起動する経路になります。

`STRATA_SET` 自体について entrypoint が出す専用ログや警告はありません。未知の engine flag に対する警告は対話式の詳細設定画面で設定を追加したときに出ます。Docker の標準 entrypoint は `--no-tui` を渡すため、この画面は通りません。設定名の構文エラーは launch 側でエラーになります。

## 根拠

- `docker/entrypoint.sh:41-44` — 既定 launch 以外のコマンドを直接 `exec` し、Docker 設定処理を通さない分岐。
- `docker/entrypoint.sh:157-159,212-213,229-237,264-269` — launch 引数の組み立て、`STRATA_SET` の展開、preset の選択・保存、起動。
- `strata_cli/launch/cmd.py:107-108,253-254` — `--set` を複数受け付け、launch 設定へ取り込む実装。
- `strata_cli/launch/settings.py:219-265` — キー形式、分割、重複キー、値の判定、CLI flag と環境変数への分類。
- `strata_cli/launch/runner.py:284-314` — 設定を run config の引数・環境に反映する処理。
- `strata_cli/launch/params.py:192-201` と `strata_cli/launch/screens.py:1201-1207` — 対話式の詳細設定画面で engine にない flag を警告して保持する処理。
- `docs/DOCKER.md:129,131-134` — `STRATA_SET` の利用例、preset の再利用・更新についての記載。
