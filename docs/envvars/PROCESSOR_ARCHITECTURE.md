# `PROCESSOR_ARCHITECTURE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この変数は Strata のモデル実行設定ではありません。Windows 用 PowerShell インストーラーが、Windows on ARM ではないかを判定するために参照します。また、Web プロファイルの Harness を起動するとき、Strata はこの変数を許可リストに含め、ホスト環境に存在すれば子プロセスへ渡します。

## 値と判定

インストーラーでは、先に `PROCESSOR_ARCHITEW6432` を読みます。その値が PowerShell の真偽判定で偽（未設定または空文字など）なら `PROCESSOR_ARCHITECTURE` を使います。選ばれた `$arch` が `AMD64` と等しくなければインストールを中止します。PowerShell の通常の `-ne` は大文字小文字を区別しない文字列比較です。空白や別のアーキテクチャ名は `AMD64` と一致しません。

| 状態 | インストーラーでの扱い |
|---|---|
| `PROCESSOR_ARCHITEW6432` が非空 | その値を優先し、`PROCESSOR_ARCHITECTURE` は判定に使わない |
| `PROCESSOR_ARCHITEW6432` が未設定または空 | `PROCESSOR_ARCHITECTURE` を判定に使う |
| 選択値が `AMD64` と一致 | `windows-x86_64` として処理を続ける |
| 選択値が `AMD64` と不一致（未設定を含む） | `Die` が stderr に理由を出して例外を投げ、インストールを止める |

Harness 起動経路では、値の内容は parse も書き換えもされません。`externalEnvironment` が返した環境のうち、変数名が `KEEP` に一致し、値が `undefined` でなく、秘密情報名の除外規則にも一致しない場合、その値をそのまま子プロセス用環境にコピーします。`PROCESSOR_ARCHITECTURE` は名前の許可リストに一致し、秘密情報名の規則には一致しません。`extra` に同じ名前が明示されていれば、後から展開される `extra` の値がコピー値を上書きします。

## 有効になる条件

- インストーラーでの判定は Windows 専用です。Windows 以外はアーキテクチャ判定より前に「Windows installer」ではないとして終了します。
- Harness への転送は `HarnessProcess.start()` が子プロセスの環境を組み立てるときに行われます。Web プロファイル用 Harness が起動されない場合、この転送経路は実行されません。
- AppImage 外では `externalEnvironment` は入力環境をコピーします。AppImage 内、または `STRATA_ORIGINAL_ENV` がある場合は、記録された起動時環境（記録がなければ AppImage の値を除去した環境）を元にします。そのため AppImage 内では、Harness に渡る値は現在の `process.env` より記録された元環境の値になる場合があります。
- Strata のエンジンやモデル計算がこの値で backend、CPU/GPU 選択、または実行挙動を変更する読み取り箇所は確認できません。

## 実行時の詳細

PowerShell インストーラーはスクリプト実行時にアーキテクチャ値を参照します。非 `AMD64` の場合、`Die` が `strata installer: ... Windows on ARM PC ...` の理由を標準エラーへ出し、例外を投げます。`AMD64` の場合は `$platform` を `windows-x86_64` に設定して後続の配布物選択へ進みます。

Harness では `agentEnvironment(process.env, ...)` が `spawn` の `env` に渡される時点で環境を作ります。従って値の検査やキャッシュではなく、その起動時点の元環境（AppImage では上記の復元環境）を子プロセスへ引き継ぐ処理です。`agentEnvironment` の追加環境に同名のキーがある場合は追加値が優先されます。

## 根拠

- `packaging/install.ps1:24,34-37` — 失敗時の stderr 出力と例外、Windows 限定、`PROCESSOR_ARCHITEW6432` 優先・`PROCESSOR_ARCHITECTURE` fallback、`AMD64` 判定および後続 platform 値。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-83` — 許可リストと値のコピー条件、追加環境の上書き、子プロセス起動時の環境設定。
- `apps/host/server/agent/agent-bridge.mjs:212-229` — Harness の起動経路と profile 環境の受け渡し。
- `apps/host/server/external-env.mjs:28-40,60-70` — AppImage 起動時環境の復元と、AppImage 外で入力環境を使う処理。
