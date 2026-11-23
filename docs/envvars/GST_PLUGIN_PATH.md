# `GST_PLUGIN_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 本体が GStreamer の設定として値を解釈するコードは確認できない。ホスト側の `external-env.mjs` がこの名前をパス一覧変数として扱い、外部プログラムへ渡す環境を作るときに値をそのまま残すか、AppImage 内部を指すパスを取り除く。これは GStreamer のプラグイン探索を Strata が制御する設定ではない。対象名の唯一の直接参照は `app/host/server/external-env.mjs:26` にある。

## 値と判定

数値や真偽値としての parse はない。`withoutAppImage` は `GST_PLUGIN_PATH` が文字列かだけを調べ、AppImage の一時マウント先を除く必要がある場合に限り `:` 区切りで処理する。外部プログラム用環境は次の条件で分岐する（`app/host/server/external-env.mjs:43-57,60-70`）。

| 条件 | unset | 設定値の扱い | 空文字・無効値 |
|---|---|---|---|
| `APPIMAGE` / `APPDIR` がなく、`STRATA_ORIGINAL_ENV` も falsy | そのまま未設定 | 外部環境のコピーに値をそのまま含める | 空文字もそのまま含む。値の文法検証なし |
| `STRATA_ORIGINAL_ENV` を base64 decode して得た起動時環境に値がある | 起動時環境でも未設定なら未設定 | 起動時の値をそのまま使う。現在の AppImage 内環境から再加工しない | 文字列の解釈・妥当性検証なし |
| `APPDIR` があり、有効な起動時環境レコードがない | 未設定のまま | 値に `APPDIR` の文字列が含まれる場合は変数全体を削除。そうでなければ `:` 分割し、空要素と `APPDIR` 自身または `APPDIR/…`（`APPDIR//…` を含む）を除いて再結合。要素が残らなければ変数を削除 | 空文字は分割後に要素が残らず削除。区切りの連続による空要素も削除 |
| `APPIMAGE` はあるが `APPDIR` がなく、有効な起動時環境レコードもない | そのまま未設定 | `APPDIR` による除去処理が走らないため、設定値を保持 | 空文字を含めて保持 |

ここでいう有効な起動時環境レコードは、`STRATA_ORIGINAL_ENV` を base64 decode し、NUL 区切りの各項目から `NAME=value` を読み取って空でないオブジェクトができることを指す。デコード例外または有効項目なしでは `null` となり、`APPDIR` があれば上表の除去処理へ進む（`app/host/server/external-env.mjs:28-40,67-70`）。値はパス要素の全体を parse せず、`APPDIR` が値のどこかに部分文字列として含まれるだけでも、最初の判定で変数全体を削除する。

## 有効になる条件

- Strata ホストが `externalEnvironment()` を通して外部プログラム用環境を作る経路で参照される。直接の呼び出し元には、Linux のフォルダ選択（`zenity`、`kdialog`、`gdbus`）、ブラウザー・通知・ファイル起動、成果物を開く処理がある（`app/host/server/folder-dialog.mjs:112-126,135-164`、`app/host/server/app-ui.mjs:39-60`、`app/host/server/chat-files.mjs:85-94`、`app/host/server/open-text-file.mjs:26-29`、`app/host/server/artifacts.mjs:5-6`）。
- 外部プログラムへ実際に渡る値は `externalEnvironment` の上記分岐による。子 Harness 向けはその後 `KEEP` の許可リストで環境変数を絞るため、`GST_PLUGIN_PATH` は許可されず渡らない（`app/host/server/agent/harness-runtime.mjs:20-36`）。
- OS や GPU backend、CLI 引数による値の有効化条件はない。このコードの対象はホスト側の外部プログラム起動であり、エンジンの CUDA/HIP/SYCL 経路ではない。

## 実行時の詳細

環境は `externalEnvironment(env = process.env, extra = {})` の呼び出し時に組み立てられ、値の結果を保持する cache はない。既定引数の `process.env` は呼び出し時に渡される。起動時環境レコードが採用される場合は、その中の `GST_PLUGIN_PATH` が現在のホスト環境より優先され、`extra` があれば最後に上書きする（`app/host/server/external-env.mjs:28-40,63-70`）。

`withoutAppImage` ではまず、値に `APPDIR` が含まれている GST 系文字列を削除し、その後 `PATH_LISTS` にある文字列を `:` で分割してマウント内の要素を除去する。`GST_PLUGIN_PATH` は `PATH_LISTS` に含まれ、AppImage 専用変数一覧 `APPIMAGE_ONLY` には含まれない（`app/host/server/external-env.mjs:17-26,43-57`）。したがって `APPDIR` を含まない外部パス要素は残るが、Strata はその要素を検査・ロードせず、その先の外部プログラムに環境として渡す。

## ログと測定値

この変数の値を処理したことを示すログ、警告、終了・失敗経路は `external-env.mjs` にない。外部プログラム起動の成否は個々の呼び出し元で別途扱うが、`GST_PLUGIN_PATH` の内容に結び付いたメッセージや測定値は確認できない。

## 根拠

- `app/host/server/external-env.mjs:17-26,43-57,60-70` — AppImage 専用変数、パス一覧、値の除去・保持と分岐。
- `app/host/server/folder-dialog.mjs:112-146,153-166` — フォルダ選択コマンドへ環境を渡す経路。
- `app/host/server/app-ui.mjs:39-60`、`app/host/server/chat-files.mjs:85-94`、`app/host/server/open-text-file.mjs:26-29`、`app/host/server/artifacts.mjs:5-6` — 他の外部プログラム呼び出し。
- `app/host/server/agent/harness-runtime.mjs:20-36` — Harness 環境の許可リストに `GST_PLUGIN_PATH` が含まれないこと。
- `app/desktop/scripts/repack-appimage.sh:83-85` — パッケージ起動時環境を `STRATA_ORIGINAL_ENV` に記録する処理。
