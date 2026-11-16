# `STRATA_REAL_ENGINE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

App Host のモデルカタログとモデルライブラリを実モードにし、推論側で実エンジンが必須かどうかを決め、デモ用の監視値の一部を抑制する。通常のソース実行では unset がデザイン反復用のシミュレーションモードであり、`'1'` で実モードになる。パッケージ版の Desktop はホスト子プロセスにこの値を `'1'` で明示設定する（`apps/host/server/catalog.mjs:24-34`、`apps/host/server/models.mjs:12-21`、`apps/desktop/src-tauri/src/main.rs:467-485`）。

「実モード」はモデルの選択・インストール・ロード経路を切り替えるが、モデルや推論サーバーを自動で用意する意味ではない。実モードで、モデルがまだディスク上になく既存のダウンロード処理もない状態でモデル一覧の install 処理に入ると HTTP 409 で拒否する。ロードにはモデルがディスク上に存在する必要があり、ロード時は `supervisor.restart` を呼ぶ（`apps/host/server/models.mjs:146-160,207-243`）。推論は既存の Strata worker、起動済み supervisor engine、または検出した OpenAI 互換サーバーへ接続し、実エンジン必須なのにどれも利用できなければシミュレーションせずエラーにする（`apps/host/server/inference.mjs:84-155,198-234`）。

## 値と判定

Strata の各箇所は数値変換をせず、文字列 `'1'` との完全一致で判定する。大文字小文字、前後空白、数値としての解釈は関係しない。空文字・`'0'`・`'true'`・`'1anything'`・`' 1'` はすべて `'1'` と一致せず、実モード判定は false になる。多くの箇所で unset も同様に false 扱いだが、推論側では `STRATA_PACKAGED` の値も合わせて判定する（`apps/host/server/models.mjs:20`、`apps/host/server/catalog.mjs:24`、`apps/host/server/inference.mjs:38-42`）。

| 条件 | unset | `'1'` | その他の設定値（例） |
|---|---|---|---|
| カタログ・モデルライブラリ | デザイン用モデル一覧／シミュレーション | `REAL_VARIANTS` と実モデル経路 | unset と同じ。空文字も無効 |
| 推論の実エンジン必須判定 | `STRATA_PACKAGED !== '1'` なら false | true。ただし後述の `STRATA_FORCE_DEMO` 優先条件あり | `STRATA_PACKAGED === '1'` なら true、そうでなければ false |
| 監視表示・restart 判定 | デモ値を使う側／restart を拒否 | 一部デモ値を抑制し restart を許可 | unset と同じ |

実モード判定の主要実装は `apps/host/server/catalog.mjs:24`、`apps/host/server/models.mjs:20`、`apps/host/server/inference.mjs:38-42`、`apps/host/server/monitor.mjs:89-103,172-194`、`apps/host/server/engine.mjs:195-197` にある。

## 有効になる条件

- OS / backend / build macro による Strata 側の値判定差はない。判定は App Host の Node.js コードで行われる。Desktop の通常起動と自己テスト起動はそれぞれ `STRATA_PACKAGED=1` と `STRATA_REAL_ENGINE=1` をホスト子プロセスに設定する（`apps/desktop/src-tauri/src/main.rs:467-485,738-749`）。
- 推論側では `STRATA_FORCE_DEMO === '1'` かつ `STRATA_PACKAGED !== '1'` のとき、先に実エンジン必須判定を false にする。この組合せでは `STRATA_REAL_ENGINE=1` であっても推論 fallback は demo になり得る。`STRATA_PACKAGED=1` の場合は `STRATA_FORCE_DEMO` による上書きはなく、最後に `STRATA_PACKAGED` が true を返す（`apps/host/server/inference.mjs:38-42,131-155`）。
- `STRATA_PACKAGED=1` 単独でも推論側は実エンジン必須になる。ただしカタログと `models.REAL` は `STRATA_REAL_ENGINE` だけで決まり、`STRATA_PACKAGED` では切り替わらない（`apps/host/server/catalog.mjs:24`、`apps/host/server/models.mjs:20`、`apps/host/server/inference.mjs:38-42`）。
- `STRATA_REAL_ENGINE=1` でも推論の実応答には接続先の worker / engine / 対応サーバーが必要である。Strata worker は `STRATA_SERVER_URL` または既定の `http://127.0.0.1:8095/v1` を調べ、その他の候補も探索する。どれも使えない場合は「No Strata engine answered ... Simulated output is disabled in this build.」をエラーにし、チャット要求を失敗させる（`apps/host/server/inference.mjs:19-26,44-49,84-155,198-234`）。
- 実モードのモデルロードは対象モデルがディスク上にある場合だけ進み、`supervisor.restart` の失敗はモデル状態を `error` にして `loaded` をクリアしたうえで呼び出し元へ再送出する（`apps/host/server/models.mjs:207-243`）。
- モデル restart API は実モードでないと `Restart is unavailable with the example engine. Save settings for the next load.` を throw する（`apps/host/server/engine.mjs:195-197`）。
- このフラグによる GPU / OS 制限の追加判定は確認できない。監視処理は別途、GPU telemetry reader や system sampler の結果を利用する（`apps/host/server/monitor.mjs:130-139,88-105`）。

