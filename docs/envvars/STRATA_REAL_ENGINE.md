# `STRATA_REAL_ENGINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 同梱 Desktop host（`apps/host/server` の Node.js 実装）で、モデル一覧・ロード処理・監視表示を実モデル向けにするか、デザイン確認用の simulated mode にするかを選びます。ホストプロセス自身が読む設定であり、環境変数を llama.cpp や GPU driver に渡す処理ではありません。

ただし「real」は単一の engine 実装を意味しません。モデルをロードするときは Strata が supervisor 経由で llama.cpp を起動します。一方、チャット推論はまず Strata API worker を探し、次に supervisor 管理 engine、既知の OpenAI 互換 server を試します。いずれも見つからないときの simulated 応答可否もこの変数が関係します。

## 値と判定

主要な比較は文字列全体に対する厳密な `=== '1'` です。数値変換、trim、大小文字の変換はありません。

| 値 | モデル・カタログ・monitor の判定 | 推論の `requiresRealEngine()` 判定 |
|---|---|---|
| 未設定、空文字、`0`、`true`、`1x`、` 1` など | simulated 側 | `STRATA_PACKAGED === '1'` でなければ demo 可 |
| 正確に `1` | real 側 | `STRATA_FORCE_DEMO === '1'` かつ packaged でなければ demo 可。それ以外は real backend 必須 |

`STRATA_FORCE_DEMO=1` は推論判定だけに作用し、`STRATA_PACKAGED=1` のときは無視されます。モデルカタログと monitor の分岐はこの2変数を参照せず `STRATA_REAL_ENGINE` だけを見るため、開発環境で `STRATA_REAL_ENGINE=1` と `STRATA_FORCE_DEMO=1` を同時設定すると、モデル・monitor は real 扱いのまま推論だけ demo になり得ます。packaged host は Tauri が両方 `STRATA_PACKAGED=1` と `STRATA_REAL_ENGINE=1` に設定します。

## 有効になる条件

- Node.js の Desktop host が対象です。候補名の読み取りは `apps/host/server` にあり、C++/CUDA/HIP/SYCL 本体での読み取りは見つかりませんでした。
- `STRATA_REAL_ENGINE=1` でも、real 推論 backend が自動的に起動するわけではありません。既存の Strata worker、supervisor 管理 engine、または認識された互換 server が接続できなければ失敗経路になります。
- `STRATA_REAL_ENGINE` が `1` 以外で、推論側も `STRATA_PACKAGED=1` でなく `STRATA_FORCE_DEMO=1` でもない場合は、接続先がない時に demo engine が選ばれます。
- `STRATA_PACKAGED=1` は推論の demo fallback を禁止しますが、`models.REAL` や monitor の値判定そのものは上書きしません。Tauri の通常起動と self-test は両方の変数を `1` に設定します。
- OS、CUDA/HIP/SYCL backend、build macro、CLI 引数による値の上書きは、この変数の読み取り箇所では確認できません。`apps/desktop/scripts` と `apps/host/scripts` にある E2E / preview 起動スクリプトは子 host に `1` または `0` を明示設定しますが、製品 host の別の値 parser ではありません。

## 実行時の詳細

### モデル一覧とロード

`models.mjs` の `REAL` と `catalog.mjs` の組み込みカタログ選択は、モジュール読み込み時に一度評価されます。`1` なら real catalog、モデル状態とロードは実ファイル・engine 状態を使い、モデル load は `supervisor.restart()` を呼びます。`1` 以外ならデザイン用バリアントを一覧にし、install/load/unload の一部を simulated state として扱います。環境を同一プロセス内で後から変更しても、これらの定数や既に作成された catalog は再評価されません。

起動時に `1` の場合だけ、保存状態の `loaded` または `current` を `startupModelId` とし、700 ms 後にその variant が存在しディスク上にあることを確認して自動 load を試みます。成功・失敗はそれぞれ `autostart · loading ...` と `autostart failed: <message>` の stdout/stderr ログに現れます。値が `1` でない場合、この自動 load は行われません。

