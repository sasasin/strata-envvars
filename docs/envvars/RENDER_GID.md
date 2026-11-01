# `RENDER_GID`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Intel / AMD 向け Docker Compose 定義で、コンテナの `group_add` に render グループを追加するための値です。Strata アプリケーションのソースコードがこの環境変数を読む箇所は見つかりませんでした。値の利用は Compose 設定の補間に限られます。

## 値と判定

両 Compose 定義は `group_add` の要素に `${RENDER_GID:-render}` を指定しています。Compose の補間式として未設定または空文字なら `render` が既定値になり、値があればその文字列が設定に渡されます。Strata のコードによる数値変換、書式検査、範囲制限はありません。

| 設定 | Compose 定義に記載された結果 |
|---|---|
| 未設定または空文字 | `render` |
| 値あり | 指定値を `group_add` の要素として補間 |

`.env.example` では AMD / Intel 向けに空の設定例をコメントで示し、ホストの `render` グループ ID を `getent group render | cut -d: -f3` で得る方法を記載しています。

## 有効になる条件

`docker-compose.intel.yml` または `docker-compose.amd.yml` を使う場合に限られます。NVIDIA 向け Compose 定義には `RENDER_GID` の参照がありません。Intel 定義のコメントは `user:` を追加する場合に必要と説明し、AMD 定義のコメントは同じ条件と root では不要であることを説明しています。

## 実行時の詳細

Compose 設定内の補間結果を `group_add` に渡す定義です。Strata の実行ファイル、サーバー、CLI における読み取り、キャッシュ、優先順位、ログ出力、失敗処理は確認できませんでした。コンテナ作成時に Docker Compose / Docker がこの設定をどう処理するかは Strata 自身の実装ではないため、ここでは Strata の挙動として記述しません。

## 根拠

- `docker/compose/docker-compose.intel.yml:28-29` — `group_add` に `${RENDER_GID:-render}` を指定。コメントにホストの render グループ ID と `user:` 条件を記載。
- `docker/compose/docker-compose.amd.yml:29-31` — `video` と補間した render グループを `group_add` に指定。コメントに `user:` 条件と root の例外を記載。
- `docker/compose/.env.example:12` — AMD / Intel 向けの設定例とホスト上でのグループ ID の取得方法。
- リポジトリ全体の `RENDER_GID` 完全一致検索では上記3箇所のみ。アプリケーションコード内の環境変数読み取りは確認できませんでした。
