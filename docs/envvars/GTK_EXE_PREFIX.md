# `GTK_EXE_PREFIX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 自身の GTK 動作を切り替える読み取り箇所は確認できない。ホスト側の `externalEnvironment()` が、AppImage の設定が混ざった環境を外部プログラムへ渡すときに、この名前を `APPIMAGE_ONLY` の一覧に含めて除去する。除去対象は実行中 AppImage 専用の変数とされており、対象の値を Strata が解釈するわけではない（`app/host/server/external-env.mjs:17-24,43-57,64-70`）。

この環境は Linux のフォルダ選択、ブラウザー起動、ファイルを開く処理、通知、チャットファイル起動などの外部コマンドに渡される（例: `app/host/server/folder-dialog.mjs:112-126`, `app/host/server/app-ui.mjs:39-47`, `app/host/server/chat-files.mjs:89-94`）。値による Strata のモデル・計算・CLI 動作の変更はない。

## 値と判定

`GTK_EXE_PREFIX` の値を直接取得・比較・変換するコードはない。`withoutAppImage()` は環境オブジェクトを複製した後、名前の一覧を使って `out[name]` を削除するため、値の形式・大文字小文字・数値性を検査しない（`app/host/server/external-env.mjs:18-24,43-57`）。挙動は `externalEnvironment()` の分岐で決まる。

| 条件 | unset | 設定時（例: 空文字、`/path`、任意の文字列） |
|---|---|---|
| AppImage 外で `APPDIR` / `APPIMAGE` がなく、`STRATA_ORIGINAL_ENV` もない | そのまま | 元の値をそのまま外部環境へコピー |
| `STRATA_ORIGINAL_ENV` に復元可能な元環境がある | 記録にキーがなければ未設定のまま | 記録された元環境の値を渡す（空文字も保持） |
| AppImage 内で元環境記録がない、または復元できない | 未設定のまま | `APPIMAGE_ONLY` に従い削除 |

いずれの分岐にも `GTK_EXE_PREFIX` 固有の既定値、CLI 引数との優先順位、値の fallback はない。呼び出し側が `externalEnvironment(env, extra)` の `extra` に同名キーを指定すれば最後に追加・上書きされる（`app/host/server/external-env.mjs:64-70`）。

## 有効になる条件

- GTK や GPU backend の条件ではなく、外部プロセス用環境を生成するときの `APPDIR` / `APPIMAGE` と `STRATA_ORIGINAL_ENV` の有無・内容で決まる（`app/host/server/external-env.mjs:60-70`）。
- AppImage の `AppRun` は起動時の環境を `STRATA_ORIGINAL_ENV` に記録するよう再パッケージ処理でフックを加える（`app/desktop/scripts/repack-appimage.sh:79-85`）。有効な記録があれば、その元環境を使うため、元から存在した `GTK_EXE_PREFIX` は保持される。
- 起動時環境の記録がない旧 AppImage では、`withoutAppImage()` がこのキーを削除する（`app/host/server/external-env.mjs:43-57,67-70`）。
- エージェント Harness 向け環境はさらに `KEEP` の名前パターンで絞るため、`GTK_EXE_PREFIX` は通常コピーされない。明示的な `extra` はフィルター後に追加される（`app/host/server/agent/harness-runtime.mjs:20-36,80-83`）。

## 実行時の詳細

`externalEnvironment()` は呼び出しごとに渡された環境（省略時はその時点の `process.env`）を使い、新しいオブジェクトを返す。`GTK_EXE_PREFIX` をキャッシュしたり後から再読したりはしない。`STRATA_ORIGINAL_ENV` が truthy なら Base64 文字列を UTF-8 に復号し、NUL 区切りの `NAME=value` 項目から元環境を組み立てる。記録が空、壊れて空の項目しか得られない場合は `withoutAppImage()` に fallback する（`app/host/server/external-env.mjs:28-40,64-70`）。

外部コマンド起動時に環境オブジェクトとして渡されるため、上記で残った値は子プロセスに渡る。例として Linux フォルダ選択は同じ環境を `zenity` / `kdialog` および portal 用 `gdbus` に渡し、エージェント起動は `agentEnvironment()` の結果を Harness に渡す（`app/host/server/folder-dialog.mjs:117-126,135-164`, `app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。

## 根拠

- `app/host/server/external-env.mjs:17-24,43-57,60-70` — 除去リスト、オブジェクトの削除、外部環境の分岐と `extra` の優先。
- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage 起動元の環境を記録するフック。
- `app/host/server/folder-dialog.mjs:112-126,135-164` — 環境を渡す外部プログラムの例。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — Harness 用環境の追加フィルターと子プロセスへの受け渡し。
- `app/host/server/app-ui.mjs:39-47,56-60`, `app/host/server/chat-files.mjs:89-94` — opener / notification / ファイル起動の例。
