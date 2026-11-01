# `GTK_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の host/server が外部プログラムへ渡す環境を作るとき、`GTK_PATH` を含めるかどうかを決めます。エンジンの GPU 計算や Strata 自身の GTK 設定を切り替える環境変数として読む箇所は見つかりませんでした。対象は Linux AppImage の影響を受ける外部プログラム向けの環境整理と、agent の shell/tool 向け環境です。

`externalEnvironment()` は AppImage 外では入力環境をそのまま複製します。AppImage 内、または `STRATA_ORIGINAL_ENV` がある場合は、起動元環境の記録が復元できればそれを使い、復元できなければ AppImage 固有値を取り除きます。後者では `GTK_PATH` を値にかかわらず削除します。呼び出し側が `extra` で明示した値は最後に追加されます。

## 値と判定

`GTK_PATH` 自体の文字列を parse したり、空文字・数値・真偽値として判定したりするコードはありません。判定は環境オブジェクトのコピー、キー削除、または元環境の復元です。

| 条件 | 外部プログラム用 `GTK_PATH` |
|---|---|
| `APPIMAGE` と `APPDIR` がなく、`STRATA_ORIGINAL_ENV` も falsy | 入力の値をそのまま複製。未設定なら未設定、空文字も空文字のまま |
| `STRATA_ORIGINAL_ENV` が base64 decode 後に空でない環境オブジェクトになる | 記録内に `GTK_PATH` があればその値を復元。空文字も値として復元し、記録にキーがなければ未設定 |
| AppImage 条件に入り、記録がない・復元結果が `null` | `GTK_PATH` を無条件で削除。未設定のまま |
| 上記いずれかで `externalEnvironment(env, extra)` に `extra.GTK_PATH` がある | `extra` の値が最後に追加される |

記録は `STRATA_ORIGINAL_ENV` の NUL 区切り `NAME=value` 列として decode されます。`recordedOriginal()` は値が空でも `GTK_PATH=` のキーを保持しますが、空の記録全体は `null` になります。AppImage fallback の `withoutAppImage()` は `GTK_PATH` を `APPIMAGE_ONLY` から先に削除します。そのため、同じファイルの `PATH_LISTS` にも `GTK_PATH` が列挙されていますが、fallback ではその後の path-list 分割処理に到達する値は残りません。

## 有効になる条件

- `externalEnvironment()` を使う外部プログラム起動経路が対象です。例は Linux の folder chooser（`zenity`、`kdialog`、`gdbus`）、`xdg-open` などの opener、desktop notification、artifact opener です。
- 環境の整理は `APPIMAGE` または `APPDIR` が truthy、あるいは `STRATA_ORIGINAL_ENV` が truthy のときに選ばれます。通常の AppImage 起動では launcher が元環境を記録し、コードコメントに記載された旧 AppImage では記録なしの削除処理を使います。
- `agentEnvironment()` は `externalEnvironment()` の結果をさらに `KEEP` whitelist で絞ります。`GTK_PATH` は whitelist に含まれないため通常の agent child env には渡りません。`extra` で明示した場合は戻り値の最後で追加されます。
- CUDA/HIP/SYCL backend、GPU 世代、モデル状態、CLI オプションによる分岐はありません。

## 実行時の詳細

AppImage repack script は `AppRun` に `env -0 | base64 -w0` を `STRATA_ORIGINAL_ENV` として記録します（`apps/desktop/scripts/repack-appimage.sh:56-58`）。host は外部プログラム起動ごとに `externalEnvironment()` を呼び、起動時に受け取った `process.env` または渡された env object のスナップショットから新しいオブジェクトを作ります。`GTK_PATH` の値を変更する処理や cache はありません。環境を受け取った子プロセスの起動後に親の環境が変わっても、既に渡した env object は再評価されません。

記録を復元できるときは記録された起動元環境を基礎にするため、AppImage 起動中の現在の `GTK_PATH` は参照せず、記録内の値があればそれを外部 child に渡します。fallback では `GTK_PATH` を含む `APPIMAGE_ONLY` の各キーを削除し、他の path list から AppImage 配下の要素を除去します。ただし `GTK_PATH` は先に丸ごと削除されるので、user 側の要素だけを残す分割処理は適用されません。

Strata は `GTK_PATH` の除去・復元を理由にログや警告を出しません。これらの関数に `GTK_PATH` 固有の終了・エラー経路もありません。子プログラムの起動結果は呼び出し側の通常のエラー処理に従います。たとえば folder chooser は候補の起動失敗を収集して次の chooser / portal を試し、利用できない場合に理由を返します（`apps/host/server/folder-dialog.mjs:110-139`）。

## 根拠

- `apps/host/server/external-env.mjs:17-26` — `GTK_PATH` を `APPIMAGE_ONLY` と `PATH_LISTS` に列挙。
- `apps/host/server/external-env.mjs:28-40` — 起動元環境記録の decode、空値を含む `NAME=value` の復元。
- `apps/host/server/external-env.mjs:43-57` — AppImage 固有キーの削除と path-list cleanup。
- `apps/host/server/external-env.mjs:60-70` — AppImage/record 条件、記録環境・fallback・`extra` の優先順。
- `apps/desktop/scripts/repack-appimage.sh:56-58` — AppImage 起動元環境を記録する launcher hook。
- `apps/host/server/folder-dialog.mjs:105-139,146-157` — chooser と portal への環境引き渡し。
- `apps/host/server/app-ui.mjs:38-59`, `apps/host/server/chat-files.mjs:89-94`, `apps/host/server/artifacts.mjs:5-6,26-30`, `apps/host/server/open-text-file.mjs:26-29` — opener、notification、artifact、system query の環境引き渡し。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-83` — agent env whitelist と明示 `extra`、Harness child 起動。
