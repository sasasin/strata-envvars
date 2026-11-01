# `STRATA_NATIVE_REPO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のデスクトップ UI をソース checkout から動かすとき、UI の native engine control が最初に参照する Strata リポジトリのパスを指定します。プロセス起動時に `createNativeControl()` が値を既定パスとして取り込みます。ユーザーが Settings → Engine でリポジトリを選ぶと、その選択は設定ファイルに保存され、以後は環境変数の初期値より優先されます。

この名前を環境から直接読む本番コードは `apps/host/server/native-control.mjs` の `process.env.STRATA_NATIVE_REPO` です。ほかの直接参照はプレビュー・テスト用スクリプトによる子プロセス環境の設定と、手渡し用文書です（下記「根拠」）。

## 値と判定

値はパス文字列として使われ、boolean や数値への変換はありません。既定引数の `process.env.STRATA_NATIVE_REPO ?? resolve(ROOT, '../../Strata')` は nullish coalescing なので、未設定なら `apps/host` から `../../Strata` を解決した sibling checkout が既定になります。空文字は未設定扱いにならず、空のパスとして後続処理に渡ります。空白の trim や環境変数値自体の形式検証もありません。

| 状態 | 初期設定に使われる値 |
|---|---|
| `native-host.json` が存在しない、または JSON を読めない | 環境変数の値。未設定なら既定 sibling path |
| 有効な `native-host.json` があり `repo` がある | 保存済みの `repo`。環境変数より優先 |
| 環境変数が空文字で、保存済み設定がない | 空文字。未設定時の既定 path へは戻らない |

`readJson()` は有効な JSON をオブジェクトごと返すため、既存ファイルに `repo` キーがない場合も環境変数とのマージは行われず、`preferences.repo` は `undefined` になります。CLI 引数による優先順位はありません。UI の Engine 設定 API から別の repository が選ばれると、そのパスが `preferences.repo` を置き換えて保存されます。

## 有効になる条件

- ソース checkout の host 経路で使われます。`repo()` は `control` が渡された packaged mode では `installRoot()` を返すため、環境変数の値はリポジトリ選択に使われません。
- 指定先が実在し、`setup.py`、`tools/strata_mcp.py`、`serve/server.py` を含む必要があります。
- 有効な既存の `native-host.json` の `repo` があればそちらが優先されます。Engine 設定画面で repository を変更すると、以後の起動でも保存値が優先されます。

## 実行時の詳細

環境変数は host プロセス内で `createNativeControl()` の既定引数を評価するときに読み取られ、その値を使って設定ファイルが読まれます。サーバー初期化時に一度だけ初期値として取り込まれるため、起動後に親プロセスの環境を変えても反映されません。設定画面からの変更は `realpathSync()` で解決したパスに差し替え、native host の設定ファイルへ保存して refresh します。

リポジトリを使うとき `repo()` は `realpathSync(preferences.repo)` を実行し、3つの必須ファイルの存在を確認します。解決・検証に失敗するとエラーになります。状態 refresh の経路では例外の `message` が native 状態の `error` に格納され、`available:false` とともに返されます。Engine 設定 API からの変更時は検証に失敗すると旧 preferences に戻し、エラーを呼び出し元へ返します。

ソース checkout の host は `process.env` を spread した環境で `tools/strata_mcp.py` と `serve/server.py` を起動するため、この変数も変更・除去されず子プロセス環境へ継承されます。autotune 起動にも同様に `process.env` を渡します。リポジトリ全体の名前検索では、これらの子プロセス側に `STRATA_NATIVE_REPO` を直接読む Strata の参照は見つかりませんでした。したがって、ここで確認できる挙動は host が初期 repository を選び、値を子プロセス環境へ引き継ぐところまでです。

## 根拠

- `apps/host/server/native-control.mjs:29-40`: `ROOT`、環境変数を使う既定値、設定ファイル読み込みと初期 snapshot。
- `apps/host/server/native-control.mjs:97-106`: packaged/source の分岐、ソース repository の実在・必須ファイル確認、MCP 子プロセス起動時の環境。
- `apps/host/server/native-control.mjs:144-146`: refresh 時のエラー状態化、Engine 設定変更時の path 検証・rollback・保存。
- `apps/host/server/native-control.mjs:55,387`: autotune と source server の起動時に渡す環境。
- `apps/host/server/control-runtime.mjs:82-85`: source server 環境は `process.env` のコピーであり、削除するのは `STRATA_API_KEY`。`STRATA_NATIVE_REPO` は除去されない。
- `apps/host/server/index.mjs:164,997-998`: host 作成時に `createNativeControl()` を呼び、`/api/native` の PATCH で Engine 設定を受け付ける。
- ほかの文字列参照: `apps/host/scripts/language-shots.mjs:26`、`apps/host/scripts/preview-ui.mjs:13`、`apps/host/tests/api-reasoning-effort.test.mjs:81`、`apps/host/tests/gh-app-features.test.mjs:205` は UI preview/test の子プロセス環境に値を注入する箇所。`apps/host/docs/native-engine-handover.md:40` は説明文であり、読み取りコードではありません。
