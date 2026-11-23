# `LIBRARY_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のホスト側 Node.js コードは、外部プログラムへ渡す環境を整える際に `LIBRARY_PATH` を「パス一覧」の一つとして扱う。Linux AppImage の自身のディレクトリを指す要素があれば取り除き、外部プログラムに Strata 同梱環境の値を持ち込まないための処理である。これは Strata が `LIBRARY_PATH` をライブラリ探索に使う設定ではなく、値を外部プロセス向け環境から保持または除去する処理である（`app/host/server/external-env.mjs:25-26,43-57,64-70`）。

この環境はフォルダ選択ダイアログ、デスクトップ通知、URL/ファイルを開く処理などで子プロセスへ渡される（`app/host/server/folder-dialog.mjs:117-126,153-154`、`app/host/server/app-ui.mjs:39-59`、`app/host/server/chat-files.mjs:89-94`、`app/host/server/open-text-file.mjs:26-29`、`app/host/server/artifacts.mjs:5-6`）。アシスタント用プロセスでは、外部環境を作った後に許可名リストでさらに絞るため、`LIBRARY_PATH` はその子環境へ渡らない（`app/host/server/agent/harness-runtime.mjs:20-33`）。

## 値と判定

`external-env.mjs` は `PATH_LISTS` の各名前について、環境オブジェクトに文字列値があるかを確認し、`:` で分割する。したがって `LIBRARY_PATH` の内容自体を真偽値や数値として解釈せず、空要素を捨て、現在の AppImage ディレクトリそのもの、またはその下で始まる要素を除去する。残った要素は元の順で `:` 結合され、1 件も残らなければ環境変数自体を削除する（`app/host/server/external-env.mjs:25-26,43-57`）。

| 条件 | unset | 設定時に残る値 | 除去・削除される値 |
|---|---|---|---|
| `APPDIR` があり、元環境の記録を使わない場合 | そのまま未設定 | 空でない要素のうち、`APPDIR` と一致せず、`APPDIR/` または `APPDIR//` で始まらない要素 | 値が空文字、または全要素が空／AppImage 内を指す場合は変数を削除。該当要素だけを取り除き、残りは保持 |
| `APPDIR` がない場合 | そのまま未設定 | 入力値を変更せず保持 | なし |
| 有効な `STRATA_ORIGINAL_ENV` 記録がある場合 | 記録に名前がなければ未設定 | 記録された元環境の値をそのまま使用 | AppImage 内の値を追加で除去しない |

文字列の大小文字、空白、数値としての妥当性は検査しない。区切り文字はコード上 `:` 固定で、要素は正規化されず単純な文字列一致／prefix 判定を受ける。たとえば `APPDIR` が `/tmp/.mount_x` のとき、`/tmp/.mount_x/lib` は除去されるが、`/tmp/.mount_x-old/lib` は prefix が `/tmp/.mount_x/` ではないため残る（`app/host/server/external-env.mjs:45-55`）。

## 有効になる条件

- AppImage 内ディレクトリの除去は、現在の環境に `APPDIR` が設定され、かつ有効な元環境記録が使われない場合に限られる。`insideAppImage` 自体は `APPIMAGE` または `APPDIR` の有無を見ているが、パス一覧を変更する `withoutAppImage` は `APPDIR` が空なら値を変更しない（`app/host/server/external-env.mjs:43-57,60-70`）。
- ランチャーが設定する `STRATA_ORIGINAL_ENV` を正常に復号でき、空でない環境オブジェクトになれば、その記録が優先される。記録の作成は AppImage ランチャーで起動元の環境全体を NUL 区切り・Base64 化して行う（`app/desktop/scripts/repack-appimage.sh:79-85`、`app/host/server/external-env.mjs:28-40,67-70`）。
- `externalEnvironment(env, extra)` の `extra` に同名の値があれば、外部環境を選んだ後にその値で上書きされる（`app/host/server/external-env.mjs:64-70`）。確認した通常の呼び出し箇所は既定の空 `extra` を使う。アシスタント環境は別途 `KEEP` に一致する名前だけを残すため、この変数は除外される（`app/host/server/agent/harness-runtime.mjs:20-33`）。
- `LIBRARY_PATH` が有効な値でも、環境を外部プロセスに渡す経路でなければこの helper による変更は起きない。Strata 本体の GPU/backend、CLI の計算経路を制御する読み取りは確認できない。

## 実行時の詳細

`LIBRARY_PATH` は `PATH_LISTS` の文字列要素として登録され、`withoutAppImage` 内で `out[name]` を動的に読む。helper の既定引数は呼び出し時点の `process.env` であり、呼び出しごとに環境オブジェクトを複製して判定する。値のキャッシュやプロセス起動後の変更を固定する処理はない（`app/host/server/external-env.mjs:25-26,43-57,67-70`）。

有効な元環境記録があると、現プロセス環境を削って再構成するのではなく、起動時に記録された環境オブジェクトを使う。従ってこの経路では、記録後に現在の `LIBRARY_PATH` が変わっても反映されない。記録がない、空、または復号後に空のオブジェクトとなる場合は `withoutAppImage` の処理へ進む（`app/host/server/external-env.mjs:28-40,67-70`）。

## 根拠

- `app/host/server/external-env.mjs:25-26,43-57,64-70` — 対象名の登録、値の分割・除去・削除、元環境と `extra` の優先順。
- `app/host/server/external-env.mjs:28-40,60-70` — 起動環境記録の復号、有効性判定、AppImage 判定と分岐。
- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage ランチャーによる起動元環境の記録。
- `app/host/server/folder-dialog.mjs:117-126,153-154`、`app/host/server/app-ui.mjs:39-59`、`app/host/server/chat-files.mjs:89-94`、`app/host/server/open-text-file.mjs:26-29`、`app/host/server/artifacts.mjs:5-6` — 外部プロセスに環境を渡す呼び出し。
- `app/host/server/agent/harness-runtime.mjs:20-33` — アシスタント用の子環境における許可名フィルタ。

索引の候補名に対し Strata 所有の実装で確認できたのは、この外部環境フィルタ処理である。Strata のエンジンや計算動作が `LIBRARY_PATH` を読む実装は確認できなかった。
