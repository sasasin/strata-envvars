# `APPIMAGE_EXTRACT_AND_RUN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata がこの変数の値を設定として読み、機能を切り替える実装は見つからない。`app/host/server/external-env.mjs` の `APPIMAGE_ONLY` リストに名前があり、AppImage の実行環境から外部プログラム向け環境を作る fallback 経路で、その名前の項目を削除する（`app/host/server/external-env.mjs:17-24,43-57`）。従って Strata 側の作用は、特定条件下で外部プロセスへの環境引き継ぎからこの変数を除くこと。

この環境の組み立てはフォルダ選択、ブラウザやファイルの opener、デスクトップ通知、成果物を開く処理などで使われる（`app/host/server/folder-dialog.mjs:112-126,153-164`; `app/host/server/app-ui.mjs:39-47,56-60`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/open-text-file.mjs:26-29`）。値を読んで AppImage の起動方式を変える用途ではない。

## 値と判定

`withoutAppImage` は値の内容を比較・変換せず、`APPIMAGE_ONLY` の各名前を出力用コピーから `delete` する。したがってこの fallback 経路では、未設定、空文字、`0`、`1`、その他の文字列で結果に差はなく、子プロセス用環境には項目が残らない（`app/host/server/external-env.mjs:17-24,43-57`）。

| 条件 | unset | 設定時の扱い |
|---|---|---|
| `externalEnvironment` が AppImage 内または `STRATA_ORIGINAL_ENV` ありで呼ばれ、記録された元環境を復元できない | fallback 環境にも項目なし | 空文字・任意の値を問わず削除 |
| 同じ条件で元環境の記録を復元できる | 元環境に無ければ項目なし | 元環境に記録された値をそのまま含める |
| `APPIMAGE` と `APPDIR` がともに偽で、`STRATA_ORIGINAL_ENV` も偽 | 呼び出し元環境の状態を維持 | 呼び出し元環境の値をそのまま維持 |
| Harness の `agentEnvironment` で通常の親環境から子環境を作る | allowlist にも無いため含めない | `KEEP` allowlist に一致しないため含めない。`extra` として明示的に渡せば後段で追加される |

`recordedOriginal` は `STRATA_ORIGINAL_ENV` の truthy な値を Base64 として UTF-8 に復号し、NUL 区切りの `NAME=value` 項目から環境オブジェクトを作る。復号結果に項目がなければ `null` を返す。`externalEnvironment` は復元できた元環境を使い、復元できない場合は `withoutAppImage` の結果を使う。`extra` は最後にマージされる（`app/host/server/external-env.mjs:28-40,63-71`）。

## 有効になる条件

- `withoutAppImage` による除去が使われるのは、`APPIMAGE` または `APPDIR` が truthy、あるいは `STRATA_ORIGINAL_ENV` が truthy で `externalEnvironment` の復元処理に進み、元環境を復元できない場合。`APPIMAGE` / `APPDIR` の判定は値の文字列比較ではなく truthiness 判定（`app/host/server/external-env.mjs:60-70`）。
- launcher が作成した `STRATA_ORIGINAL_ENV` から元環境を復元できる場合、fallback 除去リストは使われず、元環境にこの名前があればその値を保持する。AppImage の repack スクリプトは起動時環境を `env -0 | base64 -w0` で記録する hook を追加する（`app/desktop/scripts/repack-appimage.sh:83-85`; `app/host/server/external-env.mjs:28-40,67-70`）。記録内にこの名前が含まれるかは、実際の起動時環境に依存する。
- AppImage 外で記録もない場合、`externalEnvironment` は環境をそのまま複製するため、この helper 単体では除去しない（`app/host/server/external-env.mjs:63-70`）。
- Harness 子プロセス向けの `agentEnvironment` は環境名の allowlist を適用し、この変数を通常は通さない。`HarnessProcess.start` から `extra` として明示的に渡された項目は最後にマージされるため、その場合は追加される（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。
- 対象ソースには OS / backend / build macro / CLI による値の解釈分岐はない。外部プログラムがこの変数をどう使うかは Strata の実装範囲外。

## 実行時の詳細

`externalEnvironment` の既定引数は呼び出し時点の `process.env`。結果は呼び出しごとに新しいオブジェクトとして作られ、対象変数を保存する専用 cache はない。実行中に親プロセスの環境オブジェクトが変更され、その後 helper が再度呼ばれれば、その時点の値を入力として扱う（`app/host/server/external-env.mjs:29,44,60,67-71`）。

launcher の記録がない AppImage 経路では、`externalEnvironment` が作った環境が各外部コマンドの `env` オプションに渡される。例として Linux の folder chooser は `zenity`、`kdialog`、`gdbus` に同じ環境を渡し、`chat-files.mjs` は opener に渡す（`app/host/server/folder-dialog.mjs:117-126,135-164`; `app/host/server/chat-files.mjs:89-94`）。この経路では `APPIMAGE_EXTRACT_AND_RUN` の値自体は Strata の分岐やコマンド引数に使われない。

## 根拠

- `app/host/server/external-env.mjs:17-24,43-57` — 除外名リストと値を見ずにプロパティを削除する fallback。
- `app/host/server/external-env.mjs:28-40,60-71` — 元環境の復元、AppImage 判定、経路選択、`extra` の優先。
- `app/desktop/scripts/repack-appimage.sh:83-85` — launcher が元の起動環境を記録する hook。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — Harness 用 allowlist と明示 extra の追加。
- `app/host/server/folder-dialog.mjs:112-126,153-164`; `app/host/server/app-ui.mjs:39-47,56-60`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/open-text-file.mjs:26-29` — helper が使われる外部プロセス経路。
