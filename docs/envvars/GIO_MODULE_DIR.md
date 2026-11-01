# `GIO_MODULE_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のホスト実装が `GIO_MODULE_DIR` の値を GTK/GIO の設定環境として解釈したり、モジュールをロードしたりはしません。Node.js の外部プログラム向け環境を組み立てる際、この名前を AppImage 専用変数として削除するか、元の起動環境から復元した環境に含めて子プロセスへ渡します。対象経路は Linux のフォルダ選択（zenity、kdialog、gdbus）、通知、外部プログラムによるファイル表示、エージェント起動などです。

## 値と判定

Strata は `GIO_MODULE_DIR` の値自体を parse、比較、正規化しません。値の扱いは環境オブジェクト全体を選ぶ分岐と、`GIO_MODULE_DIR` が含まれるかどうかで決まります。

| 状況 | 子プロセス用の扱い |
|---|---|
| AppImage 外で `APPIMAGE` / `APPDIR` がなく、`STRATA_ORIGINAL_ENV` もない | 元の環境を複製し、呼び出し元が渡した `extra` を後から適用する。`GIO_MODULE_DIR` は unset なら unset、空文字を含む設定値ならその値のまま。 |
| `STRATA_ORIGINAL_ENV` に有効な記録がある | Base64 を UTF-8 に変換し、NUL 区切りの `NAME=value` 項目から復元した元環境を使う。記録に `GIO_MODULE_DIR=` があれば空文字も保持され、記録になければ unset。 |
| AppImage 内で起動し、復元記録がない・空・復元可能な項目がない | AppImage 起動環境を清掃する。`GIO_MODULE_DIR` は `APPIMAGE_ONLY` に含まれるため、値や `APPDIR` の有無に関係なく削除される。 |
| 呼び出し元が `extra.GIO_MODULE_DIR` を渡す | `extra` が最後にマージされるので、それまでの分岐を上書きして渡す。確認した本番呼び出し箇所には、この名前を `extra` として明示設定するものはない。 |

記録の復元は各項目の最初の `=` で名前と値を分け、名前が空でない項目を採用します。したがって GIO 値の文字列内容・コロン区切り要素・大小文字・数値境界に対する判定はありません。記録全体の Base64 入力が不正でも Node の Buffer 変換が例外を投げない場合があり、Strata は復元された項目の有無だけで復元環境を使うか判断します（`apps/host/server/external-env.mjs:28-40,67-71`）。

## 有効になる条件

- `externalEnvironment()` を利用する子プロセス起動経路でだけ、この環境整形が適用されます。外部プログラムが値を読むことや、値がそのプログラム内で有効になる条件は Strata の調査対象外です。
- AppImage 起動時は `APPIMAGE` または `APPDIR` が truthy なら AppImage 内と判定されます。元環境記録が復元できれば元環境を採用し、復元できなければ AppImage 固有環境を除去します（`apps/host/server/external-env.mjs:43-70`）。
- `agentEnvironment()` は外部環境をさらに許可リストで絞り込みます。許可リスト `KEEP` に `GIO_MODULE_DIR` は含まれないため、エージェントとその shell tools の子プロセスには、元環境記録に値があっても渡りません（`apps/host/server/agent/harness-runtime.mjs:21-36,75-83`）。
- Windows と macOS のフォルダ選択経路は別実装であり、Linux 用 `externalEnvironment()` を使うフォルダ選択経路とは異なります（`apps/host/server/folder-dialog.mjs:76-99,110-120`）。他の利用箇所はプラットフォーム別分岐により呼ばれる範囲が変わります。

## 実行時の詳細

`external-env.mjs` は既定引数として呼び出し時点の `process.env` を受け取ります。モジュール読み込み時に `GIO_MODULE_DIR` の値を保存する cache はなく、関数を呼ぶたびに環境オブジェクトを参照します（`apps/host/server/external-env.mjs:28-30,43-71`）。

AppImage 用の記録がない場合、清掃処理はまず `APPIMAGE_ONLY` の各キーを無条件で削除します。この配列には `GIO_MODULE_DIR` が含まれます。さらに `PATH_LISTS` にも名前がありますが、先行する削除後には対象キーが残らないため、GIO 値をコロン分割して個別に残す処理は実際には行われません。別の GIO 系変数に対する AppImage パス除去の正規表現にも一致し得ますが、`GIO_MODULE_DIR` は先に消えています（`apps/host/server/external-env.mjs:17-26,43-57`）。

復元記録がある場合は、清掃せず復元した元環境を使います。AppImage 起動時の `GIO_MODULE_DIR` が Strata の AppImage 内パスであっても、復元記録の中身については Strata は削除・検査しません（`apps/host/server/external-env.mjs:28-40,67-71`）。

この関数はフォルダ選択で Linux の zenity / kdialog と gdbus に渡されます。フォルダ選択に失敗した場合、呼び出し側は候補を順に試し、最終的に選択 UI 不可の結果と入力案内を返しますが、その失敗を `GIO_MODULE_DIR` の値に結び付ける Strata の分岐やログはありません（`apps/host/server/folder-dialog.mjs:106-139,146-179`）。ほかに `xdg-open` 等の起動、テキストエディター探索、通知、プレビューの外部起動にも同じ環境整形が使われます（`apps/host/server/chat-files.mjs:89-95`; `apps/host/server/open-text-file.mjs:26-29`; `apps/host/server/app-ui.mjs:36-60`; `apps/host/server/artifacts.mjs:5-8`）。起動失敗時の一般的な処理は各呼び出し元によりますが、`GIO_MODULE_DIR` 固有の警告・終了・失敗経路は確認できませんでした。

## 根拠

- `apps/host/server/external-env.mjs:17-26` — AppImage 専用キーとパスリストに `GIO_MODULE_DIR` を列挙。
- `apps/host/server/external-env.mjs:28-40` — `STRATA_ORIGINAL_ENV` の Base64/NUL 区切り記録を復元。
- `apps/host/server/external-env.mjs:43-57` — AppImage 専用キーを削除し、他の設定値やパスリストを清掃。
- `apps/host/server/external-env.mjs:60-71` — AppImage 判定、通常環境・復元環境・清掃環境の選択、`extra` の優先。
- `apps/host/server/folder-dialog.mjs:110-120,146-157` — Linux フォルダ選択候補に整形済み環境を渡す。
- `apps/host/server/agent/harness-runtime.mjs:21-36,75-83` — エージェント環境の許可リストにより同名キーを除外。

`docs/envvars/000_envvers.md` に候補名がありますが、Strata 側で確認できた用途は値の直接的な機能制御ではなく、外部プロセス環境の引き継ぎ・除去です。外部ライブラリがこの変数で行う処理は本書では説明していません。
