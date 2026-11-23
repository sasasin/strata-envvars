# `QT_PLUGIN_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のアプリ本体が Qt plugin を選ぶ設定としては使っていない。ホスト側の `external-env.mjs` が `QT_PLUGIN_PATH` をパスリスト環境変数の一つに含め、AppImage のライブラリ環境を外部プログラムへ渡さないための環境整理で参照する。対象はフォルダ選択やファイル・URL を開くプログラム、通知、ならびにエージェント用子プロセスの環境である（`app/host/server/external-env.mjs:1-13,26,64-70`、利用箇所は `app/host/server/folder-dialog.mjs:113-126`、`app/host/server/chat-files.mjs:89-94`、`app/host/server/artifacts.mjs:5-6,17-20`、`app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。

したがって Strata がこの値を `QT_PLUGIN_PATH` 固有の機能へ適用したり、値に応じて Strata の画面・モデル・生成結果を変えたりする実装は確認できない。環境の復元・清掃が実行されるときに、子プロセスへ元の値を保つか AppImage 内のパス要素を取り除くかが変わる。

## 値と判定

`external-env.mjs` は `PATH_LISTS` の各名前を `out[name]` で動的に参照する。`QT_PLUGIN_PATH` はこの配列に含まれる。値の真偽・数値・文字列全体の形式を検査せず、無効値扱いの分岐もない。処理は `APPDIR` と `STRATA_ORIGINAL_ENV` の状態で異なる（`app/host/server/external-env.mjs:15,26,43-57,60-70`）。

| 条件 | 未設定 | 空文字 | 値がある場合 |
|---|---|---|---|
| `APPIMAGE` / `APPDIR` と記録変数のどちらもない | そのまま未設定 | そのまま空文字 | 変更せずコピー |
| 有効な `STRATA_ORIGINAL_ENV` の記録がある | 記録内にもなければ未設定 | `QT_PLUGIN_PATH=` の形で記録されていれば空文字を復元 | 記録された元の文字列をそのまま復元 |
| 記録がなく `APPDIR` がある旧 AppImage | 未設定のまま | 分割後に要素が残らないためキーを削除 | `:` で分割し、空要素と `APPDIR` と同じパス、またはその直下から始まる要素を除去。残りを `:` で連結し、空ならキーを削除 |
| 記録がなく `APPIMAGE` だけがあり `APPDIR` はない | 未設定のまま | 空文字のまま | パス清掃の `dir` が空なので変更せず保持 |

旧 AppImage の要素除去は大文字小文字を区別する文字列前方一致であり、各要素が `APPDIR` と一致するか、`${APPDIR}/` または `${APPDIR}//` で始まるかを判定する。コロン区切りとして分割するため、値全体の空白除去や妥当性検査、パス正規化はしない。元環境の記録では、NUL 区切りの各項目から最初の `=` より前を名前、後ろを値として復元し、値が空でもエントリを保持する（`app/host/server/external-env.mjs:29-40,45-55`）。

## 有効になる条件

- この変数に関する加工は、外部プログラム向け環境を `externalEnvironment()` が作るときだけ行われる。AppImage 外で `APPIMAGE`・`APPDIR`・記録変数がなければ、コピー時に値は変更されない（`app/host/server/external-env.mjs:60-70`）。
- AppImage 起動時に `STRATA_ORIGINAL_ENV` が記録されていれば、旧 AppImage 用の `APPDIR` パス清掃ではなく、記録された元環境が採用される。パッケージング用スクリプトは AppImage ランチャーで `env -0 | base64 -w0` を記録する（`app/desktop/scripts/repack-appimage.sh:79-85`）。
- 記録がない場合、パス要素の清掃には `APPDIR` が必要。`APPIMAGE` だけではこの変数の値を変えない（`app/host/server/external-env.mjs:44-55,60-70`）。
- `externalEnvironment(env, extra)` の `extra` が同名のキーを持つ場合、その値が最後に上書きされる（`app/host/server/external-env.mjs:64-70`）。確認した呼び出し箇所では `QT_PLUGIN_PATH` を `extra` に指定していない。
- Harness 用の子プロセス環境は `externalEnvironment(base)` の後に `KEEP` 正規表現でさらに絞られる。正規表現は `PATH` を許可するが `QT_PLUGIN_PATH` には一致しないため、この経路では値は子プロセスへ渡らない（`app/host/server/agent/harness-runtime.mjs:20-36,80-83`）。
- CLI 引数、モデル状態、GPU backend、OS 固有の値判定でこの処理を有効化する条件は見つからない。AppImage 関連の環境状態が条件である。

## 実行時の詳細

共通関数は呼び出しごとに渡された環境オブジェクト（省略時は `process.env`）をコピーして処理し、結果を子プロセスの `env` として渡す。`QT_PLUGIN_PATH` 専用の起動時キャッシュや値の保存はない（`app/host/server/external-env.mjs:29,44,67-70`）。

通常起動と記録付き AppImage では、外部プログラム用環境に入る値はそれぞれ現在の環境値、または起動時に記録された値である。記録付き AppImage では Strata 起動後にこの値が変わっても、元環境の記録を使う呼び出しにはその変更は反映されない。記録なし旧 AppImage では呼び出し時の `APPDIR` と `QT_PLUGIN_PATH` を使って清掃する。

この環境 helper は `zenity` / `kdialog` / `gdbus` によるフォルダ選択、`xdg-open` 等によるファイル・URL のオープン、`notify-send`、および Harness 環境の生成経路から呼ばれる（`app/host/server/folder-dialog.mjs:117-126,135-154`、`app/host/server/chat-files.mjs:89-94`、`app/host/server/app-ui.mjs:39-59`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/agent/harness-runtime.mjs:25-36,80-83`）。デスクトップのアップデータ再起動では、別の経路で起動時記録の環境全体を復元して Strata を再起動するため、記録に含まれる `QT_PLUGIN_PATH` も一般の環境変数として引き継がれる（`app/desktop/src-tauri/src/supervisor.rs:274-298,358-362`）。

## ログと測定値

`QT_PLUGIN_PATH` の値や清掃結果を理由に出す専用ログ、警告、終了コードはない。`externalEnvironment()` 内でこの値を検証してエラーにする経路もない。呼び出し先のプロセス起動成否は各呼び出し元の通常の処理に従うが、その結果を `QT_PLUGIN_PATH` の値に結びつける Strata の処理は確認できない。

## 根拠

- `app/host/server/external-env.mjs:15-26,29-57,60-70` — 動的な値参照、未設定時の既定経路、AppImage 環境の選択・清掃。
- `app/host/server/folder-dialog.mjs:113-154`、`app/host/server/chat-files.mjs:85-94`、`app/host/server/app-ui.mjs:39-59`、`app/host/server/artifacts.mjs:5-6,10-20` — 外部プログラムへの環境引き渡し。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — Harness 子プロセス向け許可リストによる除外。
- `app/desktop/scripts/repack-appimage.sh:79-85`、`app/desktop/src-tauri/src/supervisor.rs:274-298,358-362` — 元環境の記録と、再起動時の環境復元。
