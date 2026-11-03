# `E2E_LINES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`apps/host/scripts/agent-lost-e2e.mjs` の agent lost end-to-end シナリオで、長文のファイル書き込み要求に含める行数を指定します。Strata engine 本体の環境設定ではなく、この E2E スクリプトが Node.js の `process.env` から読む値です。スクリプトの先頭コメントは long シナリオの既定値を 1800 と記していますが、実際のコードの既定値は 1100 です（`apps/host/scripts/agent-lost-e2e.mjs:7-13,37`）。

## 値と判定

共通 helper は環境変数が `null` または `undefined` のときだけ fallback を使います。その後 `Number(...)` で JavaScript の数値へ変換し、値の範囲や整数性を検証しません（`apps/host/scripts/agent-lost-e2e.mjs:30,37`）。

| 入力 | `LINES` の結果 | 動作 |
|---|---:|---|
| 未設定 | `1100` | 既定の行数をプロンプトに指定 |
| 空文字 | `0` | 数値 0 としてプロンプトに指定 |
| 数値文字列 | `Number` の変換結果 | 正数・負数・小数などをそのままプロンプトに指定 |
| 数値に変換できない文字列 | `NaN` | `NaN` をプロンプトに埋め込む。入力エラーや fallback はない |

変換後の値は `longPrompt` に文字列として埋め込まれます。`long` シナリオの完了判定にも使用されますが、ここではファイル行数を `LINES * 0.95` と比較するため、`LINES` が `NaN` の場合この比較は成立しません（`apps/host/scripts/agent-lost-e2e.mjs:139,185-191`）。

## 有効になる条件

`raw`、`long`、`cut` の各シナリオが共通の `longPrompt` を使うため、これらを実行するときに要求内容へ反映されます。コマンドライン引数なしの場合 `want()` はすべてのシナリオを有効にするので、その場合も使用されます。`pagoda` と `mcp` の要求文は `longPrompt` を使わず、`E2E_LINES` はそのシナリオの要求内容に影響しません（`apps/host/scripts/agent-lost-e2e.mjs:40-41,139-146,161-176,179-186,194-200`）。

サーバーがすでに動作していて `E2E_BASE_URL` が設定されている場合も、スクリプト側の `longPrompt` には同じ値が使われます。これはスクリプトがサーバーを起動するかを切り替える条件で、`E2E_LINES` の値を上書きしません（`apps/host/scripts/agent-lost-e2e.mjs:34,58-86,139`）。

## 実行時の詳細

値はスクリプト評価時に一度読み取られ、`LINES` 定数に保持されます。起動後に環境変数を変更しても再読込されません。値は行数を指定するプロンプトと long シナリオの表示・判定に使われ、`E2E_LINES` 自体についての警告や終了処理はありません。スクリプトの結果は各シナリオの `PASS` / `FAIL` 表示、`result.json`、および最終終了コードで観測できます（`apps/host/scripts/agent-lost-e2e.mjs:37,139,185-191,207-210`）。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:30,37` — `process.env` の nullish fallback helper と、既定値 `1100` を使う `Number` 変換。
- `apps/host/scripts/agent-lost-e2e.mjs:139` — `LINES` を要求プロンプトに埋め込む。
- `apps/host/scripts/agent-lost-e2e.mjs:40-41,141-146,185-191,194-204` — シナリオ選択、値を使う経路、long シナリオの出力と判定。
- `apps/host/scripts/agent-lost-e2e.mjs:207-210` — 結果一覧と成功・失敗に応じた終了コード。
