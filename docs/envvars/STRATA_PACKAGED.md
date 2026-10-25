# `STRATA_PACKAGED`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

デスクトップアプリが起動する Node ホストに、パッケージ版として動作していることを示します。主な効果は、実推論エンジンがないときにデモ生成へ進ませないことと、アプリ実行中のエンジン／コネクタの自動取得を拒否することです。ホストの control status にもパッケージ版かどうかを表示し、起動時に管理対象エンジンの残存プロセスを整理します。

これは環境変数名の候補一覧に含まれますが、Strata の C++ 推論エンジンが読む設定ではありません。デスクトップシェルからホストプロセスへ渡され、ホストの JavaScript が参照します。

## 値と判定

| 値 | パッケージ版判定 | 推論で実エンジン必須 | 取得禁止 |
|---|---:|---:|---:|
| 未設定、空文字、`1` 以外 | いいえ | `STRATA_REAL_ENGINE=1` がなければいいえ | `STRATA_NO_ACQUIRE` 側の条件次第 |
| 文字列 `1` | はい | はい | はい |

判定は数値変換や truthy 判定ではなく、文字列全体の `=== '1'` 比較です。したがって `01`、`true`、` 1`、空文字は `STRATA_PACKAGED` 単独では有効になりません。実行時に環境を書き換えた場合の再評価を止めるキャッシュはなく、参照箇所で `process.env` が読まれます。

推論の実エンジン必須判定には優先順位があります。`STRATA_FORCE_DEMO=1` は、`STRATA_PACKAGED` が `1` でない場合だけ実エンジン必須を解除します。パッケージ版では解除できません。`STRATA_REAL_ENGINE=1` は実エンジン必須にもします（`apps/host/server/inference.mjs:38-42`）。

## 有効になる条件

- この環境変数を使うのは Strata の Node ホストです。デスクトップの Tauri シェルは通常のホスト起動時に `STRATA_PACKAGED=1` と `STRATA_REAL_ENGINE=1` を明示して子プロセスを起動します。シェルの自己診断用ホストも両方を設定します（`apps/desktop/src-tauri/src/main.rs:451-461,719-726`）。
- ホストを単独で起動する場合、`STRATA_PACKAGED=1` を設定しない限り、パッケージ版専用の分岐は入りません。
- 推論では Strata worker、管理下の llama.cpp、識別できた localhost の OpenAI 互換サーバーが使える場合、それらへの接続は引き続き試されます。実エンジン必須時にそれらが見つからなければ demo backend ではなく `unavailable` になります（`apps/host/server/inference.mjs:84-157`）。
- 取得拒否は `STRATA_NO_ACQUIRE` と共通の判定です。そちらが `1` / `true` / `yes` / `on`（前後空白除去後、大文字小文字を無視）でも拒否されます。`STRATA_PACKAGED` 側はその正規化を行わず、値が厳密に `1` の場合だけ拒否条件になります（`apps/host/server/acquisition.mjs:12-30`）。

## 実行時の詳細

推論 backend の検出は、まず明示 URL または既定の `http://127.0.0.1:8095/v1` にある Strata worker を探し、次に管理下の engine と localhost の候補を調べます。実エンジン必須でいずれも利用できない場合、backend は `unavailable` として記録されます。後続の `streamChat()` はその backend でエラーを投げるため、合成された demo 応答を返しません。エラー文には `Simulated output is disabled in this build.` が含まれます（`apps/host/server/inference.mjs:84-157,199-235`）。

エンジンの検索・インストールは実際のネットワーク処理より前に共通 `requireAcquisition()` を呼びます。拒否時は `AcquisitionRefused`（code `acquisition_refused`、HTTP status `409`）が投げられます。エンジン取得 API はその status とメッセージを応答に含めます（`apps/host/server/engine-install.mjs:68-88`; `apps/host/server/index.mjs:1530-1536`; `apps/host/server/acquisition.mjs:14-30`）。Cloudflare connector は既存の利用可能な connector を探した後、新規インストールが必要な場合に同じ拒否判定を行います（`apps/host/server/cloudflared-install.mjs:46-55`）。

`GET /api/control/status` の `packaged` フィールドは同じ厳密比較の結果です（`apps/host/server/index.mjs:1271-1282`）。管理機能がある場合、ホストは listen 開始後に `STRATA_PACKAGED=1` のときだけ `control.cleanup()` を非同期で呼び、残存 engine の整理を試みます。失敗はこの呼び出し元では握りつぶされます（`apps/host/server/index.mjs:2207-2210`）。

パッケージ版で監視の合成メトリクスを無効にするのは `STRATA_PACKAGED` 自体ではなく、シェルが合わせて設定する `STRATA_REAL_ENGINE=1` です。monitor の判定は後者を直接参照します（`apps/desktop/src-tauri/src/main.rs:457-461`; `apps/host/server/monitor.mjs:71-74,147,167-179,287-289`）。

## 根拠

- 値の判定と推論時の優先順位: `apps/host/server/inference.mjs:38-42`。
- backend の検出、unavailable への分岐、demo backend の抑止: `apps/host/server/inference.mjs:84-157,199-235`。
- 取得禁止の判定と拒否エラー: `apps/host/server/acquisition.mjs:12-30`。
- エンジン／connector 取得前の確認: `apps/host/server/engine-install.mjs:68-88`; `apps/host/server/cloudflared-install.mjs:46-55`。
- パッケージホストの起動環境: `apps/desktop/src-tauri/src/main.rs:451-465,719-729`。
- status 表示、起動時 cleanup: `apps/host/server/index.mjs:1271-1282,2207-2210`。
- デスクトップシェルの取得禁止設計の説明: `docs/SAFETY.md:63-68`。