real mode のモデル一覧から実行できないスターター catalog の新規ダウンロード要求は、ネットワーク要求前に status 409 のエラーになります（ログ文言: `The app downloads models from the Models screen of the native engine, not from this list.`）。実ファイルがあり load を選ぶと supervisor の engine 起動に進みます。engine 再起動 API は環境値が厳密に `1` でなければ `Restart is unavailable with the example engine. Save settings for the next load.` で拒否します。

### 推論と観測結果

推論判定は `requiresRealEngine()` の呼び出し時に環境を直接読みます。`STRATA_FORCE_DEMO=1`（かつ packaged でない場合）が先に demo を許し、それ以外では `STRATA_REAL_ENGINE=1` または `STRATA_PACKAGED=1` が real engine 必須にします。host は Strata worker を先に probe し、次に supervisor engine、既知の互換 server を試します。real 必須なのにどれも見つからない場合、backend は `unavailable` となり、`streamChat()` は `No Strata engine answered at ... and no supervised engine is running. Start Strata (or load a model) and retry. Simulated output is disabled in this build.` を含む例外を投げます。リクエスト経路は serving entry を error で完了し、`type: 'error'` frame を送り、エラー本文を返します。

real 必須でない場合は demo backend が選ばれ、固定の demo 応答と `demo: true` の frame を出します。起動時の console 表示は `models.REAL` の値を使い、非 real 判定なら `inference · simulated (design iteration) — set STRATA_REAL_ENGINE=1 for a real engine` と表示します。real 判定では検出 backend に応じた表示となり、接続がなければ `No Strata engine` などになります。

### monitor

monitor は 1 秒ごとの tick や snapshot 生成などで環境値を都度参照します。値が `1` 以外なら GPU/CPU/RAM、temperature、throughput、expert cache、prompt/output throughput に demo source またはシミュレート値を使います。値が `1` ならこれらの demo 値を抑え、throughput は engine metrics がなければ `none`、thermal は `none`、memory はモデル状態に応じて `estimated` または `none` とします。温度読取 API の呼び出しも `1` かつ monitor が watch 対象期間内という条件付きです。`STRATA_FORCE_DEMO` は monitor 判定に影響しません。

### 読み取り時期と cache

モデル定数・カタログは Node.js の ES module 初期化時に固定されます。`startupModelId` も host boot 時に決定します。推論の `requiresRealEngine()` は backend 検出の都度評価しますが、`detectBackend()` は検出結果を最大20秒再利用する経路があり、その間は環境値を変更しても cached backend が返ることがあります。monitor の直接参照は tick/snapshot 等の実行ごとに評価されます。ソースには外部プロセスから起動中 Node プロセスの環境を更新する仕組みはありません。

## 根拠

- `apps/host/server/models.mjs:12-20,37-50,54-90,93-130,146-159,207-243,332-335` — `REAL` の厳密比較、simulated/real のモデル状態・install/load 分岐。
- `apps/host/server/catalog.mjs:10-33` — `REAL` によるカタログ選択。
- `apps/host/server/index.mjs:254-276,278-284` — 起動時モデル選択、自動 load、起動ログ。
- `apps/host/server/inference.mjs:38-42,84-156,199-235,480-524` — packaged / force-demo を含む実推論判定、backend 探索、unavailable と demo 経路。
- `apps/host/server/index.mjs:675-759` — 推論 request 呼び出し、serving error 終了と error frame。
- `apps/host/server/engine.mjs:195-220` — restart の環境値 guard と no-model warning / restart ログ。
- `apps/host/server/monitor.mjs:83-100,125-133,142-200,296-312,323-347` — demo telemetry 判定と定期・snapshot 時の読み取り。
- `apps/desktop/src-tauri/src/main.rs:463-477,734-744` — 製品 host と self-test の起動環境で `STRATA_PACKAGED=1`、`STRATA_REAL_ENGINE=1` を設定。
- 候補一覧: `docs/envvars/000_envvers.md:1404`。設計資料 `apps/host/docs/native-engine-handover.md:46` はこの変数を旧 GGUF/llama adapter の real/simulated 切替として記述しています。これは host の本番実装で確認できるカタログ・load・推論・monitor の条件と整合しますが、native adapter 自体の動作をこの変数の効果とはしていません。
