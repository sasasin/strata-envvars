# `STRATA_REAL_ENGINE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象は Strata リポジトリのソースにある `apps/host` の旧 GGUF/llama.cpp アダプターとその Desktop 起動元。ネイティブ実行アダプターは別経路。

## 役割

`apps/host` の設計プレビュー用ホストで、カタログ、モデルのインストール・ロード、推論のフォールバック、モニター表示を実物の GGUF/llama.cpp エンジン向けにするか、シミュレーションにするかを選びます。`'1'` のときモデル一覧は実モデル一覧になり、ロードは監視対象の llama.cpp プロセスを起動します。未設定や `'0'` などでは設計用一覧とシミュレーション処理が選ばれます。

この変数は Strata C++ エンジンの一般的な切替ではなく、Strata 同梱 Desktop/host の JavaScript 実装で読むフラグです。ネイティブ実行アダプターはこのフラグと独立していると handover 文書に記載されています。

## 値と判定

値は数値として parse せず、文字列全体を `'1'` と厳密比較します。空文字、`'0'`、`'true'`、`' 1'`、`'1 '`、`'01'` はすべて `'1'` と一致しません。

| 状態 | モデル・カタログ側 (`models.REAL`, `catalog.mjs`) | 推論の実エンジン要否 (`requiresRealEngine()`) |
|---|---|---|
| 未設定、または値が厳密に `'1'` でない | シミュレーション側 | `STRATA_PACKAGED === '1'` でなければ demo fallback 可。packaged なら実エンジン必須 |
| `'1'` | 実モデル・実エンジン側 | 実エンジン必須。ただし非 packaged で `STRATA_FORCE_DEMO === '1'` の場合は、この関数だけは先に `false` を返す |

`STRATA_FORCE_DEMO` の例外は推論 backend 判定用の `requiresRealEngine()` に限られます。モデル一覧・ロードの `REAL` 定数、起動時 autoload、モニターの複数箇所は `STRATA_REAL_ENGINE` を直接比較するため、`STRATA_FORCE_DEMO=1` がそれらをシミュレーションへ切り替えるわけではありません。

## 有効になる条件

- `apps/host/server` を起動したプロセスで評価される場合に適用されます。開発時は既定でシミュレーションです。
- packaged Desktop は Rust の起動コードが host 子プロセスへ `STRATA_PACKAGED=1` と `STRATA_REAL_ENGINE=1` の両方を設定します。`requiresRealEngine()` は packaged ならシミュレーションを許可しません。Desktop 側の設定により、起動前の同名環境変数よりこの値が優先されます。
- 開発用 `apps/host/scripts/preview-ui.mjs`、`approval-flow.mjs`、`qa2-flows.mjs` は host 子プロセスの値をそれぞれ `'0'` に上書きし、demo/preview 経路で起動します。
- `STRATA_REAL_ENGINE=1` でも、実推論には Strata API worker、監視中のエンジン、または検出対象の OpenAI-compatible server のいずれかが必要です。検出できない場合は `unavailable` backend になり、推論要求はエラーにします。実エンジンを自動的に用意する指定ではありません。
- モデルカタログで `'1'` のときは `REAL_VARIANTS`、それ以外は `DESIGN_FAMILIES` から合成したバリアントを使用します。実モードで一覧にないモデルのダウンロードは拒否されます（`models.mjs` の `LIST_DOWNLOAD_REFUSED`）。
- 別のネイティブ実行経路 (`native-runtime` adapter) の動作選択には適用されません。

## 実行時の詳細

`models.mjs` はモジュール読み込み時に `REAL` を一度定数化し、`catalog.mjs` も同時に組み込みカタログを選びます。`index.mjs` は起動時に `'1'` の場合だけ保存済みの loaded/current モデルを autoload 対象とし、起動ログには実モードかシミュレーションかを表示します。この初期化後にプロセス内で値を書き換えても、これらの定数・起動処理は再評価されません。

シミュレーション側ではモデルの install/load は進捗を擬似生成し、インストール完了を state file に記録します。推論 backend の探索で実 server が見つからず、かつ packaged でもなければ demo completion に進みます。実モードではモデル load が supervisor を通じて llama.cpp を起動し、推論先が見つからないと `No Strata engine answered at ...` を含むエラーになります。engine restart は実モード以外では `Restart is unavailable with the example engine. Save settings for the next load.` を投げます。

モニターは `'1'` 以外のとき GPU/VRAM/RAM/throughput/温度などのデモ値を生成し、telemetry source に `demo` を付けます。`'1'` では合成負荷を更新せず、実測がない telemetry は `none` として扱う箇所があります。モニターの関数は `process.env` を呼び出し時に直接参照する一方、`models.REAL` とカタログはモジュール初期化時に固定されます。したがって実行中の環境変更を一貫した切替手段としては扱えず、切替はプロセス起動前に設定する必要があります。

## 根拠

- `apps/host/server/models.mjs:12-20,146-159,207-244,246-261,264-329` — 厳密比較、モデル mode、実際の install/load/unload 分岐。
- `apps/host/server/catalog.mjs:13-33` — 実モデル一覧と設計用一覧の選択。
- `apps/host/server/inference.mjs:31-42,84-156,199-235` — packaged/force-demo 条件、backend 探索、実推論不能時のエラーと demo fallback。
- `apps/host/server/index.mjs:234-264` — 起動時 autoload 判定と mode の起動ログ。
- `apps/host/server/engine.mjs:195-220` — シミュレーション時の restart 拒否。
- `apps/host/server/monitor.mjs:70-80,135-172,276-328` — demo telemetry と動的な環境参照。
- `apps/desktop/src-tauri/src/main.rs:451-465,719-729` — Desktop が host 起動時に packaged/real-engine flags を設定。
- `apps/host/scripts/preview-ui.mjs:13`, `approval-flow.mjs:31`, `qa2-flows.mjs:20` — 開発用 host 起動スクリプトが子プロセスに `'0'` を設定。
- `apps/host/docs/native-engine-handover.md:46` — native adapter と旧 GGUF/llama adapter の適用範囲の区別（設計説明。挙動の根拠は上記実装）。

`apps/host/audit-fixes/apply-model.py:8` にも同じ比較文字列がありますが、これは `server/catalog.mjs` の生成コードを組み立てるパッチ用スクリプト内の文字列であり、実行中の host が読む箇所ではありません。
