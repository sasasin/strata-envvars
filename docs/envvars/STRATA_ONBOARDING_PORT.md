# `STRATA_ONBOARDING_PORT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

オンボーディング画面用の使い捨て UI fixture が、HTTP サーバーを listen するポートを指定します。読み取りは `apps/host/tests/fixtures/onboarding-ui-host.mjs` にだけあり、Strata の通常サーバーや推論エンジンが読む設定ではありません。同梱スクリプト `preview-ui.mjs` と `language-shots.mjs` から fixture を起動するときは、各スクリプトが `STRATA_ONBOARDING_PORT` を明示的に上書きして渡します。

## 値と判定

fixture のモジュール初期化時に `Number(process.env.STRATA_ONBOARDING_PORT ?? 5271)` を評価します。環境変数は文字列として扱われ、`??` による既定値選択の後、JavaScript の `Number` で数値へ変換されます。

| 環境変数の状態・値 | fixture が `listen` に渡す値 |
|---|---|
| 未設定 | `5271` |
| 空文字 | `0`（空文字を既定値とは扱わない） |
| 数値として変換できる文字列 | 変換された数値。整数に限る検査や文字列全体の独自 parse はない |
| 数値に変換できない文字列 | `NaN` |

負値、小数、範囲外の数値も Strata 側では clamp・範囲検査されず、変換結果のまま `server.listen` に渡されます。ポートとして受理される範囲や `NaN` などを渡した場合の例外は Node.js の `server.listen` 側に委ねられており、この fixture にはそのエラーを捕捉する listener や独自の fallback がありません。

## 有効になる条件

この変数を読むのは UI fixture を直接起動したときです。環境変数による OS / backend / build macro / モデル状態の条件はありません。fixture は `127.0.0.1` に bind します。

`apps/host/scripts/preview-ui.mjs` は `STRATA_PREVIEW_PORT`（既定 `5272`）から `webPort` を決め、子プロセス環境の `STRATA_ONBOARDING_PORT` にその値を文字列化して設定します。`apps/host/scripts/language-shots.mjs` はランダムに決めた `hostPort + 100` を同変数として渡します。両方とも子プロセス環境を `{ ...process.env, ..., extra }` の順で構成するため、親プロセスに同名変数があっても `extra` の値で上書きされます。したがって、この2スクリプト経由では親から指定した `STRATA_ONBOARDING_PORT` は使われません。

## 実行時の詳細

fixture 起動時に一度値を読み、変換結果を `port` 定数に保持して `server.listen(port, '127.0.0.1', callback)` を呼びます。起動後の環境変更を再読込する処理や cache 更新処理はありません。listen 完了時には stdout に `Disposable onboarding screenshots: http://127.0.0.1:<port>` を出力します。SIGTERM / SIGINT では heartbeat を止め、接続を閉じて終了する処理があります。

プレビュー起動スクリプトは fixture の URL に対して HTTP リクエストが成功するまで待ちます。`preview-ui.mjs` は100回の確認後に `The isolated preview host did not start. Check the port and console output.` を stderr に出して終了処理へ進みます。`language-shots.mjs` は201回目の確認後に `The preview page did not start.` を stderr に出して `process.exit(1)` します。これらは起動スクリプトの待機経路であり、fixture 自身の無効ポート値に対する検証やメッセージではありません。

## 根拠

- 変数の唯一の読み取り、nullish fallback、`Number` 変換、loopback bind、起動ログ、終了 handler: `apps/host/tests/fixtures/onboarding-ui-host.mjs:124-127`。
- ファイル冒頭の fixture 用途の説明: `apps/host/tests/fixtures/onboarding-ui-host.mjs:1`。
- プレビューで `STRATA_PREVIEW_PORT` から値を決め、子環境で同変数を上書きする処理と起動失敗ログ: `apps/host/scripts/preview-ui.mjs:9-10,13,23-25`。
- スクリーンショット生成でポートを決め、子環境で同変数を上書きする処理と起動待ち失敗経路: `apps/host/scripts/language-shots.mjs:24-30,40-44`。
