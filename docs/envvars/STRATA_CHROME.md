# `STRATA_CHROME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/qa2-flows.mjs` が Playwright の browser launch に渡す実行ファイルのパスを指定します。このスクリプトは画面のブラウザー QA を行う同梱ツールであり、通常の Strata アプリ起動やサーバー設定を制御する読み取り箇所は見つかりませんでした（`apps/host/scripts/qa2-flows.mjs:1-4,25`）。

## 値と判定

| 状態 | `CHROME` に設定される値 |
|---|---|
| `STRATA_CHROME` が未設定 | OS ごとの既定パス。Windows は `C:/Program Files/Google/Chrome/Application/chrome.exe`、macOS は `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`、それ以外は `/usr/bin/google-chrome` |
| 空文字を設定 | 空文字列。`??` は `null` / `undefined` の場合だけ既定値を選ぶため、空文字は置き換えられません |
| その他の値 | 指定文字列をそのまま使用 |

存在確認、パスの正規化、文字列の parse はこのスクリプトでは行いません。スクリプト引数 `[shots-dir]` はスクリーンショット保存先であり、ブラウザー実行ファイルの指定には使われません（`apps/host/scripts/qa2-flows.mjs:3,13-15`）。

## 有効になる条件

この変数を読むのは、`node scripts/qa2-flows.mjs [shots-dir]` として同スクリプトを実行した場合です。Strata のサーバーや通常の CLI に対する設定ではありません。OS による既定値の切り替え以外に、backend、build macro、モデル状態、別環境変数との条件分岐はありません（`apps/host/scripts/qa2-flows.mjs:2-3,12-15`）。

## 実行時の詳細

値はスクリプトのモジュール初期化時に一度 `process.env.STRATA_CHROME` から取得され、後続の `launch()` 呼び出しで `chromium.launch({ executablePath: CHROME, headless: true })` に渡されます。したがって同一プロセス内で環境を後から変更しても、この `CHROME` 定数は再評価されません。専用スクリプトは一時ホームを使う QA 用ホストも子プロセスとして起動し、子の環境には親の環境を展開して渡しますが、ソース内に `STRATA_CHROME` を読む別のサーバー側箇所は見つかりません（`apps/host/scripts/qa2-flows.mjs:15,20,25`）。

スクリプトは QA チェックの結果を `PASS` / `FAIL` として出力し、全チェックの成否に基づいて `process.exitCode` を設定します（`apps/host/scripts/qa2-flows.mjs:16-17,214-215`）。指定パスが存在しない場合などに Playwright やブラウザーがどう失敗するかは外部依存側の挙動なので、ここでは Strata の動作として記述しません。

## 根拠

- `apps/host/scripts/qa2-flows.mjs:1-4` — このスクリプトが split-qa2 のブラウザー QA であり、Node から直接起動するツールであること。
- `apps/host/scripts/qa2-flows.mjs:13-15` — スクリーンショット引数と環境変数の読み取り、OS ごとの既定値。
- `apps/host/scripts/qa2-flows.mjs:20,25` — 子ホストへの環境引き継ぎと、取得値を `executablePath` として渡す箇所。
- `apps/host/scripts/qa2-flows.mjs:214-215` — QA 結果に応じた終了コード設定。

候補一覧 `docs/envvars/000_envvers.md` にはこの名前があります。完全一致検索で見つかった実参照は上記 QA スクリプトの1箇所のみで、製品実行経路での読み取りは確認できませんでした。
