# `STRATA_ORIGINAL_ENV`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Linux AppImage の起動時に、AppImage 側の環境設定が加わる前の環境を NUL 区切りで記録し、Strata ホストが外部プログラム用の環境を組み立てるための内部引き継ぎ値です。AppImage の再パッケージ時に `AppRun` へ追加される処理が、`env -0` の出力を base64 化してこの変数へ設定します（`apps/desktop/scripts/repack-appimage.sh:52-58`）。

Strata ホストの `externalEnvironment()` はこの値を復元し、フォルダー選択ダイアログ、`xdg-open` 等の起動、通知、プレビュー成果物を開く処理、および Harness の shell/tool 環境に使います（`apps/host/server/external-env.mjs:1-13,67-71`; 使用箇所は下記「実行時の詳細」）。これは通常のユーザー向け設定値ではなく、AppImage launcher とホスト間の記録です。

## 値と判定

値は `apps/host/server/external-env.mjs:15,29-41` で `process.env`（または呼び出し側が渡す env object）から読みます。文字列として真偽値や数値を parse するのではなく、base64 として `Buffer.from(raw, 'base64').toString('utf8')` で復号します。

| 入力 | Strata の処理 |
| --- | --- |
| 未設定または空文字 | `if (!raw)` により記録なしとして `null`。AppImage 内なら後述の `withoutAppImage()` へ fallback します。 |
| 非空文字列で復号後に `KEY=VALUE\0` 形式の項目がある | NUL で分割し、最初の `=` より前が空でない項目を環境オブジェクトへ追加します。値に後続の `=` があればそのまま保持します。 |
| 非空文字列だが有効な項目が 0 件 | `null`。現在環境から AppImage の設定を除く fallback を使います。 |
| 壊れた、または不完全な base64 | 明示的な base64 形式検証はありません。Node の `Buffer.from(..., 'base64')` の復号結果を上記の項目規則で処理し、項目がなければ `null` になります。例外が発生した場合も `catch` で `null` です。 |

項目のキー・値に追加の文字種、長さ、数値範囲の検査はありません。同じキーが複数回あれば後の項目が先の値を置き換えます。値が `"1"` かどうかの判定はありません（`external-env.mjs:30-40`）。

## 有効になる条件

- launcher 側の記録生成は `apps/desktop/scripts/repack-appimage.sh` の再パッケージ処理で、展開した AppImage の `AppRun` に同名の記録行がまだない場合に追加されます（`apps/desktop/scripts/repack-appimage.sh:47-60`）。同名文字列がすでにあれば、このスクリプトは新しい行を追加しません。
- ホスト側は `APPIMAGE` または `APPDIR` が truthy、あるいはこの記録変数が truthy の場合に外部環境の再構成を行います（`apps/host/server/external-env.mjs:60-70`）。したがって、AppImage 外で記録もなければ変数は環境を変えません。
- 有効な記録が復元できると、それが外部プログラム用の環境全体になります。ホストプロセスの現在環境とのマージではありません。復元できない場合は現在環境を複製し、AppImage 専用の名前を削除します。`APPDIR` があれば、AppImage 内を指す GTK/GDK/GIO/GST/GI/GSETTINGS/WEBKIT 値や、列挙された path-list 内の AppImage ディレクトリも除きます（`apps/host/server/external-env.mjs:17-26,43-57,69-70`）。
- 呼び出し時の `extra` は復元環境または fallback 環境の後に展開されるため、同じキーがあれば `extra` が優先します（`external-env.mjs:63-70`）。これはこの helper の呼び出し元から渡される環境上書きであり、CLI 引数との優先順位ではありません。

## 実行時の詳細

再パッケージスクリプトは `AppRun` の `this_dir=` 行の直後に、`export STRATA_ORIGINAL_ENV="$(env -0 | base64 -w0)"` を挿入します。従って launcher 実行時点の環境を NUL 区切り・base64 形式で子の Strata プロセスへ渡す実装です（`apps/desktop/scripts/repack-appimage.sh:52-58`）。

ホストの `recordedOriginal()` が `env[RECORD]` を読むため、環境値は `externalEnvironment()` を呼ぶたびに評価され、読み取り結果の static cache はありません（`apps/host/server/external-env.mjs:15,29-40,67-71`）。実際の主な呼び出し先は次のとおりです。

- Harness 起動時の `agentEnvironment()` は復元環境をもとに、許可リストにあるユーザー環境だけを残し、資格情報らしい名前を除外してから Harness 子プロセスへ渡します（`apps/host/server/agent/harness-runtime.mjs:20-36,75-84`）。
- Linux のフォルダー選択は `zenity`、`kdialog`、portal 用 `gdbus` に同じ外部環境を渡します（`apps/host/server/folder-dialog.mjs:112-146,153-164`）。
- ブラウザー opener / `notify-send`、chat file の opener、artifact opener、システムエディター判定にも `externalEnvironment()` の戻り値を渡します（`apps/host/server/app-ui.mjs:38-59`; `apps/host/server/chat-files.mjs:85-94`; `apps/host/server/artifacts.mjs:5-6`; `apps/host/server/open-text-file.mjs:26-29`）。

この変数自体について Strata は警告やログを出しません。復元不能時も helper は fallback を返し、そこで終了・例外にはしません（`external-env.mjs:29-41,67-71`）。その後の外部プログラムが起動できるか、どう失敗を表示するかは各呼び出し元で異なります。例えば opener は短時間内の起動エラーや非ゼロ終了を `false` とし、フォルダ選択は候補を順に試して利用不可理由を返します（`app-ui.mjs:34-52`; `folder-dialog.mjs:123-146`）。これらは外部プログラムの挙動そのものをこの変数の効果として断定するものではありません。

## 根拠

- `apps/desktop/scripts/repack-appimage.sh:52-60` — AppImage 再パッケージ時の記録行の挿入条件と記録形式。
- `apps/host/server/external-env.mjs:15,17-26,29-41,43-71` — 変数名、復元、空・不正記録時の扱い、AppImage 専用環境の除去、分岐と優先順位。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-84` — Harness へ渡す環境のフィルターと起動。
- `apps/host/server/folder-dialog.mjs:112-146,153-164`; `apps/host/server/app-ui.mjs:34-59`; `apps/host/server/chat-files.mjs:85-94`; `apps/host/server/artifacts.mjs:5-6`; `apps/host/server/open-text-file.mjs:26-29` — helper の外部プログラム起動経路。

`apps/host/tests/external-env.test.mjs` に復元値や不正値のテスト参照がありますが、上記の挙動判断は本番実装に基づいています。調査対象の HEAD では、環境変数の実読み取りは helper 内の `env[RECORD]` で確認できました。