## 実行時の詳細

- `catalog.mjs` はモジュール評価時に built-in variant 一覧を選び、`models.mjs` は同じくモジュール評価時に `REAL` を定数へ保存する。通常のホスト起動後に `process.env` を変更しても、このカタログ選択と `REAL` は更新されない。ライブラリ初期化は `REAL` に応じてデモ状態の補正を行い、実モード時はファイル有無を基準にインストール状態を整える（`apps/host/server/catalog.mjs:24-34`、`apps/host/server/models.mjs:20,54-89`）。
- 推論側の `requiresRealEngine()` は呼び出しごとに環境を参照する。起動時に `detectBackend({ force: true })` が一度実行され、チャットの `streamChat` も backend を検出する。検出結果は一部の経路で最大 20 秒再利用されるため、プロセス内で環境を後から変更した場合は、モジュール定数と検出 cache が同時には更新されない（`apps/host/server/index.mjs:260-268`、`apps/host/server/inference.mjs:38-42,84-155,198-200`）。
- 監視モジュールは `process.env` を tick・snapshot・監視値更新時に直接読み直す。unset / `'1'` 以外では GPU 読み取り値の代わりに `source: 'demo'` の GPU 値、一部の RAM / VRAM 使用量、温度、prompt/output throughput 等のデモ値を作る。`'1'` ではこれらの一部を `none` または実測・engine 由来の値にし、drive 温度読み取りも Monitor 表示中などの時間条件が揃った場合だけ呼ぶ。ただし GPU load / GPU 温度ターゲットなど、監視内のすべての数値がこの変数だけで切り替わるわけではない（`apps/host/server/monitor.mjs:88-105,130-205,301-352`）。
- `autostartModel` には `'1'` の場合に `loaded ?? current` を返す判定がある。ただし調査対象 commit のホストコードでこの関数を呼ぶ箇所は見つからなかったため、ホスト起動時の自動ロードが実際に行われるとは記載しない（`apps/host/server/autostart.mjs:12-19`）。
- ソース上の直接参照には、上記のほか index の起動時案内文と engine restart 判定がある。`models.REAL` は index 内の複数モデル/API経路にも渡され、実モードと simulated mode の分岐に使われる（`apps/host/server/index.mjs:127,170,250-257,661-734,1477-1548`）。

## ログと測定値

- Host 起動時、モデルライブラリが simulated 扱いなら stdout に `inference    ·  simulated (design iteration) — set STRATA_REAL_ENGINE=1 for a real engine` を表示する。実モードでは検出 backend 名など `inferenceLine` の結果を表示する（`apps/host/server/index.mjs:262-268`）。
- 実エンジン必須時に backend が見つからないと、`detectBackend` は上記の説明文字列を含む `unavailable` 状態を返し、`streamChat` がその文言で例外にする。チャット処理は error frame と serving error に反映する（`apps/host/server/inference.mjs:131-142,228-234`、`apps/host/server/index.mjs:679-714`）。
- 実モードでモデルが未取得かつ既存ダウンロードがない状態で install が呼ばれると、HTTP 409 と `The app downloads models from the Models screen of the native engine, not from this list.` を返す。この一覧側の install はモデル取得を実行しない（`apps/host/server/models.mjs:140-159`）。
- 性能値や実行比較の定量的測定は、この変数のソース実装および参照した説明資料では確認できなかった。

## 根拠

主な読み取り箇所は `apps/host/server/catalog.mjs:24`、`apps/host/server/models.mjs:20`、`apps/host/server/inference.mjs:38-42`、`apps/host/server/monitor.mjs:89,135,172,184,187,192,312,334,351`、`apps/host/server/engine.mjs:196`。Desktop による値設定は `apps/desktop/src-tauri/src/main.rs:477,744`。
