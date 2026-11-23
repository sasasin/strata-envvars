# `PERLLIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のホストサーバーは、外部プログラムに渡す環境から AppImage 内のディレクトリを指すパス項目を取り除く際、`PERLLIB` もコロン区切りパス一覧として扱う。対象は Perl 用検索パスの調整ではなく、AppImage の環境が外部プログラムに漏れないようにする共通処理である。AppImage の元環境記録が使える場合は元環境を復元するため、その元環境にある `PERLLIB` は保たれる。通常の非 AppImage 実行ではこの変数を変更しない。`withoutAppImage` と `externalEnvironment` の処理は [`app/host/server/external-env.mjs:26-70`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/external-env.mjs:26) にある。

## 値と判定

`PERLLIB` 自体を `process.env.PERLLIB` のように直接参照する箇所はなく、`PATH_LISTS` の名前を使って環境オブジェクトから値を取り出す。`withoutAppImage` は値が文字列の場合だけコロン (`:`) で分割し、空要素と `APPDIR` 内を指す要素を除去する。残りがあればコロンで結合して保持し、空なら変数ごと削除する。値の真偽、Perl パスとしての妥当性、大小文字を検証せず、空白も trim しない。整数変換や数値境界はない。[`app/host/server/external-env.mjs:26,43-57`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/external-env.mjs:26)

| 実行時の条件 | 未設定 | 設定時の扱い | 例 |
|---|---|---|---|
| `externalEnvironment` が通常の環境で呼ばれ、`APPIMAGE` / `APPDIR` も `STRATA_ORIGINAL_ENV` もない | 未設定のまま | 変更せず子環境へコピー | `PERLLIB=/usr/lib/perl5` はそのまま |
| `withoutAppImage` により環境を掃除し、`APPDIR` がある | 変数なし | `:` で分割し、空要素と `APPDIR` またはその下のパスを除く | `/usr/lib/perl5:/tmp/app/usr/lib/perl5` → `/usr/lib/perl5`。`/tmp/app` が `APPDIR` の場合 |
| `withoutAppImage` により環境を掃除し、`APPDIR` がない | 変数なし | 空要素を除き、それ以外は保持 | `:/usr/lib/perl5::` → `/usr/lib/perl5` |
| `STRATA_ORIGINAL_ENV` から非空の環境オブジェクトを復元できる場合 | 元環境で未設定なら未設定 | 記録した起動元の値を復元し、`PERLLIB` の再フィルタはしない | 元値 `:/usr/lib/perl5` は記録のまま保持 |

フィルタ後の値が空ならキーを削除するため、明示的な空文字は掃除経路では子環境に残らない。`externalEnvironment` の `extra` 引数に `PERLLIB` を渡した場合は、後からマージされるためフィルタ結果を上書きできる。[`app/host/server/external-env.mjs:43-57,67-70`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/external-env.mjs:43)

## 有効になる条件

- 非 AppImage 実行で `APPIMAGE`、`APPDIR`、`STRATA_ORIGINAL_ENV` がいずれもない場合は `withoutAppImage` を通らず、`PERLLIB` を含む環境コピーがそのまま返る。[`app/host/server/external-env.mjs:60-70`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/external-env.mjs:60)
- AppImage 関連の環境で、`STRATA_ORIGINAL_ENV` から空でない環境オブジェクトを復元できれば、その記録が掃除後の現在環境より優先される。AppImage の `AppRun` に起動元の `env -0` を Base64 化して記録する処理がある。[`app/host/server/external-env.mjs:28-40,67-70`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/external-env.mjs:28)、[`app/desktop/scripts/repack-appimage.sh:79-85`](/home/sasasin/src/github.com/Niko1221/Strata/app/desktop/scripts/repack-appimage.sh:79)
- 有効な記録がない場合は `withoutAppImage` に進む。`APPDIR` があればそのディレクトリとその配下（`APPDIR/` または `APPDIR//` で始まる文字列）を除き、`APPDIR` が空なら空要素だけを除く。[`app/host/server/external-env.mjs:43-57,67-70`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/external-env.mjs:43)
- 外部プログラムを起動する複数のホスト機能がこの環境を使う。例として、フォルダー選択、ブラウザー起動、通知、ファイルを開く処理がある。[`app/host/server/folder-dialog.mjs:117-126,153-164`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/folder-dialog.mjs:117)、[`app/host/server/app-ui.mjs:39-47,57-60`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/app-ui.mjs:39)、[`app/host/server/open-text-file.mjs:26-29,89-94`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/open-text-file.mjs:26)
- エージェント用環境では `externalEnvironment` の結果をさらに `KEEP` の許可リストで絞る。`PERLLIB` はこの許可リストに含まれないため、外部プロセス用環境に残っていてもエージェント環境には渡されない。[`app/host/server/agent/harness-runtime.mjs:22-36`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/agent/harness-runtime.mjs:22)

## 実行時の詳細

`externalEnvironment` は呼び出し時の `process.env` を既定引数として受け取る。AppImage で起動し、元環境記録があればそれをデコードし、ない場合は現在環境から AppImage 専用変数やパス要素を除く。呼び出しごとに新しいオブジェクトを作り、`PERLLIB` の値を static cache しない。`extra` は最後にマージされる。AppImage の元環境記録は `env -0 | base64 -w0` で作成され、Node 側で NUL 区切りの `NAME=value` 項目として復元される。[`app/host/server/external-env.mjs:28-57,67-70`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/external-env.mjs:28)、[`app/desktop/scripts/repack-appimage.sh:79-85`](/home/sasasin/src/github.com/Niko1221/Strata/app/desktop/scripts/repack-appimage.sh:79)

このフィルタは子プロセス用環境オブジェクトを変えるだけで、Strata プロセス自身の `process.env.PERLLIB` を書き換えない。コード上、CLI 引数、モデル状態、GPU backend、build macro による `PERLLIB` の判定はない。[`app/host/server/external-env.mjs:43-70`](/home/sasasin/src/github.com/Niko1221/Strata/app/host/server/external-env.mjs:43)

## ログと測定値

`PERLLIB` のフィルタや復元に固有のログ・警告・終了経路はない。影響は前述の外部プロセスに渡る環境の内容に現れる。測定値の記載はない。

## 根拠

- `app/host/server/external-env.mjs:26` — `PERLLIB` を含むパス一覧。
- `app/host/server/external-env.mjs:28-40` — 元環境記録の取得とデコード。
- `app/host/server/external-env.mjs:43-57` — `APPDIR` 配下および空要素の除去。
- `app/host/server/external-env.mjs:60-70` — AppImage 判定、元環境と掃除環境の選択、`extra` の優先。
- `app/desktop/scripts/repack-appimage.sh:79-85` — 起動元環境を AppImage に記録する処理。
- `app/host/server/agent/harness-runtime.mjs:22-36` — エージェント環境の許可リスト。
