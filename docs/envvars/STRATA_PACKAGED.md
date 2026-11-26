# `STRATA_PACKAGED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Host がインストール済み desktop app として動いていることを示すフラグ。desktop shell は Host の子プロセス起動時に `STRATA_PACKAGED=1` を設定し、同時に `STRATA_REAL_ENGINE=1` も設定する。Host はこの値を使い、実エンジンが無い場合にデモ推論へ切り替えない、ソフトウェア取得を拒否する、パッケージ状態を API で返すなどの処理を行う。値だけで Host 全体のシミュレーションを切り替えるわけではなく、カタログやモデル状態等の通常モードは `STRATA_REAL_ENGINE` にも依存する（`app/desktop/src-tauri/src/main.rs:522-537`、`app/host/server/inference.mjs:40-50`、`app/host/server/models.mjs:18-20`）。

## 値と判定

本番 Host の読み取りはいずれも `process.env.STRATA_PACKAGED === '1'` の厳密比較で、数値変換や大文字小文字変換はしない。未設定、空文字、`0`、`false`、`true`、`0anything`、`01`、`1anything` は `"1"` と一致しない。`"1"` だけが一致する（`app/host/server/inference.mjs:47-50`、`app/host/server/acquisition.mjs:24-26`、`app/host/server/region.mjs:62-64`、`app/host/server/index.mjs:1427-1429,2571-2575`）。

| 判定箇所 | unset / 空文字 / `"true"` 等 | `"1"` | 優先関係 |
|---|---|---|---|
| 推論で実エンジンを必須にするか | `STRATA_FORCE_DEMO=1` ならデモ可。それ以外は `STRATA_REAL_ENGINE=1` なら必須、どちらも該当しなければデモ可 | 必須。`STRATA_FORCE_DEMO=1` でも解除されない | `STRATA_PACKAGED=1` が最優先。通常時は `STRATA_FORCE_DEMO=1` が `STRATA_REAL_ENGINE=1` より先に判定される |
| 取得禁止 | `STRATA_NO_ACQUIRE` が `1`/`true`/`yes`/`on`（前後空白除去・小文字化後）なら禁止、それ以外はこの変数による禁止なし | 禁止 | どちらかの条件で禁止 |
| テスト用 locale 上書き | `STRATA_TEST_LOCALE` が truthy なら上書き候補になる | 上書きを抑止 | `"1"` の場合、OS locale 検出へ進む |
| `/api/control/status` の `packaged` と listen 後の処理 | `false`。packaged 固有処理を行わない | `true`。Control がある場合に後述の処理を行う | 他変数との優先順位なし |

推論のデモ抑止は `STRATA_REAL_ENGINE` とは別に `STRATA_PACKAGED` 単独でも働く。ただし desktop shell は両方を設定する。`STRATA_TEST_LOCALE` は JS の truthy 判定なので unset と空文字は上書きせず、空白だけの文字列は候補として parse された後、locale 無しの結果になり得る（`app/desktop/src-tauri/src/main.rs:528-532`、`app/host/server/inference.mjs:47-50`、`app/host/server/region.mjs:62-65`）。

## 有効になる条件

- 推論の抑止は Host の `inference.mjs` を通る chat 経路で適用される。`STRATA_PACKAGED=1` でも Strata API worker、supervised engine、または識別された localhost の OpenAI 互換サーバーが使える場合は、その実エンジン経路を選ぶ。どれも無い場合は demo backend を返さず `unavailable` となる（`app/host/server/inference.mjs:93-165`）。
- `/api/control/status` の `packaged` 表示と listen 後処理は `control` が生成されている場合だけ Control 部分が動く（`app/host/server/index.mjs:1418-1436,2569-2576`）。
- 取得禁止は `cloudflared` の自動インストールで `requireAcquisition` に到達した場合に適用される。既に利用可能な connector が見つかる場合はそのまま返り、モデルをユーザーが明示的にダウンロードする操作はこの helper の対象外（`app/host/server/cloudflared-install.mjs:46-52`、`app/host/server/acquisition.mjs:7-9,24-30`）。
- locale の抑止は `/api/locale` が `systemLocale()` を呼ぶ経路で有効。`STRATA_PACKAGED=1` では `STRATA_TEST_LOCALE` を使わず、OS の locale 情報を検出する（`app/host/server/index.mjs:2217`、`app/host/server/region.mjs:32-55,58-65`）。
- desktop shell の通常 Host 起動では値を `"1"` に固定し、`STRATA_REAL_ENGINE=1` も同時に渡す。self-test 起動でも両方を `"1"` にする（`app/desktop/src-tauri/src/main.rs:522-537,797-807`）。OS/backend の個別分岐はこの値の比較にはない。

