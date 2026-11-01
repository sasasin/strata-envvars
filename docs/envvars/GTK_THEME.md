# `GTK_THEME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の通常の推論・サーバー設定として値を解釈する実装は見つからない。Strata がこの名前を明示的に扱うのは、デスクトップ診断ログへの記録と、外部プログラムへ渡す環境の復元・除去である。値を見て Strata の描画方式や GTK の設定を切り替える分岐はない。

## 値と判定

| 経路 | 未設定 | 設定時 | 変換・制限 |
|---|---|---|---|
| デスクトップ診断 (`graphics_environment`) | 出力対象から省かれる | `GTK_THEME=<値>` の形で記録。空文字なら `GTK_THEME=` | Rust の `std::env::var` で Unicode 文字列を取得し、そのまま整形する。独自 parse、大小文字変換、空文字判定、値域検査はない。Unicode として取得できない場合も `.ok()` により省かれる。 |
| 外部プログラム用環境 (`externalEnvironment`) | コピー元にない | 条件に応じて値をそのまま保持、元環境から復元、または削除 | GTK_THEME 固有の値変換はない。AppImage の元環境レコードでは `KEY=VALUE` の値部分を文字列として保持し、空値も表現できる。 |

## 有効になる条件

- **診断記録:** デスクトップアプリのクラッシュレポート生成、またはログ保存時に現在のプロセス環境から読み取る。値はエラー判定や終了条件には使われない。`crash_report()` は `Graphics session` 欄に加え、`save_logs()` は同じ欄に出力する（`apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-340`）。
- **外部プログラムへの環境:** ホストが `externalEnvironment()` を使って子プロセス環境を作る経路に限る。`APPIMAGE` / `APPDIR` と `STRATA_ORIGINAL_ENV` のどちらもない場合は現在の環境をそのまま複製する。有効な `STRATA_ORIGINAL_ENV` がある場合は起動前の環境を使い、AppImage 環境だが有効な記録がない場合は現在の環境から `GTK_THEME` を削除する（`apps/host/server/external-env.mjs:17-24,28-40,43-71`）。AppImage の repack スクリプトはこの元環境を `env -0 | base64` で記録する（`apps/desktop/scripts/repack-appimage.sh:52-58`）。
- エージェントのシェル環境は `externalEnvironment(base)` の後に `KEEP` allowlist で絞られ、`GTK_THEME` は allowlist に含まれないため除外される（`apps/host/server/agent/harness-runtime.mjs:20-36`）。

## 実行時の詳細

デスクトップ側は `graphics_environment()` を呼ぶたびに環境を読み直し、static cache はない。クラッシュレポートでは「Graphics session」欄へ一行ずつ追加し、ログ保存では同欄を `strata-logs-*.txt` に書く。値による Strata の警告、fallback、失敗、終了コード変更はない（`apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,281-289,310-340`）。

ホスト側の `externalEnvironment()` も呼び出し時の `process.env`（または渡された `env`）から新しい環境オブジェクトを作る。参照箇所はフォルダ選択、`xdg-open` 等の起動、アーティファクトを開く処理、テキストファイル確認、通知、およびエージェント実行環境の組み立てである（`apps/host/server/folder-dialog.mjs:106-118,146`; `apps/host/server/chat-files.mjs:89-94`; `apps/host/server/artifacts.mjs:5-6,27-30`; `apps/host/server/app-ui.mjs:38-59`; `apps/host/server/open-text-file.mjs:26-29`; `apps/host/server/agent/harness-runtime.mjs:25-36`）。これらの子プロセス起動が失敗する場合の処理は各呼び出し側にあり、`GTK_THEME` の値自体に対する Strata の特別な失敗経路はない。

## 根拠

- 明示的な読み取りと診断出力: `apps/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-340`。
- AppImage 向けの名前別除去、元環境の復号、外部環境の選択: `apps/host/server/external-env.mjs:17-24,28-40,43-71`。
- 元環境記録の設定: `apps/desktop/scripts/repack-appimage.sh:52-58`。
- 外部環境 helper の呼び出し元: `apps/host/server/chat-files.mjs:89-94`; `apps/host/server/artifacts.mjs:5-6`; `apps/host/server/app-ui.mjs:38-59`; `apps/host/server/folder-dialog.mjs:106-118,146`; `apps/host/server/open-text-file.mjs:26-29`; `apps/host/server/agent/harness-runtime.mjs:25-36`。

`docs/DETAILS.md` に `GTK_THEME` の Strata 側の挙動を定める記述は見つからなかった。外部 GTK/WebKit 等がこの値をどう解釈するかは、この調査文書の対象外。
