# `STRATA_NO_SYSTEM_CA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Node.js ホストが、Node の bundled CA に OS の system CA を追加する処理を止めるための切り戻しスイッチです。`STRATA_NO_SYSTEM_CA=1` では `tls.setDefaultCACertificates` を呼ばず、Node の既定 CA 設定をそのままにします。証明書検証を無効化する処理はありません。ホストのエントリポイント `server/index.mjs` が `system-ca.mjs` を HTTPS 要求より前に読み込むため、サーバー起動時に適用されます（`app/host/server/system-ca.mjs:10-24`、`app/host/server/index.mjs:1-5`）。

## 値と判定

`env.STRATA_NO_SYSTEM_CA === '1'` という文字列の完全一致だけで判定します。値を数値や真偽値に変換せず、大文字小文字も含めて比較します（`app/host/server/system-ca.mjs:11-12`）。

| 条件 | unset | system CA 追加を止める値 | 止めない値 |
|---|---|---|---|
| 全 OS・Node.js 実行時 | system CA 追加を試みる | `'1'` | 空文字、`'0'`、`'true'`、`'false'`、`'01'`、`'1x'`、`' 1'`、`'1 '`、`'TRUE'` など `'1'` と異なる値 |

「止めない値」の場合でも、Node TLS API が利用できない、system CA が空、または証明書取得・設定で例外が起きると、追加は行われず bundled CA のままになります（`app/host/server/system-ca.mjs:13-21`）。

## 有効になる条件

- `STRATA_NO_SYSTEM_CA=1` の判定は、Node.js で Strata ホストの `server/index.mjs` を起動したときに有効です。同エントリポイントは `system-ca.mjs` を先に import します（`app/host/server/index.mjs:1-5`）。
- system CA の追加には `tls.getCACertificates` と `tls.setDefaultCACertificates` の両関数が必要です。関数がない Node.js では bundled CA のままです。ソースコメントは Node 24.5 以降を対象としており、実装上の実際の判定は関数の有無です（`app/host/server/system-ca.mjs:6-7,13-17`）。
- `tls.getCACertificates('system')` が配列以外または空配列を返した場合も bundled CA のままです（`app/host/server/system-ca.mjs:15-16`）。
- 別の CLI 引数や環境変数による上書きは、この処理にはありません。エージェント子プロセス用の環境は `agentEnvironment` で絞り込まれ、`NODE_USE_SYSTEM_CA=1` が設定されます。したがって、このスイッチが制御するのはホスト側の `system-ca.mjs` であり、エージェント子プロセスへ同名変数を通常の継承で渡す構成ではありません（`app/host/server/agent/harness-runtime.mjs:20-36,80-83`）。

## 実行時の詳細

`system-ca.mjs` のモジュール評価時に `trust` を一度だけ初期化し、既定引数としてその時点の `process.env` を読みます。設定値はモジュール読み込み時に判定されるため、その後にプロセス環境を書き換えてもこの判定は再実行されません（`app/host/server/system-ca.mjs:11-12,24`）。

値が `'1'` 以外なら、実装はまず system CA を取得し、配列が空でない場合に bundled CA と system CA を `Set` で重複排除して結合した配列を `tls.setDefaultCACertificates` に渡します。関数がない、system CA が空、またはこの処理中に例外が発生した場合は `bundled` を返します。例外は捕捉され、再試行されません（`app/host/server/system-ca.mjs:13-21`）。この処理は既定 CA の構成に限られ、検証をスキップする設定は行いません（`app/host/server/system-ca.mjs:10-20`）。

## ログと測定値

この変数の判定、system CA の取得失敗、空の CA、TLS API の不在について、`system-ca.mjs` はログを出さず、例外も呼び出し元へ再送出しません。いずれも戻り値は `'bundled'` です。正常に CA を設定した場合の戻り値は `'system'` ですが、エントリポイントは戻り値を記録していません（`app/host/server/system-ca.mjs:10-24`、`app/host/server/index.mjs:4`）。この変数に関する測定値はありません。

## 根拠

- `app/host/server/system-ca.mjs:10-24` — 値の完全一致判定、TLS API の有無・system CA の検査、bundled CA との結合、例外時の fallback、モジュール評価時の適用。
- `app/host/server/index.mjs:1-5` — サーバーエントリポイントから HTTPS 要求前にモジュールを import。
- `app/host/server/agent/harness-runtime.mjs:20-36,80-83` — エージェント子プロセス用の環境フィルタと `NODE_USE_SYSTEM_CA=1` の設定。
