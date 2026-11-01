# `DSH_TELEMETRY_DISABLED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の host は、別コンポーネントである DeepSeek Harness を子プロセスとして起動するとき、この環境変数を子プロセス環境へ設定します。Strata のソースがこの変数を自分の環境から読み取ったり、その値に応じて Strata の telemetry を切り替えたりする箇所は見つかりませんでした。Harness 内での意味や効果は、この調査の対象ソースからは確認できません。

## 値と判定

Strata は `agentEnvironment()` の戻り値に `DSH_TELEMETRY_DISABLED: '1'` を加えます。現在の親プロセス環境にこの名前が未設定、空文字、または別の値で設定されているかは参照されず、通常は子へ渡す値が文字列 `'1'` になります。

ただし、`agentEnvironment(base, extra)` は `...extra` をこの固定値より後に展開します。同じキーが `extra` に含まれていれば、その値が優先されます。Harness 起動経路では `extra` は `this.extraEnv`（`HarnessProcess` の `env` 引数）と `DSH_HOME` をまとめたオブジェクトで、呼び出し元は `profile.env` を `env` として渡します。従って、この経路で `profile.env` に同名キーがあれば `'1'` を上書きします。Strata はこの上書き値を parse・検証しません。

## 有効になる条件

設定は `HarnessProcess.start()` が Harness 子プロセスを起動するときに適用されます。host 自身の通常実行や別の子プロセスに対する適用は、この参照からは確認できません。起動時に環境オブジェクトを組み立てて `spawn()` に渡すため、Strata 側では起動ごとに値が決まります。

## 実行時の詳細

`agentEnvironment()` は親環境から `externalEnvironment(base)` を通して引き継ぐ値を選別しますが、`DSH_TELEMETRY_DISABLED` は `KEEP` の許可名に含まれません。そのため親環境の同名値をそのまま引き継ぐ経路はありません。続いて固定値 `'1'` を追加し、最後に `extra` を適用します。戻り値は Harness の Node.js プロセスを起動する `spawn()` の `env` に渡されます。

この環境変数に関する Strata 独自のログ、警告、終了・失敗分岐は見つかりませんでした。テストでは `agentEnvironment()` の結果にこのキーが含まれることを確認していますが、Harness がその値をどう処理するかの根拠にはしていません。

## 根拠

- `apps/host/server/agent/harness-runtime.mjs:23-36` — 親環境の許可リスト、固定値 `'1'` の追加、`extra` による後勝ち上書き。
- `apps/host/server/agent/harness-runtime.mjs:67-69,79-83` — `env` 引数を `extraEnv` として保持し、`agentEnvironment()` の結果を Harness 子プロセスの `spawn()` に渡す。
- `apps/host/server/agent/agent-bridge.mjs:214-215` — `profile.env` を `HarnessProcess` の `env` 引数に渡す。
- `apps/host/tests/agent-events.test.mjs:61-64` — `agentEnvironment()` の結果にキーが含まれることを確認するテスト。
