# `USERNAME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは clean（`## main...origin/main`）。

## 役割

Strata 本体の設定値ではありません。リポジトリ内では、Windows の大きなページ用権限を設定する補助 PowerShell スクリプトが、対象アカウント名の既定値として読みます。また、デスクトップの agent 起動時に、ホスト環境から Harness の子プロセスへ渡す環境変数名の許可リストに含まれます。

この変数で Strata engine の挙動や大きなページの使用可否を直接切り替える実装は確認できません。ベンチマークの redaction unittest にも参照がありますが、これはテスト専用です。

## 値と判定

| 用途 | 未設定・空文字 | 設定値・変換 |
|---|---|---|
| `tools/windows/enable_large_pages.ps1` の既定アカウント | `$env:USERNAME` が未設定なら `$AccountName` の既定値は空文字相当。空文字かどうかの検証や代替値はありません。 | 値を文字列のアカウント名として使います。数値化・trim・大文字小文字変換はありません。スクリプト引数 `-AccountName` を渡した場合は PowerShell の param 既定値が使われず、引数が対象名になります。 |
| agent の Harness 環境 | 入力環境にキーがなければ渡されません。空文字は `undefined` ではないため、許可リストに通れば空文字のまま渡ります。 | 環境変数名を大文字小文字を区別しない正規表現で判定し、値はそのままコピーします。`USERNAME` の値自体は parse しません。 |
| ベンチマーク redaction unittest | `USERNAME` が空または未設定なら `USER`、さらにそれも空・未設定なら `tester` を使います。 | `os.environ.get("USERNAME") or ...` により Python の falsy な空文字は fallback します。ユーザー名が4文字以上なら redactor のテスト入力にも使います。 |

## 有効になる条件

- Windows 補助スクリプトでのみ、PowerShell 起動時に `-AccountName` を省略した場合に既定値として使われます。管理者でない場合はアカウント解決より先に終了コード `1` で停止します。`-AccountName` は環境値を上書きします。
- Harness への転送は `agentEnvironment()` が実行される経路に限られます。環境名が `KEEP` に一致し、`SECRET_NAME` に一致しない場合にコピーされます。`USERNAME` は許可対象で、秘密名フィルターには一致しません。`HarnessProcess.start()` がこの生成結果を子プロセスの `env` に設定します。
- `tools/test_strata_bench.py` の参照は `unittest.TestCase` の redaction テスト内だけです。通常の Strata 実行時に適用される設定ではありません。

## 実行時の詳細

Windows スクリプトは `$AccountName` を `NTAccount` として SID に解決し、エクスポートしたユーザー権利設定の `SeLockMemoryPrivilege` の一覧にその SID を追加します。既に対象名または SID が載っていれば `[OK] ... already possesses ...` を表示して戻ります。管理者実行時の成功経路は `[SUCCESS] ... has been granted ...` を表示し、アカウント解決やポリシー更新の例外は `[ERROR] Failed to configure privilege automatically: ...` を表示します。未設定時に有効なアカウント名が得られる保証や、対象名の事前検証・別名 fallback はコードにありません。これは手動実行する補助スクリプトの処理で、engine 起動時に自動実行される経路は確認できません。

Harness 経路は agent の実行環境を作る時点で親環境（AppImage の場合は復元された元環境）から値をコピーし、子プロセス起動時に渡します。`USERNAME` を個別に読み直したり内容を変換したりする cache はありません。この転送は agent が起動されるときに限られ、Strata 本体の環境設定としての効果を示すものではありません。

## 根拠

- `tools/windows/enable_large_pages.ps1:13-16` — `$AccountName` の既定値が `$env:USERNAME`。
- `tools/windows/enable_large_pages.ps1:23-34,37-47,49-85` — 管理者チェックと終了、アカウント SID 解決、権利一覧の確認・更新、成功・失敗表示。
- `apps/host/server/agent/harness-runtime.mjs:20-36,67-83` — 環境名フィルター、値コピー、AppImage 用環境の選択を経て Harness 子プロセスに `env` を設定。
- `apps/host/server/external-env.mjs:28-40,60-70` — AppImage で起動元環境を復元する場合と、それ以外の環境選択。
- `apps/host/server/agent/agent-bridge.mjs:205-223` — profile と Harness の起動経路。
- `tools/test_strata_bench.py:169-187` — `USERNAME` / `USER` / `tester` のテスト用 fallback と redaction assertion。
- `apps/desktop/src-tauri/nsis/installer.nsi:125` の `MULTIUSER_INSTALLMODEPAGE_SHOWUSERNAME` は NSIS のビルド定義で、環境値の読み取りではありません。

`000_envvers.md` の候補名は、上記の補助スクリプトでの実読取と agent 環境の転送によって Strata 所有コード上の使用が確認できました。環境変数文書の根拠に使わないテスト用コード、NSIS 定義、および外部 Harness 側が `USERNAME` をどう使うかは、Strata の挙動として扱っていません。
