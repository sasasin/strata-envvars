# `HOMEPATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `HOMEPATH` の値を設定として解釈せず、コーディングアシスタント用 Harness を起動するとき、親プロセス環境から選別した環境変数の一つとして子プロセスへ引き継ぐ。対象名は `KEEP` 正規表現に含まれ、`agentEnvironment()` が `externalEnvironment()` の結果から該当項目をコピーし、その戻り値が Harness の `spawn()` に渡る（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

## 値と判定

値の文字列比較・数値変換・真偽判定はない。名前が大文字小文字を区別しない `KEEP` に一致し、値が `undefined` でなければそのままコピーする。したがって未設定ならコピーされず、空文字列は設定済みの値としてコピーされる。`0`、`1`、`true`、`false`、`0anything`、空白を含む文字列も、値による有効・無効の差はなく、変換もされない（`app/host/server/agent/harness-runtime.mjs:20-33`）。

| 条件 | 未設定 | コピーされる値 | コピーされない値 |
|---|---|---|---|
| Harness 起動時 | `HOMEPATH` が環境にない場合は項目なし | `undefined` 以外の値。空文字列を含め、値は変更せず転送 | 値が `undefined` の場合。値の形式を理由に除外する規則はない |

選別後には `extra` が展開されるため、呼び出し元が `HOMEPATH` を `extra` に渡す場合は、親環境からコピーした値を上書きでき、親環境にない値も追加できる。実際の起動では `HarnessProcess` の `extraEnv`（`agent-bridge.mjs:303-305`）がここへ渡される（`harness-runtime.mjs:34-36,80-83`）。

## 有効になる条件

- `agentEnvironment()` を通る Harness 起動経路で適用される。`agent-bridge.mjs` は Harness が利用可能な場合に `HarnessProcess` を作成し、`hp.start()` を呼ぶ（`app/host/server/agent/agent-bridge.mjs:294-312`）。
- `HOMEPATH` 名は OS や backend による条件分岐なしで allowlist に含まれる（`app/host/server/agent/harness-runtime.mjs:20-33`）。
- `externalEnvironment()` は通常の環境では入力環境を複製する。AppImage 起動時または記録環境がある場合は、記録された元環境（なければ AppImage 固有項目を除いた環境）を選ぶため、Harness に渡る元の `HOMEPATH` はその結果に依存する（`app/host/server/external-env.mjs:43-57,60-71`）。
- `SECRET_NAME` に一致する名前は除外されるが、`HOMEPATH` は一致しない（`app/host/server/agent/harness-runtime.mjs:20-32`）。

## 実行時の詳細

`agentEnvironment()` は Harness の各起動時に `process.env` を読み、`Object.entries()` で環境を走査する。`HOMEPATH` 専用のキャッシュはなく、起動時点の値を `spawn()` の `env` として子プロセスへ渡す。起動後に親プロセス環境を変更しても、既に起動した子プロセスの環境には反映されない。再起動時にはその時点の環境から再構成される（`app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。

`tools/packaging/smoke_terminal.py:56-81` にも `HOMEPATH` の参照があるが、これは Windows 用の packaging smoke test が隔離環境を組み立てる際に `HOMEDRIVE` と併せて値を設定する処理であり、Strata の通常実行時の設定読み取りではない。同ファイルの説明と実装では、アーカイブをクリーン環境で検査するテスト用スクリプトとして扱われている（`tools/packaging/smoke_terminal.py:1-17,56-81,131-145`）。

## ログと測定値

`HOMEPATH` の有無や値を理由とする Strata のログ、警告、エラー、終了処理は確認できない。Harness の起動失敗・終了時の一般的な処理はありますが、`HOMEPATH` に結び付けられたものではありません（`app/host/server/agent/harness-runtime.mjs:88-116`）。測定値は該当しない。

## 根拠

- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — allowlist と値のコピー、子プロセス起動時の環境指定。
- `app/host/server/agent/agent-bridge.mjs:294-312` — Harness 利用可能性確認から `HarnessProcess.start()` まで。
- `app/host/server/external-env.mjs:43-57,60-71` — AppImage 起動時を含む親環境の選択。
- `tools/packaging/smoke_terminal.py:1-17,56-81,131-145` — Windows 用テスト環境での設定と smoke test の用途。
