# `XDG_DATA_DIRS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリがこの変数を読む動作は対象外。

## 役割

Strata は `XDG_DATA_DIRS` をアプリのデータ検索設定として使わず、外部プログラムに渡す環境を整える際に path-list の一つとして扱います。Linux AppImage 内で Strata が起動した場合、AppImage 内のディレクトリをこのリストから除いて、フォルダー選択ダイアログ、`xdg-open`、通知、ファイルを開くアプリ、エージェントの shell/tool に渡します。AppImage 外では、この helper は通常値を変更しません。処理本体は `apps/host/server/external-env.mjs:25-26,43-58,63-71` にあります。

## 値と判定

`XDG_DATA_DIRS` 自体を `process.env.XDG_DATA_DIRS` のように個別参照したり、内容を環境変数専用の形式として検証したりする箇所はありません。`withoutAppImage()` が `PATH_LISTS` の各名前で環境オブジェクトを動的に参照するため、この変数も対象になります（`apps/host/server/external-env.mjs:25-26,51-55`）。

| 状況 | Strata の処理 |
|---|---|
| AppImage 外で `APPIMAGE` / `APPDIR` も `STRATA_ORIGINAL_ENV` もない | `externalEnvironment()` は入力環境をコピーして返すだけです。unset は unset のまま、空文字・その他の値も変更しません（`apps/host/server/external-env.mjs:60-70`）。 |
| `STRATA_ORIGINAL_ENV` に復元可能な記録がある | 記録された起動元環境を返します。そこに `XDG_DATA_DIRS` があればその値が使われ、現在の AppImage 側の値からの再加工はありません（`apps/host/server/external-env.mjs:28-41,67-71`）。 |
| AppImage 環境で記録がない、または記録を復元できない。かつ `APPDIR` が空でない | 値を `:` で分割し、空要素と、`APPDIR` と一致するかその配下で始まる要素を取り除きます。残った要素は元の順序・重複のまま `:` で結合します。要素が残らなければ変数自体を削除します（`apps/host/server/external-env.mjs:43-57`）。 |
| 同上だが `APPDIR` が空または未設定 | path-list の加工は行いません。`withoutAppImage()` が `APPDIR` を空文字として扱うため、元の値（空文字を含む）はそのまま残ります（`apps/host/server/external-env.mjs:44-55`）。 |

`inside()` の照合は大文字小文字を変換せず、パスの正規化も行わず、文字列一致または `${APPDIR}/` / `${APPDIR}//` で始まるかで判定します。`PATH_LISTS` の処理では空要素は常に除かれます。復元可能な記録がある場合は、記録中の値をこの分割・除去処理に通しません。`extra` 引数に同名キーがあれば最後に上書きします（`apps/host/server/external-env.mjs:25-26,43-57,63-71`）。

## 有効になる条件

`externalEnvironment()` の特別処理は、`APPIMAGE` または `APPDIR` が truthy であるか、`STRATA_ORIGINAL_ENV` が truthy の場合に行われます。それ以外ではコピーのみです。`APPDIR` がない場合でも、特別処理に入ると AppImage 専用名を削除しますが、`XDG_DATA_DIRS` を含む path-list の項目除去は `APPDIR` がある場合だけです（`apps/host/server/external-env.mjs:17-26,43-70`）。`STRATA_ORIGINAL_ENV` は Base64 の NUL 区切り `NAME=value` 記録として復号され、復元後に少なくとも一つの項目が得られた場合に復元環境として採用されます（同:28-41）。

Linux AppImage の再梱包スクリプトは AppImage の `AppRun` に、hook より前の起動環境を `env -0 | base64 -w0` で `STRATA_ORIGINAL_ENV` に保存する行を挿入します（`apps/desktop/scripts/repack-appimage.sh:52-58`）。その記録が有効なら `XDG_DATA_DIRS` は起動元の値に戻ります。記録がない旧形式などでは `APPDIR` を含む要素の除去に fallback します。

## 実行時の詳細

この helper は結果を cache せず、呼び出しのたびに環境オブジェクトをコピー・加工します。環境値が変わった後の呼び出しにはその時点の `process.env` が渡ります。Strata は `XDG_DATA_DIRS` に既定値を設定せず、CLI 引数や他の環境変数との値の優先順位も定義しません。相互作用する値は `APPDIR`、`APPIMAGE`、`STRATA_ORIGINAL_ENV` と、呼び出し側が渡す `extra` です（`apps/host/server/external-env.mjs:25-26,60-71`）。

加工済み環境は、Linux フォルダー選択で `zenity` / `kdialog` / `gdbus` に渡され（`apps/host/server/folder-dialog.mjs:105-120,128-157`）、ファイルやフォルダーを開く `xdg-open` など（`apps/host/server/chat-files.mjs:85-94`、`apps/host/server/artifacts.mjs:5-6,27-30`）、アプリ起動・通知（`apps/host/server/app-ui.mjs:34-58`）にも渡されます。エージェント shell/tool 用には `externalEnvironment(base)` の結果をフィルターし、`XDG_` で始まる名前を許可しているため、残った `XDG_DATA_DIRS` は環境に含まれます（`apps/host/server/agent/harness-runtime.mjs:20-36`）。これらの外部プログラムやライブラリが変数をどう解釈するかは、この調査の対象外です。

この helper 自体はログを出さず、変数固有の終了・失敗経路もありません。呼び出し先で失敗した場合、フォルダー選択は chooser の失敗理由を結果として返し（`apps/host/server/folder-dialog.mjs:121-139`）、ブラウザー opener は候補を順に試して全て失敗すると `false` を返します（`apps/host/server/app-ui.mjs:38-52`）。その結果を `XDG_DATA_DIRS` の特定値に結び付ける Strata のコードはありません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:1711-1715`。
- path-list 登録、AppImage 条件、値の加工・復元・上書き: `apps/host/server/external-env.mjs:15-71`。
- 起動元環境を記録する AppImage hook: `apps/desktop/scripts/repack-appimage.sh:52-58`。
- 整形環境の主な渡し先: `apps/host/server/folder-dialog.mjs:105-157`、`apps/host/server/chat-files.mjs:85-94`、`apps/host/server/app-ui.mjs:34-58`、`apps/host/server/artifacts.mjs:5-6`、`apps/host/server/agent/harness-runtime.mjs:20-36`。
