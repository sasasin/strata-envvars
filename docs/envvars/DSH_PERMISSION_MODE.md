# `DSH_PERMISSION_MODE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のホストは、DeepSeek Harness の子プロセスを起動するとき、子プロセスの環境に `DSH_PERMISSION_MODE=read-only` を設定します。Strata ソース内にこの環境変数を読み取る処理はなく、Strata がこの値で自身の権限処理を分岐するものではありません。

値の設定箇所のコメントは、チャットのモードがまだ適用されていない session（child agent や seeded session）の合成時に使う既定値として説明しています。各チャットのモードは別途、turn ごとに Harness の session API を通じて適用されます。この文書では Harness が環境変数をどう解釈するかは扱いません。

## 値と判定

Strata は親プロセスにある `DSH_PERMISSION_MODE` の値を parse しません。`agentEnvironment()` は、親環境のうち許可リストにある名前だけをコピーし、その後 `DSH_PERMISSION_MODE` に文字列 `read-only` を設定します。したがって、親環境でこの変数が未設定、空、または別の文字列でも、それ自体は Strata 側の入力値として判定されません。

環境生成関数の `extra` 引数は既定値より後に展開されるため、同名キーがあれば上書きできます。現行の Harness 起動元は `profile.env` を `extra` に渡します。`buildProfile()` が返すこの環境には接続/API キーや MCP 用の `STRATA_*` 名が追加されますが、`DSH_PERMISSION_MODE` を追加する処理はありません。

## 有効になる条件

この設定は `HarnessProcess.start()` が Harness 子プロセスを起動するときに、その子プロセスの環境として渡されます。Harness が見つからず起動しない場合は渡されません。Strata ホストの各チャットに選ばれた permission mode は、この環境値の読み取りではなく、`applyMode()` による `session/projections` の確認と `/permission ...` コマンドで適用されます。

## 実行時の詳細

`agentEnvironment(base, extra)` は呼び出しごとに環境オブジェクトを組み立てます。`HarnessProcess.start()` は `spawn()` の `env` にその結果を渡すので、値の設定・引き渡し時点は Harness 子プロセスの起動時です。Strata によるこの変数の static cache、リクエストごとの読み取り、変数値に起因するログ・警告・終了経路は確認できませんでした。

## 根拠

- `apps/host/server/agent/harness-runtime.mjs:20-36` — 親環境のフィルタ、固定値 `read-only` の設定、`extra` による上書き順。
- `apps/host/server/agent/harness-runtime.mjs:75-83` — 起動時に生成した環境を子プロセスの `spawn()` へ渡す箇所。
- `apps/host/server/agent/agent-bridge.mjs:205-215` — `profile.env` を `HarnessProcess` の追加環境として渡す箇所。
- `apps/host/server/agent/profile.mjs:77-100,196-200,290-298,348` — profile 環境に入れる MCP 変数と、返却する `env`。
- `apps/host/server/agent/agent-bridge.mjs:299-315,408-411` — チャットの permission mode を環境変数ではなく session API 経由で適用する箇所。
- `apps/host/tests/agent-events.test.mjs:61-64` — 環境フィルタのテストで `DSH_PERMISSION_MODE` が設定されることを確認する箇所。
