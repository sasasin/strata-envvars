# `TEST_PIDFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

製品コードに `TEST_PIDFILE` を名前指定で読む処理や、その値で動作を切り替える処理は見つからない。アプリ側の Control 起動処理は環境マップを汎用的に子プロセスへ渡すため、親プロセスの環境にこの名前があれば Control 子プロセスにも渡る。ただし Strata 側では値を解釈せず、PID ファイルの作成もしない（`app/host/server/control-runtime.mjs:89-107,141-146,213-220`）。

名前指定で値を読む箇所は `app/host/tests/fix0217-app-update-check.test.mjs:99` のテストが作る一時的な Node.js CLI スクリプトである。このテストでは PID ファイルの出力先として使う。これはテスト専用コードであり、製品機能の根拠には含めない。

## 値と判定

製品側に値の parse、空文字判定、許容値の判定はない。`controlEnvironment` は渡された環境オブジェクトを複製し、特定のキーを削除・上書きするだけで、`TEST_PIDFILE` はその削除対象に含まれない。したがって Control 子プロセスを起動する経路では、未設定ならキーはなく、設定済みなら空文字・`0`・`1`・`0anything` などの値も加工せず引き継がれる（`app/host/server/control-runtime.mjs:89-107,141-146`）。この転送上、値の大小文字や数値妥当性による違いはない。

## 有効になる条件

- `createControl` の既定経路では `env` の既定値がホストの `process.env` であり、Control 呼び出しが `runCli` を通るとその環境が子プロセスに渡される（`app/host/server/control-runtime.mjs:141-146,213-220`）。
- `controlEnvironment` は `PYTHONHOME`、`PYTHONPATH`、`PYTHONSTARTUP`、`VIRTUAL_ENV`、`STRATA_PYTHON`、`STRATA_NATIVE_PYTHON`、`STRATA_API_KEY` を削除するが、`TEST_PIDFILE` は削除しない（`app/host/server/control-runtime.mjs:89-107`）。
- テスト用スクリプトでは `TEST_PIDFILE` が出力先として使われるが、通常の Strata 実行で同じ用途があるとは確認できない（`app/host/tests/fix0217-app-update-check.test.mjs:94-112`）。

## 実行時の詳細

`runCli` は起動ごとに `controlEnvironment` の戻り値を `spawn` の `env` に渡す。`createControl` で独自の `env` オブジェクトを指定した場合はその内容が基になる。環境値は子プロセス起動時に引き渡されるもので、Strata が `TEST_PIDFILE` を読み取ってキャッシュしたり、実行中の変更を監視したりするコードはない（`app/host/server/control-runtime.mjs:89-107,141-146,213-220`）。

明示的なテスト用スクリプトは `process.env.TEST_PIDFILE` に現在のプロセス ID を書き込む。テストはファイル生成を待って PID を読み、子プロセスを終了する（`app/host/tests/fix0217-app-update-check.test.mjs:94-112`）。この挙動を Strata 本体の環境変数機能として扱うことはできない。

## ログと測定値

`TEST_PIDFILE` の値に応じた Strata のログ、警告、終了・失敗経路はない。Control 起動時の一般的な timeout / 起動失敗処理は `app/host/server/control-runtime.mjs:154-157,171-172` にあるが、この変数を理由に発生するものではない。性能測定値は該当しない。

## 根拠

- `app/host/server/control-runtime.mjs:89-107` — Control 用環境を複製し、指定キーを除いて返す。`TEST_PIDFILE` 固有の処理はない。
- `app/host/server/control-runtime.mjs:141-146,213-220` — Control 子プロセスへ環境を渡す経路。
- `app/host/tests/fix0217-app-update-check.test.mjs:94-112` — テストだけで生成する CLI スクリプトが `process.env.TEST_PIDFILE` を PID の書き込み先として読む。
