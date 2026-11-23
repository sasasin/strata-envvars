# `GTK_IM_MODULE_FILE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 自身の機能や GTK 設定値としては読み取られない。Node 側の `external-env.mjs` が、AppImage 自身用に設定された環境変数を Strata 外のプログラムへ渡さないための除外対象名 `APPIMAGE_ONLY` に `GTK_IM_MODULE_FILE` を列挙している。したがって、この値の内容に応じて Strata 内の処理や GTK の動作を切り替える分岐はない。起動元の環境を記録した `STRATA_ORIGINAL_ENV` が使える場合は記録された値を復元して渡す。`app/host/server/external-env.mjs:17-24,28-40,43-57`。

## 値と判定

値の文字列、空文字、大小文字、数値形式は判定されない。Strata はこの名前をキーとして扱う。

| 条件 | unset | 設定時の扱い |
|---|---|---|
| AppImage 外かつ `STRATA_ORIGINAL_ENV` なし | そのまま環境コピーに存在しない | 値を変更せず外部プロセス用環境へコピーする |
| `STRATA_ORIGINAL_ENV` が有効な記録を持つ | 記録に含まれなければ存在しない | 記録された起動元環境の値をそのまま返す |
| AppImage 内で記録がない、または記録を復元できない | 存在しない | `withoutAppImage` が値を調べずキーを削除する |

`externalEnvironment` は AppImage 外かつ記録なしなら入力環境をコピーし、そうでなければ記録済み環境を復元し、復元できない場合に限って `withoutAppImage` の除去済み環境へフォールバックする。`app/host/server/external-env.mjs:28-40,43-57,60-70`。

## 有効になる条件

- この名前が環境伝播に影響するのは `externalEnvironment` を使って外部プログラムを起動する経路に限られる。AppImage 内で有効な `STRATA_ORIGINAL_ENV` があれば、その記録に含まれる起動元の値が渡される。記録がない／復元不能なら本変数は除外される。`app/host/server/external-env.mjs:28-40,67-70`。
- 記録なしのフォールバックでは、AppImage 判定に加えて `APPDIR` の有無や値に関係なく `APPIMAGE_ONLY` の名前一致で削除される。`app/host/server/external-env.mjs:18-24,43-50,60-70`。
- 対象となる呼び出し先には、ファイル選択ダイアログ、URL opener、通知、外部ファイル起動がある。Linux フォルダー選択は同じ環境を `zenity`、`kdialog`、portal 呼び出しへ渡す。`app/host/server/folder-dialog.mjs:112-126,135-136`; `app/host/server/app-ui.mjs:39-59`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/open-text-file.mjs:28`; `app/host/server/artifacts.mjs:6`。
- Harness のエージェント環境は `externalEnvironment(base)` の結果をさらに `KEEP` の許可リストで絞るため、この GTK 名は元環境にあっても子エージェントの環境には含まれない。`app/host/server/agent/harness-runtime.mjs:20-36`。
- Strata の engine 起動や通常の推論設定に本変数を適用するコードは確認できない。`app/host/server/external-env.mjs:1-9` は対象を Strata 外のプログラムと説明しており、実装上も外部プロセス用環境の組み立てに使われる。

## 実行時の詳細

デフォルトでは関数呼び出し時の `process.env` を入力として参照し、`externalEnvironment` 自体にキャッシュはない。明示的な `env` を引数に渡す呼び出しでは、そのオブジェクトを処理する。launcher が `STRATA_ORIGINAL_ENV` を設定する実装は AppImage 再梱包スクリプトにあり、起動元環境全体を NUL 区切りで base64 化して記録する。`app/host/server/external-env.mjs:28-40,60-70`; `app/desktop/scripts/repack-appimage.sh:79-85`。

有効な記録が選ばれる場合、復元処理は全キーをオブジェクトに戻すため、本変数が記録にあれば値は保持される。記録を使えない経路では、コピーを作った後 `APPIMAGE_ONLY` のキーを削除する。追加の環境オブジェクト `extra` は最後にマージされる設計だが、確認した本番呼び出しはこの関数を追加値なしで使用している。`app/host/server/external-env.mjs:33-39,46-48,64-70`; `app/host/server/chat-files.mjs:92`; `app/host/server/folder-dialog.mjs:118`。

## 根拠

- `app/host/server/external-env.mjs:17-24` — `GTK_IM_MODULE_FILE` を含む AppImage 専用の除外名一覧。
- `app/host/server/external-env.mjs:28-40,43-57,60-70` — 起動元環境の復元、復元失敗時のキー削除、AppImage 外のコピーという分岐。
- `app/host/server/folder-dialog.mjs:112-126,135-136`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/app-ui.mjs:39-59`; `app/host/server/open-text-file.mjs:28`; `app/host/server/artifacts.mjs:6` — 外部プログラムに用意した環境を渡す呼び出し箇所。
- `app/host/server/agent/harness-runtime.mjs:20-36` — 外部環境をさらに許可リストで絞るエージェント起動経路。
- `app/desktop/scripts/repack-appimage.sh:79-85` — AppImage 起動元環境を `STRATA_ORIGINAL_ENV` に記録する処理。
