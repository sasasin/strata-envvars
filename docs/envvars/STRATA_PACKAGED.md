# `STRATA_PACKAGED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有コードを調査。

## 役割

Desktop shell が Host プロセスへ `STRATA_PACKAGED=1` を渡し、Host に「パッケージ済みアプリとして扱う」状態を伝えます。Host では主に、推論用デモへの fallback を禁止する判定、エンジン／connector の自動取得を拒否する判定、Control status の表示、および listen 完了後の Control cleanup に使います。Desktop shell の通常の Host 起動では `host_command()` がこの値を設定します。self-test の Host 起動でも設定します（`apps/desktop/src-tauri/src/main.rs:442-483,668-745`）。

## 値と判定

packaged-mode の判定は文字列の完全一致です。`true`、空文字、`01` などを `1` と同じ値には扱いません。地域設定の分岐だけは別途 `STRATA_TEST_LOCALE` の truthiness も見ます。

| 読み取り箇所 | `STRATA_PACKAGED=1` | unset、空文字、その他の値 |
|---|---|---|
| 推論の `requiresRealEngine()` | デモ推論を禁止 | この変数単独では禁止しない |
| 取得判定 `forbidden()` | 取得を禁止 | この変数単独では禁止しない |
| `/api/control/status` | `packaged: true` | `packaged: false` |
| Host の listen 完了 callback | `control` があれば `control.cleanup()` を呼ぶ | 呼ばない |
| `systemLocale()` のテスト locale 分岐 | `STRATA_TEST_LOCALE` を使う分岐を通らない | `STRATA_TEST_LOCALE` が truthy なら分岐する |

推論判定の優先順位は次のとおりです。

- `STRATA_PACKAGED=1` なら、`STRATA_FORCE_DEMO=1` があっても demo を許可しません。`STRATA_REAL_ENGINE` の値にもかかわらず `requiresRealEngine()` は true になります。
- packaged でない場合、`STRATA_FORCE_DEMO=1` は最初に評価され、`STRATA_REAL_ENGINE=1` より優先して false を返します。
- それ以外では `STRATA_REAL_ENGINE=1` なら true、そうでなければ false です。

取得判定は `STRATA_NO_ACQUIRE` の既存判定との OR です。`STRATA_NO_ACQUIRE` が `1` / `true` / `yes` / `on`（trim 後、大文字小文字を無視）でも取得禁止になります。`STRATA_PACKAGED` 側は厳密に `=== '1'` です。

根拠: `apps/host/server/inference.mjs:38-42`, `apps/host/server/acquisition.mjs:12-30`。

## 有効になる条件

この値を設定して Host を起動するのは Desktop shell のコードです。Rust の `host_command()` は Node Host のコマンドへ `.env("STRATA_PACKAGED", "1")` を加えます。self-test 用の別起動も同じ値を渡します。Host の listen 後処理は `control` が存在することも条件です（`apps/desktop/src-tauri/src/main.rs:463-483,734-745`; `apps/host/server/index.mjs:2262-2266`）。

デモ禁止は「特定 engine だけを必須にする」条件ではありません。Host は Strata worker、supervised engine、または検出できた OpenAI-compatible server を使える経路を先に調べ、実 engine が見つからない場合にだけ `requiresRealEngine()` に従って unavailable/demo を選びます。従って `STRATA_PACKAGED=1` は demo fallback を止めますが、他の実 backend の利用を止めません（`apps/host/server/inference.mjs:84-156`）。

`STRATA_TEST_LOCALE` は packaged でない場合だけテスト用地域設定として採用されます。地域情報の通常の検出結果は `systemLocale()` 内に cache されますが、これは `STRATA_PACKAGED` 自体の cache ではありません（`apps/host/server/region.mjs:58-65`）。

## 実行時の詳細

推論では Host の起動処理が `detectBackend({ force: true })` を呼び、後続の chat は `streamChat()` から backend を検出します。Strata worker、supervised engine、OpenAI-compatible server が見つからず、`requiresRealEngine()` が true なら backend は `kind: 'unavailable'` になり、エラー文に `Simulated output is disabled in this build.` を含めます。`streamChat()` はその backend で demo を実行せず例外を投げます。逆に実 engine 必須でない場合のみ `kind: 'demo'` に進みます。backend 情報は module 変数に保持され、非 engine backend は強制再検出でなければ 20 秒以内 cache されます。環境変数判定そのものを `static` 等へ保存する処理はなく、`requiresRealEngine()` の呼び出しごとに process environment を参照します（`apps/host/server/index.mjs:278-284`; `apps/host/server/inference.mjs:28-42,84-156,199-234`）。

取得制限は engine installer と connector installer が取得処理に入る前に `requireAcquisition()` を呼ぶ形です。禁止条件では `AcquisitionRefused`（`code: 'acquisition_refused'`, `status: 409`）を throw します。既に使える connector が見つかる場合、connector installer はそのパスを返すため取得判定まで進みません（`apps/host/server/engine-install.mjs:16,65-90`; `apps/host/server/cloudflared-install.mjs:46-52`; `apps/host/server/acquisition.mjs:14-30`）。

`/api/control/status` は完全一致の結果を JSON の `packaged` として返します。Host は listen 完了後、`control` があり値が `'1'` の場合に `control.cleanup().catch(() => {})` を開始します。cleanup の失敗はここでは握りつぶされます（`apps/host/server/index.mjs:1291-1303,2262-2266`）。

## ログと失敗経路

実 engine が見つからない packaged Host では、起動ログの `inference · ...` は Control の状態に応じて「エンジン未搭載」等を表示し、inference を必要とする要求は demo 応答の代わりに unavailable のエラーへ進みます。起動時の文言は `inferenceLine()` にあり、chat 側は unavailable backend のエラーを throw します（`apps/host/server/index.mjs:278-284`; `apps/host/server/inference.mjs:131-142,229-232,532-537`）。取得禁止時は `AcquisitionRefused` が発生しますが、ここで確認したコードは例外型・code・status を設定するところまでです。環境変数固有のログ文言は確認できません（`apps/host/server/acquisition.mjs:14-30`）。

## 根拠

- Desktop shell が Host と self-test Host の環境に値を設定: `apps/desktop/src-tauri/src/main.rs:442-483,668-745`。
- 推論での完全一致判定、demo 抑止、fallback: `apps/host/server/inference.mjs:38-42,84-156,199-234`。
- 取得禁止判定と typed error: `apps/host/server/acquisition.mjs:12-30`; 呼び出し元 `apps/host/server/engine-install.mjs:65-90`, `apps/host/server/cloudflared-install.mjs:46-52`。
- status API と listen 後 cleanup: `apps/host/server/index.mjs:1291-1303,2262-2266`。
- locale test 分岐: `apps/host/server/region.mjs:58-65`。
