# `WEBKIT_EXEC_PATH`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 自身のモデル処理や UI 動作を切り替える設定ではない。ホスト側コードはこの値を解析せず、外部プログラム向け環境から AppImage 専用値として除去するか、起動元の環境を復元して引き渡す。対象名を個別に扱う実装は `apps/host/server/external-env.mjs` の `APPIMAGE_ONLY` と環境組み立て処理である（`apps/host/server/external-env.mjs:17-24,43-57,63-71`）。

## 値と判定

Strata は `WEBKIT_EXEC_PATH` の値を数値・真偽値・パスとして検証せず、変換もしない。空文字を含む値をそのまま環境オブジェクト間で保つ経路と、値にかかわらずキーごと削除する経路がある。CLI 引数との優先順位や fallback はない。`externalEnvironment` の `extra` に同名キーが明示的に渡された場合は最後に上書きされるが、確認した呼び出し箇所は `extra` にこの名前を渡していない（`apps/host/server/external-env.mjs:63-71`）。

| 条件 | 未設定 | 設定時の扱い |
|---|---|---|
| `externalEnvironment` が AppImage 外で、`STRATA_ORIGINAL_ENV` もない | キーは引き継がれない | 値を検査せず外部プログラム用環境にコピーする。空文字や任意の文字列もそのまま（`apps/host/server/external-env.mjs:61-70`）。 |
| AppImage 環境で、`STRATA_ORIGINAL_ENV` に復元可能な起動元環境がある | 起動元記録にキーがなければ出力にもない | 現在の AppImage 環境値ではなく、記録をデコードした起動元の値を使う。記録にキーがあれば空文字を含めそのままコピーする（`apps/host/server/external-env.mjs:28-40,67-70`）。 |
| AppImage 環境で、有効な起動元記録がない | 出力にもない | `withoutAppImage` が値にかかわらず `APPIMAGE_ONLY` のキーを削除する（`apps/host/server/external-env.mjs:17-24,43-57,67-70`）。 |
| Harness の agent shell / tools 用環境 | 通常は出力にもない | `agentEnvironment` の許可名パターンに `WEBKIT_EXEC_PATH` は含まれないため、元環境からは除かれる。実際の起動呼び出しが追加する環境名も `STRATA_HOST_URL` と `STRATA_INTERNAL_SECRET` で、このキーを追加しない（`apps/host/server/agent/harness-runtime.mjs:22-36,80-83`; `apps/host/server/index.mjs:1194`）。 |

値の比較、大文字小文字、前後空白、数値としての境界判定は行わない。`WEBKIT_EXEC_PATH=` のような空値も、コピー対象の経路では値として保持され、AppImage 専用環境を掃除する経路では他の値と同じくキーごと除去される。

## 有効になる条件

- AppImage 外で起動したホストから外部プログラムを起動する場合は、`externalEnvironment` が環境をそのまま複製するため、設定値は引き渡される（`apps/host/server/external-env.mjs:61-70`）。
- AppImage では `APPIMAGE` または `APPDIR` があると AppImage 内として扱われる。外部プログラム用環境は、有効な `STRATA_ORIGINAL_ENV` があれば記録された元環境から作り、そうでなければ AppImage 専用キーを取り除いた現在環境から作る（`apps/host/server/external-env.mjs:43-48,60-70`）。パッケージングスクリプトは AppImage の `AppRun` に `env -0 | base64 -w0` の記録を設定する（`apps/desktop/scripts/repack-appimage.sh:80-85`）。
- Linux のフォルダ選択では `zenity`、`kdialog`、`gdbus` に `externalEnvironment()` の結果を渡す（`apps/host/server/folder-dialog.mjs:112-126,135-165`）。ブラウザー起動、通知、ファイル・artifact のオープンでも同じ helper の結果を子プロセスに渡す（`apps/host/server/app-ui.mjs:38-58`; `apps/host/server/artifacts.mjs:5-6`; `apps/host/server/chat-files.mjs:89-94`; `apps/host/server/open-text-file.mjs:26-29`）。
- Harness の agent shell / tools は上記とは別に環境名を許可リストで絞り、このキーを渡さない（`apps/host/server/agent/harness-runtime.mjs:22-36,80-83`）。
- updater による Strata 再起動では、Rust supervisor が `STRATA_ORIGINAL_ENV` をデコードし、その環境を `env_clear().envs(...)` で新プロセスへ渡す。復元対象から除外するのは `STRATA_ORIGINAL_ENV` 自身であり、このキーは除外されないため、元環境に設定されていれば再起動先にも引き継がれる。有効な記録がない場合は現在の環境を継承し、別の supervisor 用キーだけを削除する（`apps/desktop/src-tauri/src/supervisor.rs:272-297,356-366`）。

## 実行時の詳細

値を独立して読み込む起動時設定や cache はない。Node 側では `externalEnvironment` の呼び出し時に渡された `env`（通常はその時点の `process.env`）を複製し、`APPIMAGE` / `APPDIR` / `STRATA_ORIGINAL_ENV` の有無で分岐する。AppImage 内の記録復元は base64 を UTF-8 文字列にし、NUL 区切りの `名前=値` 項目を環境オブジェクトへ組み立てる（`apps/host/server/external-env.mjs:28-40,60-70`）。記録値はランチャー起動時に作られるため、その後の環境変更で記録内容が更新される処理はない（`apps/desktop/scripts/repack-appimage.sh:83-85`）。

Rust supervisor の updater 再起動は `STRATA_ORIGINAL_ENV` の記録を最大 8 重までたどり、見つかった元環境を新しいプロセスへ渡す。失敗時は元環境復元に切り替わらず現在環境を継承する（`apps/desktop/src-tauri/src/supervisor.rs:272-297,356-366`）。

## ログと測定値

このキーの有無・値や除去を示す専用ログ、警告、終了・失敗分岐は見つからない。環境組み立て時の処理だけで、性能・正確性の測定値も該当しない（`apps/host/server/external-env.mjs:43-71`）。子プロセス起動自体の一般的な結果処理は各呼び出し元にあるが、`WEBKIT_EXEC_PATH` の値による分岐ではない。

## 根拠

- `apps/host/server/external-env.mjs:17-24,28-40,43-71` — AppImage 専用キー一覧、起動元記録の復元、外部環境の生成。
- `apps/host/server/folder-dialog.mjs:112-145,153-165`; `apps/host/server/app-ui.mjs:38-58`; `apps/host/server/artifacts.mjs:5-6`; `apps/host/server/chat-files.mjs:89-94`; `apps/host/server/open-text-file.mjs:26-29` — 外部プログラム起動時の環境引き渡し。
- `apps/host/server/agent/harness-runtime.mjs:22-36,80-83`; `apps/host/server/index.mjs:1194` — agent shell / tools 用環境の許可リストと実際に加える環境名。
- `apps/desktop/scripts/repack-appimage.sh:80-85`; `apps/desktop/src-tauri/src/supervisor.rs:272-297,356-366` — AppImage 起動元環境の記録と updater 再起動時の復元。
