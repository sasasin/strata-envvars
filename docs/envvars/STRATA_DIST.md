# `STRATA_DIST`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象は Strata 所有のホストとデスクトップ起動コード。テスト・スクリプト中の設定例は、本番時の値判定の根拠にはしていない。

## 役割

`apps/host` の Node ホストが、配信するビルド済み Web UI のディレクトリを選ぶための変数です。ホストの静的ファイル配信が参照するパス `DIST` を設定します。API の動作や推論エンジンの選択はこの変数では変わりません。

デスクトップアプリのホスト起動処理は、リソース内の `host/dist` を `STRATA_DIST` に設定して Node 子プロセスを起動します。Node ホストを直接起動する場合は、CLI の `--dist` より環境変数が優先されます。

## 値と判定

値を数値や真偽値として parse せず、Node.js の truthy 判定と `path.resolve()` を使います。

| `STRATA_DIST` | 選ばれるディレクトリ |
|---|---|
| 未設定 | `--dist` があればその次の引数を `resolve()` したパス。`--dist` もなければホスト基準の `ROOT/dist` |
| 空文字 | 未設定と同じ。`--dist` があればそちらを使う |
| 空でない文字列 | その文字列を `resolve()` したパス。`--dist` より優先 |

空白だけの値や `0` も空でない文字列なのでパスとして使われます。相対パスはプロセスの作業ディレクトリ基準で絶対化され、空白の trim、ディレクトリの存在確認、`index.html` の事前検証は選択時には行いません。`--dist` があり、その直後の引数が存在しない場合は `ROOT/dist` が使われます。

## 有効になる条件

Node ホスト `apps/host/server/index.mjs` を実行したときに適用されます。環境変数はモジュール初期化時に一度読み取られます。起動後にプロセス環境を変更しても、選択済みの `DIST` は再計算されません。

デスクトップ側の `host_command()` は、バンドル内の `host/dist` ディレクトリが存在しなければホストを起動せず、UI のビルドがない旨をエラーにします。この起動経路では環境変数をそのディレクトリに固定して子プロセスへ設定します。Node ホストを直接起動する経路では、指定先が存在しなくても起動時には拒否しません。

## 実行時の詳細

`/api/` と `/v1/` 以外の HTTP リクエストは `staticFile()` に渡され、`DIST` を起点にファイルを探します。指定したディレクトリ自体が存在しない場合は、HTTP 200 で「Strata host is running」と「No built web app found at …」を含む案内 HTML を返します。ディレクトリは存在するが要求された拡張子付きファイルがない場合は 404 `Asset not found`、拡張子のないパスでは `index.html` にフォールバックし、それもなければ 404 `Not found` です。

デスクトップの本番起動では Rust の `host_command()` が `STRATA_DIST` を `host_dir/dist` に設定します。これにより、ホストの作業ディレクトリや Electron/Tauri の引数一覧に依存せず、バンドルされた UI を配信できます。デスクトップのセルフテスト用起動でも同じパスを設定します。

## 根拠

- `apps/host/server/index.mjs:83-97` — `ROOT`、`--dist` の検出、環境変数優先、既定パスの決定。
- `apps/host/server/index.mjs:934-964` — `/api/`、`/v1/` 以外を静的ファイル処理へ送るルーティング。
- `apps/host/server/index.mjs:2155-2180` — ビルドディレクトリ不在時の案内、ファイル検索、404 と index fallback。
- `apps/desktop/src-tauri/src/main.rs:432-477` — デスクトップホスト起動時に `host/dist` を検査し、子プロセスの `STRATA_DIST` に設定。
- `apps/desktop/src-tauri/src/main.rs:653-729` — セルフテストでホストを起動する際の値設定。
