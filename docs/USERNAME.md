# `USERNAME`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Windows 用の `tools/windows/enable_large_pages.ps1` が、Windows の「Lock pages in memory」権限を付与する対象アカウント名の初期値として読みます。Strata エンジンの実行時設定ではありません。このスクリプトで `-AccountName` を省略した場合に、現在の PowerShell プロセスの環境変数 `$env:USERNAME` が使われます。

## 値と判定

| 状態 | `AccountName` の初期値 |
|---|---|
| `USERNAME` が設定されている | その文字列 |
| `USERNAME` が未設定 | `$env:USERNAME` は `$null`。別のアカウント名への補完はない |
| スクリプト起動時に `-AccountName <文字列>` を指定 | 指定した文字列。環境変数の値を置き換える |

環境変数の内容を数値や真偽値へ変換したり、空文字を既定の別アカウント名へ置き換えたりする処理はありません。アカウント名の存在確認は、後続の Windows アカウント変換処理に委ねられます。

## 有効になる条件

この変数が使われるのは、スクリプトを Windows PowerShell で起動し、`-AccountName` を省略した場合だけです。Strata 本体やサーバーの動作には影響しません。スクリプトは管理者権限を要求し、管理者でない場合はアカウント名を使った権限変更を行わず、案内を表示して終了します。

## 実行時の詳細

パラメーター既定値としてスクリプト開始時に `$env:USERNAME` を読みます。管理者として実行された場合、`AccountName` は `NTAccount` から SID に変換され、既存の `SeLockMemoryPrivilege` 設定に対象ユーザーがいなければ、その SID を追加したポリシーを適用します。成功時の表示にもアカウント名が使われます。明示的に `-AccountName` を渡せば、環境変数の値にかかわらずその名前が対象です。

変数が未設定または空で有効なアカウント名が渡らず SID 変換に失敗すると、スクリプトの `catch` がエラーを表示して GUI 手順を案内します。権限付与後はサインアウト・サインインまたは再起動が必要との案内がスクリプトにあります。

同名の参照は `tools/test_strata_bench.py` にもありますが、これはテスト専用コードのユーザー名匿名化テストであり、Strata の本番機能の挙動には含めていません。

## 根拠

- `tools/windows/enable_large_pages.ps1:13-16` — `AccountName` の既定値を `$env:USERNAME` に設定。
- `tools/windows/enable_large_pages.ps1:23-34` — 管理者権限の確認と、対象アカウント名を含む案内。
- `tools/windows/enable_large_pages.ps1:37-57` — アカウント名を SID に変換し、既存権限設定へ追加。
- `tools/windows/enable_large_pages.ps1:69-84` — ポリシー適用と成功・失敗時の表示。
- `docs/DETAILS.md:539` — このスクリプトを管理者として実行し、現在のアカウントに権限を付与する手順への案内。
