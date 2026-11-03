# `E2E_REPEAT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`apps/host/scripts/agent-lost-e2e.mjs` の `long` シナリオを何回実行するか指定します。これは Strata engine の実行時設定ではなく、agent-lost E2E 検証スクリプト専用の制御です。スクリプトの説明では、実 Harness と実 engine を使う end-to-end 検証として案内されています（`apps/host/scripts/agent-lost-e2e.mjs:3-5`）。

## 値と判定

スクリプトは共通 helper `env(name, fallback) => process.env[name] ?? fallback` で値を取り、`Number(...)` に渡します。helper は未設定 (`undefined`) の場合だけ fallback を使うため、空文字列は既定値扱いになりません（`apps/host/scripts/agent-lost-e2e.mjs:29-30,38`）。

| 環境変数の値 | `REPEAT` の結果 | `long` シナリオの反復 |
|---|---:|---|
| 未設定 | `1`（既定値） | 1回 |
| 空文字、空白だけ | `0` | 0回 |
| 数値文字列 | JavaScript の `Number` による数値変換 | `rep` が1から始まり `rep <= REPEAT` の間だけ実行 |
| 数値に変換できない文字列 | `NaN` | 0回（比較が成立しない） |
| 負数または0 | その数値 | 0回 |
| 正の小数 | その数値 | 1から整数を増やすため、結果として `ceil(REPEAT)` 回 |
| `Infinity`（例: `1e309`） | 正の無限大 | ループを止める上限がなく、通常の完了条件では終了しない |

文字列全体を `Number` で変換し、`parseInt` のように数値接頭辞だけを読む処理や、整数化・clamp・明示的な無効値エラーはありません。たとえば `2x` は `NaN` になり、`2.5` は2回ではなく3回実行されます（`apps/host/scripts/agent-lost-e2e.mjs:38,185-186`）。

## 有効になる条件

反復回数が参照されるのは、コマンドライン引数に `long` が含まれる場合、またはシナリオ引数がなく全シナリオを選ぶ場合だけです。`pagoda`、`mcp`、`raw`、`cut` の実行回数はこの変数では変わりません（`apps/host/scripts/agent-lost-e2e.mjs:40-41,141,161,179,185,194`）。

数値用の CLI 引数による上書きはありません。CLI 引数はシナリオ選択に使われます。`E2E_BASE_URL` は既存 server を利用するかどうかを切り替えますが、`E2E_REPEAT` の loop 条件は変えません（`apps/host/scripts/agent-lost-e2e.mjs:34,40-41,58,185`）。

## 実行時の詳細

値はスクリプトのモジュール初期化時に一度読み、`const REPEAT` に保存します。スクリプト実行中に環境変数を変更しても、この定数は再評価されません（`apps/host/scripts/agent-lost-e2e.mjs:38`）。

`long` の各反復は `long1`、`long2` のような名前で `turn()` を呼び、結果をコンソールに出力して `rows` に記録します（`apps/host/scripts/agent-lost-e2e.mjs:185-191`）。完了時は `rows` を `result.json` に書き、いずれかの記録が失敗なら終了コード1、そうでなければ0で終了します。したがって、`REPEAT` が0または `NaN` で `long` 以外のシナリオも選ばれていない場合、`rows` が空のままでも、スクリプトのこの集計条件では終了コード0になります（`apps/host/scripts/agent-lost-e2e.mjs:207-209`）。

スクリプトが自前で server を起動するとき、子 server の環境は `...process.env` を含むオブジェクトで作られるため、設定されていれば `E2E_REPEAT` も子へ継承されます。ただし、このスクリプト内で反復数として読むのは親プロセス側の `REPEAT` であり、子の起動後に回数を再読する処理はありません（`apps/host/scripts/agent-lost-e2e.mjs:58,77-79,185`）。

この変数専用のログや警告、範囲エラー処理はありません。反復した場合は各回の `longN: ...` と PASS/FAIL が出力され、結果は `result.json` に記録されます（`apps/host/scripts/agent-lost-e2e.mjs:189-191,207-209`）。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:29-30,38` — 環境変数 helper、未設定時の `'1'`、`Number` 変換。
- `apps/host/scripts/agent-lost-e2e.mjs:40-41,185-186` — CLI によるシナリオ選択と、`long` シナリオだけを反復する loop。
- `apps/host/scripts/agent-lost-e2e.mjs:189-191,207-209` — 各反復の出力・結果集計・終了コード。
- `apps/host/scripts/agent-lost-e2e.mjs:58,77-79` — server 子プロセスを起動する条件と環境の継承。
