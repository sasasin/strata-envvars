# `STRATA_FORCE_DEMO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata desktop/host の推論 backend 判定で、engine が見つからないときの demo 推論を許可します。推論 worker や C++ engine が読む変数ではなく、Node.js の host が `process.env` から読みます。変数を設定しても実在する Strata worker、supervisor engine、または検出された OpenAI-compatible endpoint より demo が優先されるわけではありません。

## 値と判定

| `STRATA_FORCE_DEMO` | `STRATA_PACKAGED` | `requiresRealEngine()` の判定 |
|---|---|---|
| 文字列が厳密に `1` | 厳密に `1` ではない | `false`（demo を許可） |
| 文字列が厳密に `1` | 厳密に `1` | force-demo 条件は不成立。次に `STRATA_REAL_ENGINE`、続いて packaged 判定を評価 |
| 未設定、空文字、その他の文字列（`true`、`01` 等を含む） | 任意 | force-demo 条件は不成立。次に `STRATA_REAL_ENGINE`、続いて packaged 判定を評価 |

空文字を含め、`'1'` 以外は有効になりません。数値変換、trim、大文字小文字変換はありません。未設定または force-demo 条件不成立時は、`STRATA_REAL_ENGINE === '1'` なら実 engine 必須、そうでなければ `STRATA_PACKAGED === '1'` のときだけ実 engine 必須です。したがって unpackaged 環境では `STRATA_FORCE_DEMO=1` が `STRATA_REAL_ENGINE=1` より先に評価され、demo を許可します。一方 packaged 環境では `STRATA_FORCE_DEMO=1` でも demo を有効にできません。

根拠: `apps/host/server/inference.mjs:31-42`。

## 有効になる条件

`STRATA_FORCE_DEMO=1` が demo を許可するのは、推論 backend の探索が demo fallback まで到達した場合です。`detectBackend()` は最初に Strata worker を probe し、次に起動中の supervisor engine を採用し、さらに llama.cpp / Ollama / LM Studio の endpoint を調べます。いずれも使えず、かつ `requiresRealEngine()` が `false` の場合に `kind: 'demo'`、`simulated: true` の backend を返します。`streamChat()` はこの backend に対して `demoCompletion()` を実行します。

`STRATA_PACKAGED=1` では force-demo の例外が成立せず、実 engine が見つからない場合は `kind: 'unavailable'` を返します。`streamChat()` はこの状態でエラーを throw し、demo completion へ進みません。desktop の Tauri shell は host 起動時に `STRATA_PACKAGED=1` と `STRATA_REAL_ENGINE=1` を設定しています。

根拠: `apps/host/server/inference.mjs:38-41,84-156,199-235`; `apps/desktop/src-tauri/src/main.rs:463-478`。

## 実行時の詳細

環境変数は `requiresRealEngine()` の呼び出しごとに `process.env` から直接評価され、関数内に値の static cache はありません。host 起動時には `detectBackend({ force: true })` が初回判定を行います。通常の chat 時は `detectBackend()` が使われ、backend 判定結果を20秒間再利用する経路があります（`force` が false で、既存 backend が engine 以外の場合）。その cache が返される間は新しい探索と fallback 判定を通らないため、実行中に環境変数を書き換えた場合、値自体は再読込可能でも既存 backend の反映は即時とは限りません。これは環境変数値の cache ではなく backend オブジェクトの cache です。

demo backend が選ばれると、起動ログの inference 行は設定に応じて `simulated (design iteration) — set STRATA_REAL_ENGINE=1 for a real engine` と表示されます。demo 応答は `demoCompletion()` が生成し、コード内では demo 用の文面や simulated metrics を扱います。実 engine 必須で endpoint が見つからない場合の backend error は `No Strata engine answered at ... and no supervised engine is running. Start Strata (or load a model) and retry. Simulated output is disabled in this build.` です。

根拠: `apps/host/server/inference.mjs:28-29,84-156,199-235,365-418`; `apps/host/server/index.mjs:278-284`。

## 根拠

- 候補名の全参照検索では、実行時の読み取りは `apps/host/server/inference.mjs:39` のみでした。`docs/work/IMPLEMENTATION_STATUS.md:251-255` にも force-demo の unpackaged 限定という記述がありますが、動作根拠は上記の実装です。
- backend 探索順、demo fallback、実 engine 必須時の unavailable backend: `apps/host/server/inference.mjs:84-156`。
- chat が demo を呼ぶ条件と unavailable 時の失敗: `apps/host/server/inference.mjs:199-235`。
- 起動時の backend 判定と inference ログ: `apps/host/server/index.mjs:278-284`。
- desktop shell が packaged / real-engine の値を host に設定: `apps/desktop/src-tauri/src/main.rs:463-478`。
