# `E2E_TURN_S`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata 同梱の `apps/host/scripts/agent-lost-e2e.mjs` が `turn()` で実行する個々の agent turn に、停止を要求するまでの時間を秒単位で指定します。Strata の通常の CLI、engine、server の設定値ではなく、この end-to-end 検証スクリプト専用です。スクリプト内で `E2E_TURN_S` を読むのは1箇所です（`apps/host/scripts/agent-lost-e2e.mjs:39`）。

## 値と判定

値は共通 helper `env(name, fallback)` で取得され、`Number(...)` で数値化されます。helper は値が `undefined` のときだけ既定値を使うため、空文字列は未設定と同じ扱いになりません（`apps/host/scripts/agent-lost-e2e.mjs:29-30,39`）。

| 入力 | `TURN_S` の値 | スクリプト側の扱い |
|---|---:|---|
| 未設定 | `900` | 900秒をタイマーに渡す |
| 空文字列または空白だけ | `0` | 0秒相当をタイマーに渡す |
| 数値として変換できる文字列 | 変換後の数値 | 秒からミリ秒へ換算してタイマーに渡す |
| 数値として変換できない文字列 | `NaN` | 明示的な検査・警告・fallback はなく、`NaN * 1000` をタイマーに渡す |

整数であること、正であること、上限・下限は検査されず、値の clamp もありません。したがって負数、小数、`Infinity` などもスクリプト内では拒否されず、そのまま秒数としてミリ秒換算に進みます。`Number` による変換なので、数値接頭辞だけを読む処理ではなく、`12x` のような文字列は `NaN` になります（同ファイル `:39,117`）。

## 有効になる条件

- コマンドライン引数で `pagoda`、`long`、`cut` のいずれかを選んだ場合、そのシナリオが呼び出す `turn()` の各ターンに適用されます。引数を省略して全シナリオを実行する場合も同様です（`apps/host/scripts/agent-lost-e2e.mjs:40-41,179-200`）。`long` は `E2E_REPEAT` により複数回実行されることがあります。
- `mcp` と `raw` は `turn()` を通らないため、この変数では制限されません（同ファイル `:141-177`）。シナリオ引数は実行対象を選びますが、時間を指定する CLI 引数はありません。
- `E2E_BASE_URL` の設定は既存 server を使うかスクリプト自身が server を起動するかを変えますが、`E2E_TURN_S` の値や `turn()` のタイマー設定は変えません（同ファイル `:34,58-84,111-118`）。OS/backend による分岐はありません。

## 実行時の詳細

スクリプトのモジュール初期化時に環境変数を一度読み、`const TURN_S` に保存します。実行中に環境を書き換えても再読込しません（`apps/host/scripts/agent-lost-e2e.mjs:29-40`）。各 `turn()` は開始時に `setTimeout` を作り、指定時間が経つと `timedOut` を `true` にして `bridge.stop(chatId)` を呼びます。`bridge.stop` は active turn に対して停止処理を行い、Harness session に `session/cancel` を送ります。`runTurn()` が解決するとタイマーは解除され、`timedOut` を含む turn summary が `turn-<name>.json` に保存されます（同ファイル `:111-136,117-119`; `apps/host/server/agent/agent-bridge.mjs:1380-1402`）。

このスクリプトはタイムアウト専用のログやエラー文を出しません。`timedOut` は summary に記録されますが、シナリオの PASS/FAIL 判定や最終終了コードでは直接参照されず、最終コードは `rows` に記録されたシナリオ検査の成否で決まります（`apps/host/scripts/agent-lost-e2e.mjs:134-136,179-209`）。timeout 後の turn がどの frame やファイルを残すかは実行状況に依存し、この変数の実装だけでは断定できません。

スクリプト自身が server 子プロセスを起動する経路では `...process.env` を子の環境に含めるため、設定値は子にも継承されます。ただしこの候補名を読む箇所は親の E2E スクリプトの1箇所だけで、Strata server / engine 側でタイムアウト値として再利用する読み取りは見つかりません（同ファイル `:39,77-79`）。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:29-30,39` — helper の nullish fallback、既定値900秒、`Number` 変換。
- `apps/host/scripts/agent-lost-e2e.mjs:40-41,111-119` — シナリオ選択、turn ごとのタイマー、停止要求、タイマー解除。
- `apps/host/server/agent/agent-bridge.mjs:1380-1402` — bridge の stop 要求と session cancel。
- `apps/host/scripts/agent-lost-e2e.mjs:134-136,179-209` — `timedOut` summary、シナリオ判定、最終終了コード。
- `apps/host/scripts/agent-lost-e2e.mjs:77-79` — server 子プロセスへの環境継承。
