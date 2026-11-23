# `GST_PLUGIN_SCANNER_1_0`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata はこの名前の値を機能設定として読み取っていません。Linux AppImage から起動した Strata が外部プログラムに渡す環境を整える際、旧形式 AppImage の環境からこのキーを削除します。ランチャーが記録した起動元環境を復元できる場合は、その記録中にこのキーがあれば値をそのまま引き継ぎます。したがって、Strata 内部の GST 動作やプラグインスキャナーを制御する環境変数ではなく、外部プログラム用の環境の整理対象です（`app/host/server/external-env.mjs:17-23,43-57,64-70`）。

この環境処理はフォルダ選択、ブラウザー・ファイル起動、デスクトップ通知、成果物を開く処理、およびエージェントの shell/tool 起動で共用されています（`app/host/server/folder-dialog.mjs:112-126,153-164`、`app/host/server/app-ui.mjs:39-47,57-60`、`app/host/server/chat-files.mjs:89-94`、`app/host/server/open-text-file.mjs:26-29`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/agent/harness-runtime.mjs:28-30`）。ただし、このキーが除外リストどおりに残る可能性があるのは、helper の返却環境をそのまま子プロセスへ渡す経路です。エージェント用環境は helper の後に許可名だけへ絞られ、この名前は許可されないためエージェントには渡りません（`app/host/server/agent/harness-runtime.mjs:20-36`）。

## 値と判定

Strata は `GST_PLUGIN_SCANNER_1_0` の値を直接取得、比較、変換しません。`APPIMAGE_ONLY` の名前一覧に含め、旧形式 AppImage 用のコピー環境からキー自体を `delete` します。よって値の内容、大文字小文字、空白、数値形式による判定や fallback はありません（`app/host/server/external-env.mjs:17-23,43-57`）。

| 条件 | unset | 設定時の扱い |
|---|---|---|
| AppImage 外で `APPIMAGE`・`APPDIR`・`STRATA_ORIGINAL_ENV` がいずれも truthy でない | そのまま未設定 | 空文字を含め、元の `env` の値をそのまま返す |
| `STRATA_ORIGINAL_ENV` の記録を復元できる | 記録環境にもキーがなければ未設定 | 記録環境にある値を内容にかかわらずそのまま返す。空値も保持される |
| `APPIMAGE` / `APPDIR` が truthy、または `STRATA_ORIGINAL_ENV` が truthy で、記録を復元できない | コピーにもキーなし | `withoutAppImage` が値の内容にかかわらずキーを削除する |

記録は `STRATA_ORIGINAL_ENV` の truthy 判定後、Base64 decode した NUL 区切り `NAME=value` 項目から復元されます。`=` より前に名前がある項目を採用し、値は `=` の後ろ全体です。復元結果が空なら記録なしとして扱います（`app/host/server/external-env.mjs:28-40,67-70`）。

## 有効になる条件

- `APPIMAGE` または `APPDIR` が truthy、あるいは `STRATA_ORIGINAL_ENV` が truthy のときに限り、通常の `env` をそのまま返さず外部プログラム向けの環境を組み立てます（`app/host/server/external-env.mjs:60-70`）。ソースにはこの分岐の OS 判定はありません。
- `STRATA_ORIGINAL_ENV` から元の環境を復元できればそちらを使い、このキーも記録どおりに保持または省略します。記録がなければ `withoutAppImage` を使い、このキーを常に削除します。helper の分岐自体に OS 判定はなく、truthy な記録が不正な場合は AppImage 判定の有無にかかわらず後者になります（`app/host/server/external-env.mjs:28-40,43-57,67-70`）。
- `externalEnvironment` の `extra` 引数は環境再構成後に加算されるため、呼び出し側が同名キーを明示すれば上書きできます。ただし本 checkout 内の呼び出しは引数なし、または `env` のみを渡しており、同名キーの `extra` 上書きはありません（`app/host/server/external-env.mjs:64-70` と同 helper の呼び出し箇所）。
- エージェント用の `agentEnvironment` は `KEEP` 正規表現で名前を絞るため、このキーを通しません（`app/host/server/agent/harness-runtime.mjs:20-36`）。
- Strata の engine、Node、Python など同梱プログラムはこの外部環境 helper の対象ではありません（`app/host/server/external-env.mjs:2-9`）。

## 実行時の詳細

`externalEnvironment(env = process.env, extra = {})` の呼び出し時点で入力オブジェクトを読みます。既定引数の `process.env` をプロセス起動時に cache する処理や、このキー専用のキャッシュはありません。旧形式経路ではオブジェクトを shallow copy し、キー一覧を走査して削除します。記録環境の経路では記録文字列をその呼び出し時に decode します（`app/host/server/external-env.mjs:28-57,64-70`）。

呼び出し元は、生成した環境オブジェクトを `spawn` / `execFile` の `env` に渡します。たとえば Linux の folder chooser は一度作った `env` を zenity、kdialog、gdbus に渡します（`app/host/server/folder-dialog.mjs:117-126,135-164`）。エージェント runtime も helper の結果を使いますが、後段の `KEEP` フィルターでこの名前を除きます（`app/host/server/agent/harness-runtime.mjs:20-36`）。Strata はこのキーを理由に警告、ログ、終了、fallback を発生させません。

## 根拠

- `app/host/server/external-env.mjs:17-23,43-57,60-70` — 除外リスト、キー削除、AppImage 判定、記録環境との選択。
- `app/host/server/external-env.mjs:28-40` — 起動元環境記録の decode と項目の復元。
- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage 起動時に `STRATA_ORIGINAL_ENV` を記録する hook の追加。
- `app/host/server/folder-dialog.mjs:112-126,153-164`、`app/host/server/app-ui.mjs:39-47,57-60`、`app/host/server/chat-files.mjs:89-94`、`app/host/server/open-text-file.mjs:26-29`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/agent/harness-runtime.mjs:28-30` — helper の実行時利用先。
