# `GST_PLUGIN_PATH_1_0`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Strata 自身の機能やエンジン設定を変える値としては読み取られていない。ホストの `external-env.mjs` が、外部プログラムに渡す環境を作る際の `APPIMAGE_ONLY` 除去リストに名前を含める。通常起動や、AppImage の起動前環境を復元できる場合は外部プログラムへ値が残り、古い AppImage の環境を掃除する場合は値にかかわらず取り除かれる（`app/host/server/external-env.mjs:17-26,43-57,63-71`）。この名前自体はコード上に 1 箇所だけ現れる（同:22）。

この処理は Linux AppImage に同梱されたライブラリ環境からシステムプログラムを切り離すための環境転送であり、Strata が GStreamer を起動したり、この値を検証したりする実装ではない（同:2-13）。

## 値と判定

文字列比較、数値変換、空白除去は行わない。値の意味や妥当性を判定せず、環境オブジェクトからキーをコピーするか削除するかだけを決める。したがって、保持される経路では未設定なら未設定のまま、空文字を含む設定値はそのまま渡される。除去経路では未設定・空文字・その他の値のいずれも子プロセス環境に残らない（`app/host/server/external-env.mjs:18-24,44-57,67-71`）。

| 環境の組み立て経路 | 未設定 | 設定値の扱い | 例 |
|---|---|---|---|
| `APPIMAGE` / `APPDIR` がなく、`STRATA_ORIGINAL_ENV` もない | 未設定のまま | 変更せずコピー | `''`、`/path/to/plugins`、任意の文字列をそのまま保持 |
| `STRATA_ORIGINAL_ENV` に復元可能な起動前環境がある | 起動前環境で未設定なら未設定 | 起動前環境の値をそのまま復元 | 空文字も任意の文字列もそのまま保持 |
| AppImage 環境で起動前環境を復元できない | キーを削除 | 値にかかわらずキーを削除 | `''`、`/path/to/plugins` とも除去 |
| Harness エージェント子プロセス | 通常は渡さない | `KEEP` 許可リストに一致しないため除外 | 明示的な `extra` に指定した場合は後段で追加可能 |

外部プログラム向け環境で追加引数 `extra` が与えられた場合は、それが最後にマージされるため同名キーを上書きできる（`app/host/server/external-env.mjs:64-70`）。現行の Harness 起動側が渡す追加環境は `profile.env` と `STRATA_UPDATE_PAUSE_FILE` であり、この名前を追加していない（`app/host/server/agent/agent-bridge.mjs:303-304`）。

## 有効になる条件

- Strata 内の推論 backend、OS の GPU 選択、モデル状態、CLI 引数によってこの値の解釈が変わる分岐はない。エンジン側の値判定もない（`app/host/server/external-env.mjs:17-26`）。
- `externalEnvironment()` は通常起動では現在の環境をコピーする。AppImage 起動時に有効な `STRATA_ORIGINAL_ENV` があれば、記録された起動前環境を使う（同:28-40,60-71）。AppImage の起動前環境はランチャーが `env -0 | base64 -w0` で記録する（`app/desktop/scripts/repack-appimage.sh:79-85`）。
- 古い AppImage などで起動前環境の記録を使えない場合は、`withoutAppImage()` が `APPIMAGE_ONLY` の各キーを削除するため、この変数も値に関係なく除去される（`app/host/server/external-env.mjs:17-24,43-57,67-71`）。
- `externalEnvironment()` を使う外部起動経路には、チャットファイルの open/reveal、フォルダー選択、artifact の open、システム opener・通知、テキストエディター確認がある（`app/host/server/chat-files.mjs:85-95`、`app/host/server/folder-dialog.mjs:112-126,149-165`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/app-ui.mjs:35-59`、`app/host/server/open-text-file.mjs:26-36`）。これらは外部プログラム向けの経路である。
- Harness 子プロセスでは、`externalEnvironment(base)` の結果から `KEEP` 正規表現に合う名前だけを残す。この正規表現は本変数に一致しないため、起動前環境に値があっても通常は除外される（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

## 実行時の詳細

`externalEnvironment()` は呼び出し時に環境オブジェクトをコピーし、静的キャッシュはしない。通常起動では呼び出し時点の `env` を使う。起動前環境の記録がある場合は `recordedOriginal()` が記録をデコードし、その時点の `process.env` にある同名値ではなく記録中の値を使う。ランチャーの記録は AppImage 起動時に作成されるため、その経路では Strata プロセス内で後から値を変更しても復元元は変わらない（`app/host/server/external-env.mjs:28-40,63-71`、`app/desktop/scripts/repack-appimage.sh:79-85`）。

外部起動先へは各呼び出し元が `externalEnvironment()` の返却値を `spawn` / `execFile` の `env` として渡す（例: `app/host/server/chat-files.mjs:89-94`、`app/host/server/folder-dialog.mjs:117-126`）。一方、Harness は返却値をさらに名前で絞ってから子プロセスに渡す（`app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。この変数を CLI 引数や別の Strata 設定へ変換する処理はない。

## ログと測定値

この変数の有無・値・除去を示す専用ログ、警告、終了コード分岐はない。外部起動のエラー処理は呼び出し先ごとに行われるが、本変数を原因として分類する処理は確認できない（`app/host/server/external-env.mjs:43-71`、`app/host/server/chat-files.mjs:89-95`、`app/host/server/app-ui.mjs:35-48`）。測定値は該当しない。

## 根拠

- `app/host/server/external-env.mjs:17-26,43-57,60-71` — 除去対象リスト、値を見ない削除処理、通常環境・記録環境の選択。
- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage 起動前の環境全体を記録する箇所。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — Harness 用の環境名フィルターと起動。
- `app/host/server/agent/agent-bridge.mjs:294-311` — Harness 起動時に渡す追加環境。
- `app/host/server/chat-files.mjs:85-95`、`app/host/server/folder-dialog.mjs:112-126,149-165`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/app-ui.mjs:35-59`、`app/host/server/open-text-file.mjs:26-36` — 外部プログラムに環境を渡す呼び出し経路。
