# `STRATA_TEST_KEEP_PROFILE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

これは `apps/host/tests/helpers/isolate-profile.mjs` が読む、ホストのテスト用 profile 隔離を止めるフラグです。ホストの設定ファイル・components・ユーザーデータ置き場を一時ディレクトリへ差し替える処理を、値が truthy のときスキップします。テスト helper 内の読み取りであり、アプリ本体・server・native control がこの名前を読む実装は見つかりませんでした。したがって Strata 実行時の製品設定ではなく、テストの起動環境にだけ作用します。helper のコメントは、テストが所有者の実 profile を書き換えた事例を避けるための隔離だと説明しています。`apps/host/tests/helpers/isolate-profile.mjs:1-4,10-18`

## 値と判定

JavaScript の `process.env.STRATA_TEST_KEEP_PROFILE` を truthiness で判定します。文字列の parse、数値変換、値の比較はしません。

| 条件 | 判定と動作 |
|---|---|
| 未設定 | falsy。隔離を行い、一時ディレクトリ配下へ関連環境変数を設定する |
| 空文字 `''` | falsy。隔離を行う |
| 空でない文字列 | truthy。隔離をスキップする。例: `'1'`, `'0'`, `'true'`, `'false'`, `'0anything'`, 空白だけの文字列 |

大文字小文字や数値としての妥当性は検査されません。CLI 引数や別の環境変数との優先順位、無効値時の fallback はありません。`apps/host/tests/helpers/isolate-profile.mjs:10`

## 有効になる条件

- `apps/host/tests` のテストが `helpers/isolate-profile.mjs` を import する場合に限り、この判定が実行されます。該当する import は `no-acquire.test.mjs`、`applin-0214-drafter.test.mjs`、`user-args.test.mjs`、`parallel-default.test.mjs`、`split-app.test.mjs`、`df2ux-0213.test.mjs`、`arcfix-updated-control.test.mjs`、`load-pictures.test.mjs`、`fix0215-drafting-off.test.mjs`、`no-llama-server.test.mjs`、`engine-update-model.test.mjs`、`models-folder.test.mjs`、`draft-layer.test.mjs`、`component-updates.test.mjs`、`packaged-control.test.mjs`、`applin-0214.test.mjs`、`native-checking-0213.test.mjs` (`apps/host/tests/<name>:1`, `native-checking-0213.test.mjs:5`)。
- この helper を import しないテストやアプリケーション/server/native-control の実行だけでは、この変数は読み取られません。C++/CUDA/HIP/SYCL コード、build macro、GPU/backend、モデル状態、サーバー/CLI オプションによる条件はありません。

## 実行時の詳細

ES module の import 時に一度同期評価されます。変数が未設定または空文字なら `mkdtempSync(join(tmpdir(), 'strata-host-test-profile-'))` で一時ディレクトリを作り、現在の Node.js プロセスの `process.env` の以下の値をその下のパスで上書きします: `STRATA_SETTINGS_FILE`、`STRATA_COMPONENTS_DIR`、`LOCALAPPDATA`、`APPDATA`、`XDG_DATA_HOME`、`XDG_STATE_HOME`、`XDG_CONFIG_HOME`。値が truthy なら一時ディレクトリを作らず、これらの値も変更しません。したがって `'0'` や `'false'` でも profile の隔離は無効になります。判定後にプロセス環境を変更しても、この helper の処理は再実行されません。`mkdtempSync` が失敗した場合は import 中に例外となり、後続のテストコードへ進みません。子プロセスの生成や変数の転送はこの helper 自身では行いません。`apps/host/tests/helpers/isolate-profile.mjs:6-18`

## ログと測定値

この helper はログを出力せず、測定値もありません。隔離が有効な場合は Node.js プロセスの環境値が変更され、隔離をスキップした場合は変更されません。テスト実行の起動方法や終了コードをここで変更する処理はありません。`apps/host/tests/helpers/isolate-profile.mjs:10-18`

## 根拠

- `apps/host/tests/helpers/isolate-profile.mjs:1-4,6-18` — helper の目的、設定有無判定、一時ディレクトリ作成、上書きする環境変数。
- `apps/host/tests/no-acquire.test.mjs:1` ほか 16 件 — テストからの import。
- `docs/envvars/000_envvers.md:2130` — 候補一覧への掲載。候補一覧自体は実装の根拠ではありません。
