# `THINK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`THINK` は Strata host の HTTP 対話用スクリプト `apps/host/scripts/agent-http.mjs` と `apps/host/scripts/agent3-http.mjs` が、`stream` コマンドのリクエストに reasoning level を付けるための環境変数です。Strata サーバー自身が `process.env.THINK` を読む箇所はありません。両スクリプトは環境変数を JSON の `thinking` プロパティに載せ、サーバーへ転送します（`apps/host/scripts/agent-http.mjs:83-86`, `apps/host/scripts/agent3-http.mjs:72-75`）。

## 値と判定

| `THINK` の状態 | スクリプトの処理 |
|---|---|
| 未設定 | `thinking` プロパティを送らない |
| 空文字 | JavaScript の falsy 判定により、未設定と同じくプロパティを送らない |
| 非空文字列 | 文字列を加工せず `thinking` に設定して送る |

スクリプトでは文字列の検証、trim、大小文字変換をしません。数値としての解釈もありません。サーバーでの扱いは実行経路によって異なります。

- agent 経由では `effortOf()` が値を小文字化して `off`, `low`, `medium`, `high`, `max` のいずれかと照合します。大文字小文字は無視しますが、前後の空白は除去しません。それ以外の値は `null` になり、選択要求に `reasoningEffort` を付けません（`apps/host/server/agent/profile.mjs:160-170`, `apps/host/server/agent/agent-bridge.mjs:388-405`）。
- plain 経由では `model-providers.mjs` が同じ5語を小文字化して照合します。OpenAI Chat 形式かつモデルの reasoning 対応が確認できる場合だけ、認識した値を provider 向けリクエストに設定します。OpenRouter には `reasoning.effort`、それ以外には `reasoning_effort` を設定し、`off` は `none`、`max` は OpenRouter で `xhigh`、それ以外で `high` に写します。無効値、未対応モデル、他 protocol ではこの分岐を通りません（`apps/host/server/model-providers.mjs:146-166`, `apps/host/server/agent/profile.mjs:164-167`）。provider やモデルがその指定をどう実行するかは Strata の処理範囲外です。

## 有効になる条件

環境変数が有効なのは、上記どちらかのスクリプトを起動し、`stream` コマンドを実行した場合だけです。他のコマンドでは該当プロパティを組み立てません。両スクリプトとも送信先モデルは保存済み API 接続から選びます（`agent-http.mjs:27-32,83-86`; `agent3-http.mjs:27-32,72-75`）。

既定の agent 経由かどうかはサーバー側の状態にもよります。`PLAIN` が truthy ならスクリプトは `agent: false` を付けます。サーバーも `STRATA_AGENT=off`、`agent: false`、chat ID の欠落、またはモデル未選択で agent を使わず plain 経路にします。また agent が利用不可の場合も plain 経路へ進みます（`apps/host/scripts/agent-http.mjs:83-86`; `apps/host/scripts/agent3-http.mjs:72-75`; `apps/host/server/index.mjs:2001-2026`）。

## 実行時の詳細

値は host スクリプトが `stream` 用リクエスト本文を作る時点で読み、リクエストごとに使います。環境値を保存する static cache はありません。非空の値は `/api/chat/stream` の JSON 本文に入り、Strata サーバーは本文の `thinking` を agent または plain の処理へ渡します（`agent-http.mjs:35-37,83-86`; `agent3-http.mjs:35-37,72-75`; `apps/host/server/index.mjs:1980-2007,2026-2038`）。

値を省略したときの既定値は経路で異なります。agent 経由は `null` を `effortOf(thinking ?? 'Medium')` に渡すため `medium` を選びます。plain 経由は `/api/chat/stream` handler の `body.thinking ?? 'high'` により `high` を渡します。明示した非空値はこの既定値を置き換えます（`apps/host/server/index.mjs:633-639,2034-2038`; `apps/host/server/agent/agent-bridge.mjs:388-405`）。agent 経由では、値に応じた `session/selectModel` 呼び出しが失敗し、有効 level がある場合は level なしで再試行します。再試行も失敗した場合、agent は `The coding assistant could not use ...` を含む error frame を返します（`agent-bridge.mjs:397-405`; `apps/host/server/index.mjs:642-645`）。

plain 経由で remote model に送るときは Strata がモデル対応を確認した上で provider リクエストを組み立てます。`THINK` 固有の警告やログ出力は見つかりません。HTTP 応答が成功でない場合、スクリプトの `stream()` は `stream -> <status> <response text>` の例外を投げます。ストリーム中のサーバー側エラーは `error` frame としてスクリプトに表示されます（`agent-http.mjs:35-38,53-68`; `agent3-http.mjs:35-38,52-58`; `apps/host/server/index.mjs:595-600`）。

## 根拠

`THINK` の環境読み取りは `apps/host/scripts/agent-http.mjs:86` と `apps/host/scripts/agent3-http.mjs:75` の2箇所です。リポジトリ全体の大文字 `THINK` 検索には reasoning タグ定数、UI 名、テスト・fixture などの参照もありますが、これらは環境変数の読み取りではありません。サーバーへの受け渡しと値の解釈は本文の各経路の根拠に記載しました。
