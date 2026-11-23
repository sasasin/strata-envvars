# `STRATA_DIST`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Node の App Host が配信するビルド済み Web UI のディレクトリを指定する。`app/host/server/index.mjs` はこの値から `DIST` を決め、`/api/` と `/v1/` 以外のリクエストを `staticFile` に渡す。通常はホスト自身の `dist/` を使い、変数または `--dist` で別の場所を指定できる。API や推論処理の設定ではない（`app/host/server/index.mjs:95-110,1023-1038`）。

デスクトップアプリでは Tauri が `host/dist` のパスを `STRATA_DIST` として Node ホストの子プロセスに設定する。Windows/macOS の通常起動と Linux supervisor の起動は共通の `host_command` を通る。パッケージのセルフテストでも同じパスを設定する（`app/desktop/src-tauri/src/main.rs:503-526,554-560`、`app/desktop/src-tauri/src/main.rs:797-807`、`app/desktop/src-tauri/src/supervisor.rs:503-527`）。

## 値と判定

値は真偽値や数値として解析せず、JavaScript の truthiness 判定の後に `path.resolve` へ渡す。Node の `process.env` の文字列全体がパスとして使われ、前後空白の除去、大文字小文字変換、パス存在の起動時検証はない。相対パスは Node プロセスの現在ディレクトリを基準に絶対化される（`app/host/server/index.mjs:104-108`）。

| 条件 | `STRATA_DIST` | 採用される `DIST` |
|---|---|---|
| Node App Host 全般 | 未設定 | `--dist` の次の引数があればそのパス。なければホストの `dist/` |
| Node App Host 全般 | 空文字 | 未設定と同じ。`--dist` の次の引数があればそちら、なければホストの `dist/` |
| Node App Host 全般 | 空でない任意の文字列 | その文字列を `resolve` したパス。`--dist` より優先 |
| デスクトップアプリ／セルフテスト | Tauri が子プロセス環境に設定 | Tauri が解決した `host/dist` が `--dist` の有無にかかわらず優先 |

`0`、`false`、`true`、空白だけの文字列も空でなければパスとして採用される（`app/host/server/index.mjs:98-108`）。値の指定順は `STRATA_DIST`、`--dist <path>`、既定の `ROOT/dist`。`--dist` があり次の引数がない場合は `ROOT/dist` に戻る（同:96-108）。

## 有効になる条件

- Node App Host のみが値を読み、Web UI の静的配信経路で使う。GPU backend、OS 固有のエンジン実装、モデル状態、ビルド macro による値判定の違いはない（`app/host/server/index.mjs:95-108,1023-1038`）。
- デスクトップ起動では Tauri が値を `host_dir/dist` に固定して子プロセスへ渡すため、呼び出し元が持つ同名の値でその子プロセスのパスを変更する経路ではない。ホストと UI のエントリが見つからない、または `dist` がない場合は Tauri が起動コマンドを作れずエラーを返す（`app/desktop/src-tauri/src/main.rs:503-520,522-527`）。
- 単独起動では有効なパス文字列でも、その先にビルド済み UI がなければ UI は配信されない。`DIST` の存在確認は静的リクエストごとに行われる（`app/host/server/index.mjs:2511-2537`）。

## 実行時の詳細

`DIST` は `server/index.mjs` のモジュール評価時に一度計算される定数で、プロセス稼働中に環境変数を変えても再評価されない。一方、ディレクトリやファイルの存在確認は静的リクエストごとに行うため、同じプロセスでもファイル配置の変化はその後のリクエストで反映される（`app/host/server/index.mjs:95-108,2511-2537`）。

`/api/` は API handler、`/v1/` は OpenAI 互換 handler に振り分けられ、それ以外が `staticFile` に渡る。`DIST` 自体がない場合、ホストは HTTP 200 で「Strata host is running」「No built web app found at …」を含む案内 HTML を返す。ディレクトリが存在していて要求ファイルがない場合、拡張子付きパスには 404 `Asset not found`、拡張子なしパスは `index.html` にフォールバックし、それもなければ 404 `Not found`。ファイルがあれば MIME type と内容を返し、`index.html` は `no-store`、その他は `public, max-age=3600` とする（`app/host/server/index.mjs:1023-1038,2511-2552`）。

デスクトップでは、Tauri は `host/dist` が存在しないと「the built UI is missing at …; run …」を起動エラーとして返す。セルフテスト経路は同じパスを設定してホストを起動し、45 秒以内の health check と `/` の UI 配信を別々に記録する（`app/desktop/src-tauri/src/main.rs:513-518,797-832`）。

## ログと測定値

この変数の読み取り自体に専用ログはない。単独ホストで `DIST` がない場合の応答 HTML に、実際に選ばれた絶対パスを含む `No built web app found at …` が表示される。Tauri 側の `dist` 欠落は起動エラー文字列にパスを含む（`app/host/server/index.mjs:2512-2525`、`app/desktop/src-tauri/src/main.rs:513-518`）。測定値は該当なし。

## 根拠

- `app/host/server/index.mjs:95-110` — Node ホストの引数と環境変数の優先順位、パス解決。
- `app/host/server/index.mjs:1023-1038` — API、OpenAI 互換 API、静的ファイルの振り分け。
- `app/host/server/index.mjs:2511-2552` — `DIST` の存在、ファイル選択、応答内容。
- `app/desktop/src-tauri/src/main.rs:503-527` — デスクトップ用ホストコマンドの配置検査と環境設定。
- `app/desktop/src-tauri/src/main.rs:797-832` — セルフテスト用ホストの設定と UI 確認。
- `app/desktop/src-tauri/src/supervisor.rs:503-527` — Linux supervisor が共通ホストコマンドを起動する経路。
