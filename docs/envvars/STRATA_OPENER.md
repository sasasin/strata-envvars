# `STRATA_OPENER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata host がファイルを外部プログラムで開くとき、`STRATA_OPENER=record` なら起動要求を実行せず、コマンドと引数をメモリー上の配列に記録します。値が `record` 以外なら、OS ごとに選んだプログラムを detached child process として起動します。

この分岐はテスト専用のビルドやモードに限定されていません。`chat-files.mjs` の `launch()` が実行時に環境を直接参照するため、通常の host に `STRATA_OPENER=record` を渡した場合も外部プログラムの起動を抑止します。対象となる本番経路はチャットの「ファイルを開く」と、Native model の設定ファイルを開く操作です。

## 値と判定

| 値 | Strata の判定 | 結果 |
|---|---|---|
| 未設定 | `process.env.STRATA_OPENER === 'record'` が偽 | 外部プログラムを起動する |
| 空文字 | 偽 | 外部プログラムを起動する |
| 文字列 `record` と完全一致 | 真 | 起動せず、コマンドと引数を記録する |
| その他すべて（例: `Record`, `true`, `1`, `record `） | 偽 | 外部プログラムを起動する |

trim、大小文字変換、数値変換、許容値検査はありません。文字列全体の厳密比較です。未設定時と無効値時の fallback は同じで、通常の起動経路です。

## 有効になる条件

- OS や backend による条件分岐はありません。対象関数は Windows、macOS、Linux 用のコマンドを `openCommand()` / `textEditorCommand()` で選び、その後同じ `launch()` を呼びます。
- `STRATA_OPENER=record` であっても、呼び出し側から `recorder` が渡された場合は同じく起動せず、渡された recorder に記録します。`recorder` の明示指定は環境値にかかわらず記録経路になります。
- 変数が `record` でないときは `spawn()` を呼び、`detached: true`、`stdio: 'ignore'` で起動して待たずに `unref()` します。子プロセスの `error` イベントは空の handler で処理されます。

## 実行時の詳細

`launch()` は呼び出しごとに `process.env.STRATA_OPENER` を読むため、この値をモジュール初期化時に cache しません。Node プロセス内で呼び出し前に `process.env` が変更されれば次の呼び出しに反映されます。Strata の API にこの値を変更する処理は見つかりません。

チャットの `POST /api/files/open` は `openFile()` を呼びます。`openFile()` はパスを検証して OS 用のコマンドを作り、`launch()` の後に `{ ok: true, started: true, ... }` を返します。そのため `record` 設定時にも API は成功応答を返しますが、コマンドは起動されません。パスや `how` の検証エラーは API が 400（チャットフォルダー外のパスは 403）で返します。

Native model 設定ファイルの `POST /api/native/models/:model/settings-file` は `openSettingsFile()` から `openTextFile()` を経て同じ `launch()` を使います。`record` 設定時も設定ファイルの内容を確認した情報を返しますが、エディターは起動されません。Linux では `openTextFile()` が `launch()` より先に `xdg-mime` などでテキストエディターを検索します。この検索自体は `STRATA_OPENER=record` でも行われます。

起動コマンドは標準出力・標準エラーを Strata と共有せず、終了も待ちません。起動後の非同期エラーは握りつぶされます。`STRATA_OPENER=record` そのものに関するログ出力はありません。したがって、呼び出し元が成功応答を受け取っても、外部アプリが実際に開いたことは保証されません。

## 根拠

- `apps/host/server/chat-files.mjs:85-96` — `record` との厳密比較、記録先、通常時の `spawn()` と非同期 error handler。
- `apps/host/server/chat-files.mjs:98-122` — OS 別コマンド選択と、チャットの `openFile()` が起動後に成功結果を返す処理。
- `apps/host/server/index.mjs:1745-1748` — チャットのファイルを開く API と検証エラーの HTTP 応答。
- `apps/host/server/open-text-file.mjs:6-23,26-37` — OS 別テキストエディター選択、Linux の事前検索、同じ `launch()` の利用。
- `apps/host/server/native-control.mjs:150-152` — Native model の設定ファイルを開く処理。
- `apps/host/server/index.mjs:1050-1052` — 設定ファイルを開く API。
- `apps/host/tests/app-ui.test.mjs:130-142` — テストが host 起動時に `STRATA_OPENER=record` を渡す例。テストコードは挙動の実装根拠には用いていません。
