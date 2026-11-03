# `WEBKIT_INJECTED_BUNDLE_PATH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata のホストサーバーは、この変数を WebKit の機能設定として読み取ったり、値を検査したりしません。Linux AppImage から外部プログラムを起動する際の環境整理で、AppImage が付与した環境変数として除去する名前の一覧に含めています。起動元環境を記録した `STRATA_ORIGINAL_ENV` が利用できる場合は、その記録にこの変数が含まれていれば値をそのまま外部プロセスへ渡します。

この処理は、フォルダー選択、ブラウザー・ファイル起動、通知、成果物を開く処理など、`externalEnvironment()` を使う外部プログラムの起動経路に関係します。変数自体がアプリのモデル処理や WebKit の起動を有効化するものではありません。

## 値と判定

値の文字列や形式は parse されず、値を使った分岐もありません。環境オブジェクト上にキーがあるかどうかと、元の起動環境の記録を使えるかどうかで、子プロセスに残るかが決まります。

| 状況 | 外部プロセスへ渡す `WEBKIT_INJECTED_BUNDLE_PATH` |
|---|---|
| AppImage 外で、`STRATA_ORIGINAL_ENV` もない | 現在の環境に設定されていれば、その値を変更せず渡す。未設定なら渡さない。空文字も設定値として残る。 |
| 起動元環境の有効な記録がある | 記録内にキーがあれば記録された値をそのまま渡す。キーがなければ渡さない。現在の Strata プロセス側の値は使わない。 |
| AppImage 環境だが有効な記録がない | `withoutAppImage()` がこのキーを無条件に削除する。値が空でも同じ。 |

`externalEnvironment(env, extra)` に `extra` が渡された場合は最後にマージされるため、`extra` の同名キーが結果を上書きします。確認した本番の呼び出し箇所は引数なしで使っており、この上書きはしていません。

## 有効になる条件

- `externalEnvironment()` は、`APPIMAGE` と `APPDIR` のどちらもなく、かつ `STRATA_ORIGINAL_ENV` が空・未設定なら、現在の環境をそのまま複製します。この経路では対象変数を除去しません。
- それ以外では `STRATA_ORIGINAL_ENV` の記録をデコードします。記録から少なくとも一つの `NAME=value` 項目が得られれば、その記録を外部プログラム向け環境として使います。対象キーは記録時点に存在した場合だけ残ります。
- 記録が空、またはデコード後に項目がなければ `withoutAppImage()` にフォールバックし、対象キーを削除します。フォールバックでは `APPDIR` 以下を指す `WEBKIT*` 変数も追加で除去されますが、この対象名は値や `APPDIR` に関係なく先に削除されます。
- `apps/desktop/scripts/repack-appimage.sh` は AppImage の `AppRun` に `STRATA_ORIGINAL_ENV` を設定する行を追加します。その値は AppImage 側の環境フックが加わる前に起動元環境を記録するものです。
- GPU backend、モデル状態、CLI 引数による条件はありません。Strata がこの値を外部ライブラリへ設定し直す処理も確認できません。

## 実行時の詳細

`externalEnvironment()` は呼び出し時の環境（既定値は `process.env`）を受け取り、呼び出すたびに新しい環境オブジェクトを作ります。対象変数の値を別にキャッシュしません。AppImage の記録がある経路では `recordedOriginal()` が `STRATA_ORIGINAL_ENV` を base64 から UTF-8 に戻し、NUL 区切りの各項目を最初の `=` で分けます。従って対象変数の値に `=` が含まれていても、最初の区切り以降は値として保持されます。

フォールバックの `withoutAppImage()` は入力を複製し、`APPIMAGE_ONLY` の各キーを削除します。この一覧に `WEBKIT_INJECTED_BUNDLE_PATH` が明記されています。結果は外部プログラム起動時の `env` として渡されます。該当する呼び出しは、フォルダー選択（`folder-dialog.mjs`）、`xdg-open` 等の起動（`chat-files.mjs`、`app-ui.mjs`、`artifacts.mjs`）、システムのファイル関連付け照会（`open-text-file.mjs`）です。エージェントのシェル環境は別途 `agentEnvironment()` の許可リストで作られるため、この `WEBKIT_*` 名は許可リストに一致せず渡されません。

この変数だけを理由に Strata が出すログ、警告、終了、エラー経路はありません。外部プログラムが受け取る環境に含まれるかどうかが、ソースから確認できる効果です。外部プログラムや WebKit 自身がその値をどう解釈するかは本調査の対象外です。

## 根拠

- `apps/host/server/external-env.mjs:17-26` — `APPIMAGE_ONLY` の列挙と、パスリスト定義。
- `apps/host/server/external-env.mjs:28-40` — `STRATA_ORIGINAL_ENV` の取得・base64 decode・項目分解。記録が空なら `null`。
- `apps/host/server/external-env.mjs:43-57` — 現在環境の複製、対象キーの削除、`APPDIR` を含む `WEBKIT*` 値の追加除去。
- `apps/host/server/external-env.mjs:60-70` — AppImage／記録の有無による分岐、起動元記録とフォールバックの優先順位、`extra` の最後のマージ。
- `apps/desktop/scripts/repack-appimage.sh:52-58` — AppImage ランチャーが起動元環境を `STRATA_ORIGINAL_ENV` に記録する処理。
- `apps/host/server/folder-dialog.mjs:112-126,135-145,153-164`、`apps/host/server/chat-files.mjs:89-94`、`apps/host/server/app-ui.mjs:38-46,55-60`、`apps/host/server/artifacts.mjs:5-6`、`apps/host/server/open-text-file.mjs:26-29` — 外部プログラムに整理後の環境を渡す呼び出し箇所。
- `apps/host/server/agent/harness-runtime.mjs:20-36` — エージェント環境で任意の環境変数を除外し、許可リストと明示 `extra` だけを渡す処理。
