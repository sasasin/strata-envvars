# `PYTHONSTARTUP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata は `PYTHONSTARTUP` の値を利用せず、アプリ同梱の Strata Control を起動するときに子プロセス用環境からこのキーを削除します。対象は Control の Python CLI、チューナー、インストーラーです。これはユーザー側 Python の環境設定を Control に引き継がないための環境整理です。

## 値と判定

値の文字列・内容・形式は判定しません。`controlEnvironment()` は入力環境をオブジェクトコピーし、キー名の固定リストに対して `delete` します。そのため `PYTHONSTARTUP` が未設定なら子環境にも存在せず、空文字を含む何らかの値が設定されていても子環境から取り除かれます。既定値への置換や CLI 引数との優先順位はありません。

## 有効になる条件

この削除は、ホストが `control` を持つ packaged mode で Control 用子プロセスの環境を作る場合に適用されます。`runCli()` は `controlEnvironment()` の戻り値を `spawn` に渡し、`installerEnvironment()` も同関数の結果を引き継ぎます。packaged mode ではオートチューナーも同じ環境関数を使い、MCP インストーラー起動には `installerEnvironment()` を使います。

ソース checkout mode では `native-control.mjs` が Control 用環境関数を通らず、`process.env` をコピーして Python 用の UTF-8 設定を加えた環境で起動します。この経路では Strata による `PYTHONSTARTUP` の削除はありません。OS 別の値判定はなく、差は packaged/source checkout の起動経路によります。

## 実行時の詳細

`controlEnvironment()` が呼ばれるたびに渡された環境（既定ではその時点の `process.env`）から新しいオブジェクトを作り、`PYTHONSTARTUP` を含む固定キー群を削除します。関数内にキャッシュはありません。作成済みの子プロセス環境はその起動時点のコピーであり、親の環境を後から変更してもその子の環境オブジェクトは変化しません。後続の起動は、その呼び出しに渡された環境を再びコピーします。

Strata 側には、この変数の値に応じたログ、警告、終了処理、エラー処理はありません。子プロセスの起動失敗や Control の応答失敗には一般的なエラー経路がありますが、ソースから `PYTHONSTARTUP` に起因するものとは確認できません。Python ランタイム側が環境変数をどう扱うかはここでは扱いません。

## 根拠

- 候補一覧には `PYTHONSTARTUP` が掲載されています（`docs/envvars/000_envvers.md:522`）。
- 入力環境のコピーと `PYTHONSTARTUP` を含む削除リスト: `apps/host/server/control-runtime.mjs:88-103`。
- Python CLI に渡す環境: `apps/host/server/control-runtime.mjs:124-130`。
- インストーラー環境の継承: `apps/host/server/control-runtime.mjs:106-111`。
- packaged mode の判定、チューナーとインストーラーの packaged/source checkout 分岐: `apps/host/server/native-control.mjs:50-58,102-110`。
- Control の生成: `apps/host/server/index.mjs:124`。
