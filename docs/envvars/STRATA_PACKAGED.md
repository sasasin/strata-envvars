# STRATA_PACKAGED

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

Desktop shell が起動する App Host に STRATA_PACKAGED=1 を渡し、host に「配布アプリとして動作中」であることを知らせる内部フラグである。shell の host_command は caller の値を継承するだけでなく、子 Node プロセスの環境に "1" を明示して設定する。self-test 用の host 起動経路も同じ値を設定する（app/desktop/src-tauri/src/main.rs:522-540,797-806）。

Host では、推論の demo fallback の禁止、STRATA_TEST_LOCALE による locale 上書きの無効化、Control 状態 API の packaged 表示、起動時の Control cleanup / native refresh、ソフトウェア取得の禁止判定に使う（app/host/server/inference.mjs:47-50; app/host/server/region.mjs:60-65; app/host/server/index.mjs:1427-1435,2569-2575; app/host/server/acquisition.mjs:24-30）。この変数単独ではモデルライブラリを real mode にしない。ライブラリの REAL は別の STRATA_REAL_ENGINE === '1' だけで決まり、Desktop shell は両方を host に設定する（app/host/server/models.mjs:12-20; app/desktop/src-tauri/src/main.rs:528-532）。

## 値と判定

Host の読み取りは JavaScript の文字列全体に対する厳密比較 === '1' / !== '1' である。truthy 判定、trim、数値変換はしない。未設定と空文字は同じく '1' と一致せず、0、true、01、1 、 1、大文字小文字を変えた値も packaged 条件を満たさない。値を受け付けない場合の警告や fallback はこの比較自体からは発生しない（app/host/server/inference.mjs:47-50; app/host/server/region.mjs:63; app/host/server/index.mjs:1428,2572,2575; app/host/server/acquisition.mjs:25）。

| 条件 | unset / 空文字 | '1' | その他の値 |
|---|---|---|---|
| requiresRealEngine()。ただし STRATA_FORCE_DEMO === '1' かつ packaged でない場合を除く | packaged 理由では false。STRATA_REAL_ENGINE === '1' なら true | true。STRATA_FORCE_DEMO=1 でも false に戻せない | packaged 理由では false。STRATA_REAL_ENGINE === '1' なら true |
| acquisition.forbidden() | この変数による禁止なし。STRATA_NO_ACQUIRE も別途評価 | true | この変数による禁止なし。STRATA_NO_ACQUIRE も別途評価 |
| /api/control/status の packaged | false | true | false |
| systemLocale() の STRATA_TEST_LOCALE 分岐 | packaged ではないものとして扱う | 分岐を抑止 | packaged ではないものとして扱う |
| listen 後の cleanup / refresh | 実行しない | control が存在すれば両方を開始 | 実行しない |

STRATA_FORCE_DEMO と STRATA_REAL_ENGINE の比較も文字列全体の厳密比較である。モデルライブラリは host 起動時に STRATA_REAL_ENGINE を一度読んで REAL 定数に保持するため、そこでは実行中の環境変更は反映されない（app/host/server/inference.mjs:47-50; app/host/server/models.mjs:20）。

## 有効になる条件

