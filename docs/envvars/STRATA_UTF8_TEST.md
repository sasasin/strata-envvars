# `STRATA_UTF8_TEST`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

この名前は `apps/host/tests/powershell-utf8.test.mjs` の Windows 専用テストで、PowerShell 子プロセスに一時ディレクトリのパスを渡すために使われています。Strata のホストやエンジンが読む利用者向け設定ではありません。通常実行時に何かを切り替える環境変数としての実装は確認できません。

## 値と判定

製品コードに読み取り箇所がないため、製品動作について値の parse、既定値、空文字・無効値の扱いはありません。

テストコードでは、Windows で動くテストが `STRATA_UTF8_TEST` に作成した一時ディレクトリのパスを設定し、PowerShell 側で `$env:STRATA_UTF8_TEST` として参照します。テストは変数の値を検証・変換せず、そのパスを `Get-Item -LiteralPath` に渡します。これはテストプロセスが明示的に子プロセス環境へ設定する値であり、製品の既定値を示すものではありません。

## 有効になる条件

この変数を使う箇所はテスト専用です。対象テストは `process.platform !== 'win32'` の場合に skip されるため、PowerShell が利用できる Windows でのみテストの処理が実行されます。製品の実行経路、ビルド設定、CLI オプションとの相互作用はありません。

## 実行時の詳細

テストはキリル文字を含む一時ディレクトリを作り、`execFileSync` で `powershell.exe` を起動するときに `STRATA_UTF8_TEST` を設定します。環境変数を参照する PowerShell コマンドは `utf8Script()` で UTF-8 出力設定を先頭に付けた状態で実行され、Node.js 側は返されたパスの末尾が元のディレクトリ名と一致することを確認します。テスト終了後、一時ディレクトリを削除します。

ホスト製品コードの PowerShell UTF-8 対応は `POWERSHELL_UTF8` 定数をスクリプトへ付ける仕組みであり、`STRATA_UTF8_TEST` を参照しません。

## 根拠

- `apps/host/tests/powershell-utf8.test.mjs:16-25` — Windows 限定テスト、一時ディレクトリの作成、子 PowerShell プロセスへの変数設定、PowerShell からの参照、結果の検証と後処理。
- `apps/host/server/powershell-utf8.mjs:1-9` — 製品コードの UTF-8 用 PowerShell 接頭辞と `utf8Script()`。`STRATA_UTF8_TEST` は参照しません。
- `apps/host/server/hardware.mjs:14,130,189`、`apps/host/server/snapshot.mjs:4,18`、`apps/host/server/model-directory-default.mjs:5,8`、`apps/host/server/cloudflared-find.mjs:13,138`、`apps/host/server/fonts.mjs:3,15`、`apps/host/server/agent/harness-runtime.mjs:16,131` — 製品コード内で `utf8Script()` を使う箇所。調査対象の環境変数は参照しません。

対象リポジトリ内の環境変数名の全検索では、`STRATA_UTF8_TEST` の参照は上記テストに限られました。したがって、この変数について製品の挙動やサポートを主張できる根拠はありません。
