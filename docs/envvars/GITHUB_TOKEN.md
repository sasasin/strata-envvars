# `GITHUB_TOKEN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `GITHUB_TOKEN` を機能設定として使わない。agent の Harness 子プロセスを起動するとき、ホスト環境を `agentEnvironment` で絞り込み、許可名にない変数を渡さない。`GITHUB_TOKEN` は許可名 `KEEP` に一致せず、除外される（`app/host/server/agent/harness-runtime.mjs:20-23,26-36,80-83`）。

この除外は agent の子プロセス環境に対するもの。Strata ホスト自身が起動時に受け取る環境や、GitHub Actions の workflow が使うトークンの動作を変更するものではない。

## 値と判定

`GITHUB_TOKEN` の値は比較・変換されない。環境変数名に対する `SECRET_NAME = /(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)/i` と、許可名の `KEEP` を使って各項目を判定し、どちらかの条件に合わなければ除外する。したがって、設定値が空文字でも非空でも、`GITHUB_TOKEN` は Harness に渡らない。未設定なら除外対象の項目自体がない。`0`、`1`、`true` などの値による境界や無効値の区別はない（`app/host/server/agent/harness-runtime.mjs:20-23,26-33`）。

## 有効になる条件

- agent の Harness 子プロセスを起動する経路で適用される。`HarnessProcess.start()` が `spawn` の `env` に `agentEnvironment(process.env, ...)` の結果を渡す（`app/host/server/agent/harness-runtime.mjs:75-83`）。
- `agentEnvironment` は環境名を大文字小文字を区別せず判定する。`GITHUB_TOKEN` は許可名 `KEEP` に一致せず、かつ `SECRET_NAME` に一致するため除外される（`app/host/server/agent/harness-runtime.mjs:20-23,30-33`）。
- 起動元は追加環境として `profile.env` と `STRATA_UPDATE_PAUSE_FILE` を渡す。プロフィール側の MCP secret は `STRATA_MCP_<番号>_<種別>_<名前>` という別名に格納され、ホストの `GITHUB_TOKEN` を同名で追加する処理はない（`app/host/server/agent/agent-bridge.mjs:303-305`; `app/host/server/agent/profile.mjs:93-97,105-111`）。`agentEnvironment` は `extra` を最後に展開するため、明示的に同名を `extra` に渡せばフィルタ後に追加できるが、この起動元ではそうしていない（`app/host/server/agent/harness-runtime.mjs:34-36`）。

## 実行時の詳細

フィルタは Harness の起動ごとに実行され、起動時点の `process.env` を列挙して子プロセス用の新しい環境オブジェクトを作る。`GITHUB_TOKEN` を読み取ってキャッシュする処理や、実行中に値を再評価する処理はない。子プロセスを起動した後の親環境の変更は、その起動済み Harness の環境には反映されない（`app/host/server/agent/harness-runtime.mjs:26-36,75-83`）。

## 根拠

- `app/host/server/agent/harness-runtime.mjs:20-36` — 機密名と許可名の判定、環境のフィルタ、追加環境の展開。
- `app/host/server/agent/harness-runtime.mjs:75-83` — Harness 起動時にフィルタ結果を子プロセスへ渡す。
- `app/host/server/agent/agent-bridge.mjs:303-305` — 起動元が追加環境としてプロフィールと pause marker を渡す。
- `app/host/server/agent/profile.mjs:93-97,105-111` — MCP の環境値・header 値を生成名でプロフィール環境へ渡す。
- `app/host/tests/agent-events.test.mjs:63-66` — `GITHUB_TOKEN` を含む ambient credential が agent 環境から除外されることを確認する fixture と期待値。