- Desktop packaged 実行では shell が子 host の値を必ず '1' に設定する。通常 host では shell によるこの設定はなく、起動側が渡さなければ packaged 条件は成立しない（app/desktop/src-tauri/src/main.rs:522-540; app/host/server/index.mjs:1428）。
- 推論で demo を禁止するには、Strata worker、監視対象の supervised engine、または採用可能な OpenAI-compatible server のいずれかが実際に利用可能である必要がある。どの real backend も見つからないと unavailable backend になり、demo 応答ではなくエラーを返す（app/host/server/inference.mjs:93-166,209-246）。
- STRATA_FORCE_DEMO=1 は packaged でない時だけ real-engine 要求を解除する。STRATA_PACKAGED=1 と同時なら解除できない（app/host/server/inference.mjs:47-50）。
- packaged フラグだけではモデルライブラリの mode、ロード状態、monitor の real 計測を切り替えない。それらの経路は STRATA_REAL_ENGINE=1 を参照する。Desktop shell は両方を設定するが、手動起動で片方だけ渡す場合は機能が分かれる（app/host/server/models.mjs:17-20,93-108; app/host/server/index.mjs:296-314; app/desktop/src-tauri/src/main.rs:528-532）。
- locale 上書き抑止は systemLocale() の通常呼び出しで適用される。明示的な options を渡す呼び出しは先に detectRegion(options) を返すため、この packaged 判定を通らない。HTTP /api/locale は options なしで呼び出す（app/host/server/region.mjs:58-65; app/host/server/index.mjs:2217）。
- 起動時 cleanup / native refresh は control が存在する場合に限る。refresh は読み取りだけで、失敗は catch されて起動を止めない（app/host/server/index.mjs:2569-2575）。
- connector の自動取得禁止は「必要になった場合」に限る。既存 connector の探索後、見つからずインストールへ進む場合に acquisition 判定が行われる。STRATA_NO_ACQUIRE も同時に禁止条件となる（app/host/server/cloudflared-install.mjs:46-52; app/host/server/acquisition.mjs:24-30）。

## 実行時の詳細

host_command は App Host entry を子 Node に渡す際に STRATA_PACKAGED=1 と STRATA_REAL_ENGINE=1 を設定する。この設定は親 shell の値や CLI 引数から選択されるものではない（app/desktop/src-tauri/src/main.rs:501-540）。host の環境参照は通常 process.env から行われる。推論の requiresRealEngine() は backend 判定のたびに環境値を読む一方、detectBackend() は検出 backend を module 内に保持し、通常呼び出しで最大 20 秒間再利用する。したがって起動後に環境を変更した場合、すでに cache された backend が最大 20 秒残ることがある（app/host/server/inference.mjs:37-50,93-120,142-166）。

起動時に control がある packaged host は listen 完了後に control.cleanup() と native.refresh(false) を fire-and-forget で開始する。/api/control/status はリクエストごとに現在の値との厳密比較結果を packaged として返す（app/host/server/index.mjs:1418-1436,2569-2575）。

実推論 backend がなく、requiresRealEngine() が true の場合、detectBackend() は kind: 'unavailable' を返し、streamChat() は No Strata engine answered at … and no supervised engine is running. Start Strata (or load a model) and retry. Simulated output is disabled in this build. を例外として投げる。チャット処理はそれを error frame と serving entry の error に載せる（app/host/server/inference.mjs:142-153,209-246; app/host/server/index.mjs:785-797）。packaged 値そのものについて stdout / stderr に専用ログはない。

connector が未導入で自動取得を試みると、AcquisitionRefused（code: acquisition_refused, status: 409）を投げる。例外文は <what> is not installed here, and the app never downloads it while it runs. Install it from <command>.。トンネル開始はこれを error state に保存して再送出する（app/host/server/acquisition.mjs:14-30; app/host/server/cloudflared-install.mjs:46-52; app/host/server/cloudflare.mjs:61-66,91-93）。

## ログと測定値

packaged 判定専用のログや測定値はない。推論 backend 不在時のエラーと connector 取得拒否の観測結果は「実行時の詳細」に記載した。Control の refresh 失敗は catch され、ページ側の読み取りに委ねられるため、この箇所からはログを出さない（app/host/server/index.mjs:2573-2575）。

## 根拠

- app/desktop/src-tauri/src/main.rs:501-551 — packaged host の子プロセス環境。
- app/host/server/inference.mjs:37-50,93-166,209-246 — 判定、backend cache、demo 禁止と unavailable 経路。
- app/host/server/models.mjs:12-20,93-108 — モデルライブラリは別変数で real mode を決定。
- app/host/server/region.mjs:58-65 — テスト locale の抑止。
- app/host/server/acquisition.mjs:14-30; app/host/server/cloudflared-install.mjs:46-52; app/host/server/cloudflare.mjs:61-66,91-93 — connector 取得判定と拒否。
- app/host/server/index.mjs:1418-1436,2217,2569-2575 — Control API、locale API、起動時処理。

docs/DETAILS.md には STRATA_PACKAGED の記述がなく、この変数に関する資料記述との照合対象はなかった。実装の説明は上記 commit の Strata 所有ソースに限定した。
