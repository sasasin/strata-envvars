# `ACQUIRE_SPY_LOG`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は host の通常設定ではなく、同梱の取得監視 preload `apps/host/tests/helpers/acquire-spy.mjs` が、検知した取得試行を JSON Lines 形式で追記するファイルのパスである。同 helper は非 loopback への `fetch`、HTTP(S) 要求、socket 接続と、package manager・compiler・download tool などの子プロセス起動を検知して遮断する。`ACQUIRE_SPY_LOG` はその遮断機能を切り替えず、記録先だけを指定する。first-run UI と installed-flow の診断スクリプトが preload を host に適用する経路で使われる（`apps/host/tests/helpers/acquire-spy.mjs:1-6,16-20,26-76`; `apps/desktop/scripts/first-run-ui.mjs:32-33,48-57`; `apps/desktop/scripts/installed-flow.mjs:5-18,107-117`）。

## 値と判定

helper は初期化時に `process.env.ACQUIRE_SPY_LOG` を文字列として一度読み、truthy 判定、数値変換、パス検証は行わず `LOG` に保持する。`note()` は検知イベントごとに `appendFileSync(LOG, JSON.stringify({ kind, detail }) + '\n')` を試し、追記の例外をすべて握りつぶす（`apps/host/tests/helpers/acquire-spy.mjs:16-17`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| spy preload が実行中 | `undefined` が保存され、記録の追記は失敗して握りつぶされる | 書き込み可能なパス。`/tmp/acquire.log` や `spy.log` のように文字列をそのまま追記先にする | 空文字は追記先として使われず例外が握りつぶされる。存在しない親ディレクトリなど、追記に失敗するパスも記録できない |

`0`、`false`、`true` なども真偽値として解釈されず、文字列のままファイルパスになる。空白・大文字小文字も値変換や比較には使われない。ファイル作成・追記の可否は `appendFileSync` の結果による。書き込みに失敗しても検知・遮断の分岐は続く（同 `:16-17,26-30,33-51,61-75`）。

## 有効になる条件

- `apps/desktop/scripts/first-run-ui.mjs` は通常、`node --import <acquire-spy.mjs> ...` として host を起動し、`ACQUIRE_SPY_LOG` に `spy.log` のパスを渡す。`--no-spy` が指定された場合は preload 自体を付けない（`apps/desktop/scripts/first-run-ui.mjs:32-33,48-57`）。
- `apps/desktop/scripts/installed-flow.mjs` は `--spy <acquire-spy.mjs>` が指定された場合だけ preload を付け、作業ディレクトリの `acquire-spy.log` を環境に加える。省略時はこの spy を起動しない（`apps/desktop/scripts/installed-flow.mjs:5,107-117`）。
- 変数だけを設定しても spy は有効にならない。上記のように preload が host の Node.js プロセスへ読み込まれることが必要である。helper 内には OS / backend / GPU による有効条件はない（`apps/host/tests/helpers/acquire-spy.mjs:1-6,16-20`）。
- 記録先が unset、空、または書き込み不能でも、preload が有効ならネットワーク・子プロセスの遮断処理は実行される。ログを読み取って試行の有無を判定する診断側は記録を確認するため、ログが書けないと観測できない（`apps/host/tests/helpers/acquire-spy.mjs:17,26-30,61-75`; `apps/desktop/scripts/first-run-ui.mjs:113-117`; `apps/desktop/scripts/installed-flow.mjs:288-295`）。

## 実行時の詳細

`LOG` は ES module の初期化時に一度だけ取得される。以後の環境変数変更は反映されない。イベントごとにファイルを append open し、1 行に `{kind, detail}` の JSON を書く。ログ書き込みの失敗は空の `catch` で無視する（`apps/host/tests/helpers/acquire-spy.mjs:16-17`）。

preload は `fetch`、`http` / `https`、`net.Socket.prototype.connect`、`child_process` の起動関数を差し替える。loopback 以外への要求・接続や取得用と判定したコマンドをログへ記録した後、`fetch` では rejected `TypeError('blocked by the acquisition spy')`、HTTP/socket/子プロセス経路では `Error('blocked by the acquisition spy')` を返すか throw する。loopback は元の関数へ渡し、子プロセスは basename 等で取得用コマンドと判定された場合に限って遮断する。これらは helper が行う診断上の介入であり、外部ライブラリや driver の動作を説明するものではない（`apps/host/tests/helpers/acquire-spy.mjs:18-20,26-75`）。

## ログと測定値

各検知イベントは `{"kind":...,"detail":...}` の JSON 1 行として指定先へ追記される。`kind` は `fetch`、`http.request` / `https.get`、`socket`、または差し替え対象の child-process 関数名など、検知経路に応じた値である。遮断例外の文字列は `blocked by the acquisition spy`。ログ追記に失敗した場合、helper 自身は警告を出さない（`apps/host/tests/helpers/acquire-spy.mjs:17,26-75`）。first-run UI は最後に spy log が空であることを確認し、installed-flow は spy 有効時に取得試行がなかったことをステップとして記録する（`apps/desktop/scripts/first-run-ui.mjs:113-118`; `apps/desktop/scripts/installed-flow.mjs:288-295`）。測定値の記載はない。

## 根拠

- `apps/host/tests/helpers/acquire-spy.mjs:1-6,16-20,26-75` — preload の用途、環境値の読み取り、記録、検知と遮断。
- `apps/desktop/scripts/first-run-ui.mjs:32-33,48-57,113-118` — first-run 診断での preload 適用、環境へのログ先設定、ログ確認。
- `apps/desktop/scripts/installed-flow.mjs:5-18,107-117,288-295` — installed-flow の任意 spy、子プロセスへのログ先設定、結果確認。
