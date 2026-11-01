# `STRATA_DIST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の Node App Host が、ビルド済み Web UI のファイルを探すディレクトリを指定します。`apps/host/server/index.mjs` が `process.env.STRATA_DIST` を読み、その値を絶対パス `DIST` にして HTTP の静的ファイル配信に使用します。API 専用の設定ではなく、`/api/` と `/v1/` 以外の要求の UI/静的ファイル応答に関係します。GPU backend やモデル状態による条件はありません。

## 値と判定

`apps/host/server/index.mjs` は起動引数から `--dist` の位置を探し、次の順で `DIST` を一度設定します（同ファイル 88–100 行）。

| `STRATA_DIST` | `--dist` | 採用値 |
|---|---|---|
| 空でない文字列 | 有無を問わない | `resolve(STRATA_DIST)`。CLI と既定値より優先 |
| 未設定または空文字 | あり、後続引数あり | `resolve(--dist の次の引数)` |
| 未設定または空文字 | あり、後続引数なし | `resolve(ROOT/dist)` |
| 未設定または空文字 | なし | `join(ROOT, 'dist')` |

環境変数は数値や真偽値として parse されず、内容をそのままパスとして渡します。Node.js の条件式で空文字は falsy なので未設定と同じく扱われます。それ以外は空白だけの文字列も非空値として優先されます。相対パスは Node.js の `resolve()` によりホストプロセスの現在ディレクトリ基準で絶対化されます。大文字小文字変換、trim、存在確認による別候補への切替は設定時には行いません。

`--dist` は完全な引数一致で最初の位置だけを使います。直後の引数が `--other` のような別オプションでもパス値として受け取られます。`--dist` があり次引数が欠けているときは `ROOT/dist` が使われます。

根拠: `apps/host/server/index.mjs:86-100`。

## 有効になる条件

App Host の Node プロセスで有効です。環境変数は Chromium の引数リストにホスト用の `--dist` を混在させにくいデスクトップキャリア向けに導入されたとコメントされています。通常の開発・serve 起動では、`STRATA_DIST` が空または未設定なら CLI `--dist`、さらに指定がなければ `apps/host/dist` 相当の既定位置が使われます（`apps/host/server/index.mjs:90-99`）。

デスクトップシェルの `host_command` は `host/dist` を確認し、子 Node プロセスに `STRATA_DIST` として渡します（`apps/desktop/src-tauri/src/main.rs:444-468`）。`start_host` は Linux 以外の desktop 起動経路でこのコマンドを起動します（同ファイル 495-515 行）。同ファイルの self-test 用ホスト起動も同じディレクトリを設定します（同ファイル 734-745 行）。この環境変数を設定する起動スクリプトとして、desktop の UI/E2E スクリプトにも参照があります（例: `apps/desktop/scripts/first-run-ui.mjs:48-53`, `apps/desktop/scripts/ui-flows.mjs:151-154`, `apps/desktop/scripts/vision-e2e.mjs:33-36`）。これらはテスト用の起動設定であり、別の本番読取実装ではありません。

## 実行時の詳細

値は `index.mjs` のモジュール評価時に `const DIST` として決まり、リクエストのたびに環境変数を読み直しません。プロセス起動後の環境変更はこの値に反映されません。ルーターは `/api/` を API handler、`/v1/` を OpenAI 互換 handler に渡し、それ以外を `staticFile()` に渡します（`apps/host/server/index.mjs:969-984`）。

`staticFile()` はまず `DIST` の存在を確認します。ディレクトリが見つからない場合は HTTP 200 で「Strata host is running」と「No built web app found at …」を含む案内 HTML を返します。したがって、存在しないパスは UI 配信を止めますが、この分岐自体はエラー終了や警告ログにはせず、サーバーの API 経路は別に処理されます。ディレクトリが存在する場合は要求パスに対応するファイルを配信し、拡張子のないパスは `index.html` に fallback します。要求ファイルがない場合は拡張子ありで HTTP 404 `Asset not found`、`index.html` もない場合は HTTP 404 `Not found` です（同ファイル 2210-2252 行）。この変数専用の起動時ログや値の検証エラーは見当たりません。リクエスト処理で例外が発生すれば共通 catch が `[strata]` と例外を stderr に出して HTTP 500 を返します（同ファイル 985-987 行）。

## 根拠

- 読み取り、空値判定、CLI と既定値の優先順位、絶対パス化: `apps/host/server/index.mjs:86-100`。
- API / `/v1/` と静的配信の振り分け、例外ログ: `apps/host/server/index.mjs:969-987`。
- UI ディレクトリ不在時の応答、ファイル fallback と 404: `apps/host/server/index.mjs:2210-2252`。
- desktop 子プロセスへの値設定と UI ディレクトリ事前確認: `apps/desktop/src-tauri/src/main.rs:444-481`。
- desktop 起動時の `host_command` 使用（Linux 以外）: `apps/desktop/src-tauri/src/main.rs:495-515`。
- self-test 子プロセスへの設定: `apps/desktop/src-tauri/src/main.rs:734-745`。
