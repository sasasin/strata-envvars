# `GST_REGISTRY_REUSE_PLUGIN_SCANNER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata はこの変数の値を設定値として解釈しない。Node の `external-env.mjs` で AppImage 専用環境変数の一覧に含め、起動元環境の記録を復元できないときに `withoutAppImage()` が外部プログラムへ渡す環境コピーからキーを削除する（`app/host/server/external-env.mjs:17-24,43-57,63-71`）。対象はフォルダ選択、ファイル・URL を開く処理、通知、エージェント用プロセスなど `externalEnvironment()` を使う呼び出し経路である（例: `app/host/server/folder-dialog.mjs:112-123`, `app/host/server/chat-files.mjs:85-95`, `app/host/server/app-ui.mjs:35-60`, `app/host/server/agent/harness-runtime.mjs:25-33`）。

この処理は外部プログラムへ渡す環境の調整であり、Strata 自身の起動環境から値を削除したり、Strata のエンジン設定を変えたりはしない（`app/host/server/external-env.mjs:44-57,67-71`）。

## 値と判定

この名前の値は読み出しも parse も比較もされず、`APPIMAGE_ONLY` のリテラルなキーとして処理される。したがって、値が `1`、`0`、`true`、`false`、空文字、その他の文字列のいずれでも、このキー単独では挙動に違いがない。数値・大文字小文字・空白の検証や値による fallback はない。差が生じるのは環境の選択経路である（`app/host/server/external-env.mjs:17-24,29-40,43-57,60-71`）。

| `externalEnvironment()` の条件 | 対象キーの扱い |
|---|---|
| `APPIMAGE` と `APPDIR` がなく、`STRATA_ORIGINAL_ENV` も空または未設定 | `env` のコピーをそのまま返すため、設定されていれば値も保持する（`app/host/server/external-env.mjs:60-68`）。 |
| AppImage 内、または `STRATA_ORIGINAL_ENV` が truthy で、記録を復元できる | 復元した起動元環境を返す。記録に対象キーが含まれていればその値を保持する。記録が空の文字列なら `recordedOriginal()` は null を返す（`app/host/server/external-env.mjs:28-40,67-71`）。 |
| AppImage 内で記録を復元できない | `withoutAppImage()` がコピーから対象キーを無条件に削除する。対象キーが未設定でも追加はしない（`app/host/server/external-env.mjs:43-57,67-71`）。 |

記録復元の成否は `STRATA_ORIGINAL_ENV` の base64 デコード結果から作られた環境オブジェクトが空かどうかで決まる。この変数の値自体を有効・無効と判定する処理はない（`app/host/server/external-env.mjs:28-40`）。

## 有効になる条件

- キー削除が発生するのは `externalEnvironment()` が `withoutAppImage()` を選ぶ場合だけ。AppImage 内で `STRATA_ORIGINAL_ENV` が有効な起動元環境を復元できる場合は、その環境が使われ、対象キーを個別に削除しない（`app/host/server/external-env.mjs:60-71`）。
- AppImage 外で `APPIMAGE` / `APPDIR` がなく、記録も truthy でなければ環境はそのままコピーされる（`app/host/server/external-env.mjs:60-68`）。
- `agentEnvironment()` は `externalEnvironment()` の結果を `KEEP` の名前許可リストで絞るため、元環境にあったこのキーは許可リストに一致せず除外される。ただし関数の `extra` は最後にマージされるため、呼び出し側が `extra` に明示すれば再追加できる（`app/host/server/agent/harness-runtime.mjs:20-33,36`）。
- `extra` 引数は基底環境の後からマージされるため、呼び出し側が同じ名前を明示的に `extra` で渡せば上書き・再追加できる設計だが、確認した本番呼び出し箇所ではこの名前を `extra` に渡していない（`app/host/server/external-env.mjs:63-71`; 呼び出し箇所は `app/host/server/chat-files.mjs:92`, `app/host/server/app-ui.mjs:39,57`, `app/host/server/folder-dialog.mjs:118,153`, `app/host/server/artifacts.mjs:6`, `app/host/server/open-text-file.mjs:28`, `app/host/server/agent/harness-runtime.mjs:30`）。

## 実行時の詳細

`externalEnvironment(env = process.env, extra = {})` が呼ばれるたびに分岐・環境コピーを作る。対象キー用の static cache や値の読み取りキャッシュはない。既定引数は呼び出し時点の `process.env` である（`app/host/server/external-env.mjs:29,44,60-71`）。通常の AppImage 起動ではランチャーが AppImage のフックを適用する前に環境を `env -0 | base64 -w0` で `STRATA_ORIGINAL_ENV` に記録する（`app/desktop/scripts/repack-appimage.sh:79-85`）。この記録が復元されれば Strata は起動元環境を外部プログラム用に返す。記録がない・復元できない AppImage 環境では AppImage 内で設定された値を含めて対象キーを削除する（`app/host/server/external-env.mjs:11-13,28-40,43-57,67-71`）。

## ログと結果

このキーの削除・保持について `external-env.mjs` はログを出さない（`app/host/server/external-env.mjs:43-57,63-71`）。フォールバック清掃経路では、対象キーは子プロセスに渡す環境オブジェクトからなくなる。復元経路や AppImage 外の通常経路では、元の環境にキーがあればその値が引き継がれる。対象変数を理由にした終了・エラー処理はない。

## 根拠

- 対象名の登録と値を取らずに削除する処理: `app/host/server/external-env.mjs:17-24,43-57`
- 環境選択・記録復元・追加値の優先順: `app/host/server/external-env.mjs:28-40,60-71`
- AppImage ランチャーによる起動元環境の記録: `app/desktop/scripts/repack-appimage.sh:79-85`
- 外部プログラムへの環境適用例: `app/host/server/chat-files.mjs:85-95`, `app/host/server/folder-dialog.mjs:112-123`, `app/host/server/app-ui.mjs:35-60`, `app/host/server/agent/harness-runtime.mjs:25-33`