## 実行時の詳細

- desktop shell が Host 子プロセスを起動するとき環境へ設定する。推論の `requiresRealEngine()`、取得判定、locale 分岐、状態 API は Host 実行中に `process.env` を参照する。`requiresRealEngine()` 自体に static cache はないが、起動時に `detectBackend({ force: true })` が一度評価され、backend の状態を保持する。以後の chat でも `detectBackend()` が呼ばれる。backend の一部候補結果は 20 秒間再利用される（`app/desktop/src-tauri/src/main.rs:522-537`、`app/host/server/inference.mjs:37-50,93-120,142-165,209-210`、`app/host/server/index.mjs:306-314`）。
- 推論先がすべて見つからず、実エンジン必須なら backend は `kind: 'unavailable'` となる。chat 側では `streamChat()` が `No Strata engine answered at … and no supervised engine is running. Start Strata (or load a model) and retry. Simulated output is disabled in this build.` の Error を投げ、Host はエラー frame として通知し、request を error 付きで終了する（`app/host/server/inference.mjs:142-153,241-246`、`app/host/server/index.mjs:732-768,785-797`）。
- 取得禁止時、connector が未導入で自動取得へ進もうとすると `AcquisitionRefused` を投げる。code は `acquisition_refused`、status は `409`、message は `<対象> is not installed here, and the app never downloads it while it runs. Install it from <案内>.`（`app/host/server/acquisition.mjs:14-21,28-30`、`app/host/server/cloudflared-install.mjs:46-52`）。
- listen 完了後、`control` があり値が `"1"` なら `control.cleanup()` を開始し、`native.refresh(false)` で初回状態を読み込む。refresh の失敗はこの呼び出しでは握りつぶされ、ページ側の読み取りに委ねる（`app/host/server/index.mjs:2569-2576`）。
- locale は通常検出結果を module-level `cached` に保持する。packaged の場合はこの cache を使う通常経路に入り、`STRATA_TEST_LOCALE` は参照しない（`app/host/server/region.mjs:58-65`）。

## ログと測定値

この変数固有のログ出力や測定値はない。確認可能な結果は `/api/control/status` の `packaged` boolean、推論 backend の `unavailable` と chat error frame、取得拒否の例外、および `/api/locale` の結果である（`app/host/server/index.mjs:1418-1436,2217`、`app/host/server/inference.mjs:142-153`、`app/host/server/acquisition.mjs:14-21`）。

## 根拠

- `app/desktop/src-tauri/src/main.rs:522-537,797-807` — desktop shell と self-test Host に `"1"` を設定。
- `app/host/server/inference.mjs:40-50,93-165,209-210,241-246` — 実エンジン必須判定、backend 選択、demo 禁止時の unavailable / Error。
- `app/host/server/acquisition.mjs:7-9,12-30`、`app/host/server/cloudflared-install.mjs:46-52` — 取得禁止判定と拒否。
- `app/host/server/region.mjs:32-65`、`app/host/server/index.mjs:2217` — テスト用 locale の抑止と `/api/locale`。
- `app/host/server/index.mjs:1418-1436,2569-2576` — packaged 状態 API、listen 後の cleanup と初回 refresh。
- `app/host/server/models.mjs:18-20` — モデルの real/simulated モードは `STRATA_REAL_ENGINE` から決定。

