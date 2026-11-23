# `QML2_IMPORT_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のホストプロセスが外部プログラムへ渡す環境から、AppImage 内部のパスを除くためのパス一覧の一つとして扱う。通常の起動環境または AppImage 起動時に記録された元の環境では値を変更せず、AppImage 起動時の元環境の記録がない場合に限り、`APPDIR` 配下の要素を取り除く。QML の読み込み設定を Strata 自身が解釈したり、engine の動作を切り替えたりする実装ではない。対象名の参照は `external-env.mjs` の `PATH_LISTS` にある動的参照だけである（`app/host/server/external-env.mjs:26,43-57,64-71`）。

## 値と判定

値の文字列を真偽値や数値として parse しない。`externalEnvironment()` が環境オブジェクトを作るとき、`APPDIR` がある旧 AppImage 経路ではコロンで分割し、空要素と `APPDIR` 自身またはその下のパスを除く。それ以外の経路では値をそのまま保持する（`app/host/server/external-env.mjs:43-57,64-71`）。

| 条件 | 未設定 | 設定値の扱い | 空文字・除去後に要素が残らない場合 |
|---|---|---|---|
| AppImage ではない（`APPIMAGE` / `APPDIR` と記録がない） | 未設定のまま | 値を変更せずコピー | 空文字のままコピー |
| `STRATA_ORIGINAL_ENV` から元環境を復元できる | 復元元で未設定なら未設定 | 復元元の値をそのまま使う | 空文字もそのまま保持 |
| 元環境の記録がなく、`APPDIR` がある | 未設定のまま | `:` 区切りで空要素と `APPDIR` 配下の要素を除き、残りを順序どおり連結 | 変数を出力環境から削除 |
| 元環境の記録がなく、`APPDIR` はない（`APPIMAGE` のみ等） | 未設定のまま | 値を変更せずコピー | 空文字のままコピー |

旧 AppImage 経路での除去判定は文字列上の前方一致で、要素が `APPDIR` と等しいか、`APPDIR/` または `APPDIR//` で始まる場合に除去する。大文字小文字を変換したり、パスを正規化したり、区切り文字を検証したりはしない。たとえば `APPDIR=/opt/Strata` のとき `/opt/Strata/qml:/usr/share/qml` は `/usr/share/qml` となり、空文字や `/opt/Strata/qml` だけの値は出力環境から削除される（`app/host/server/external-env.mjs:45-55`）。

## 有効になる条件

- 外部プログラム向け環境の生成にだけ関係する。`externalEnvironment()` は AppImage でない通常起動では環境を変更せず、AppImage では `STRATA_ORIGINAL_ENV` を復元できればその元環境を優先する（`app/host/server/external-env.mjs:28-40,60-71`）。
- 元環境の記録を復元できず `APPDIR` が設定されている場合に、`PATH_LISTS` の他の変数と同じ除去処理を受ける。`APPIMAGE` が設定されていても `APPDIR` がなければパス要素の除去は行わない（`app/host/server/external-env.mjs:43-57,60-61`）。
- OS、GPU backend、build macro、CLI 引数、サーバーモード、モデル状態による追加分岐はない。実際に環境を生成する外部プログラム起動経路に入ったかと、`APPDIR` / `STRATA_ORIGINAL_ENV` の状態で処理が決まる（`app/host/server/external-env.mjs:43-71`）。
- フォルダ選択の `zenity` / `kdialog` / `gdbus`、ファイルや URL を開く外部プログラム、通知コマンドなどは、この環境を受け取る（`app/host/server/folder-dialog.mjs:117-126,153-154`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/app-ui.mjs:39-59`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/open-text-file.mjs:26-29`）。
- Harness の子プロセスでは、`externalEnvironment()` の結果をさらに `KEEP` の許可リストで絞るため、通常の親環境にある `QML2_IMPORT_PATH` は渡されない。`HarnessProcess` の `extraEnv` はこの絞り込みの後に追加される（`app/host/server/agent/harness-runtime.mjs:20-36,67-83`）。現行の生成元は `agent-bridge.mjs` の `profile.env` と一時停止ファイルの設定である（`app/host/server/agent/agent-bridge.mjs:303-305`）。

## 実行時の詳細

環境変数名そのもののリテラルは `PATH_LISTS` 配列に置かれ、旧 AppImage 経路で `for (const name of PATH_LISTS)` が `out[name]` を参照する。したがって、これは C++ engine の `getenv` などによる読み取りではなく、ホスト側 JavaScript の外部環境フィルターによる動的な読み取りである（`app/host/server/external-env.mjs:26,43-57`）。

関数は呼び出しごとに既定引数の `process.env` を参照し、結果をコピーして返す。値を static 変数などに保存するキャッシュはない。外部プログラムを起動する呼び出し元が、その時点で得た環境を子プロセス起動 API に渡すため、起動後に親環境を変更しても、すでに起動した子プロセスへは反映されない（`app/host/server/external-env.mjs:29,44,67-71`; `app/host/server/folder-dialog.mjs:118,124-126`; `app/host/server/chat-files.mjs:89-94`）。

`externalEnvironment(env, extra)` が `extra` を受け取った場合は最後にマージされ、同名の値を上書きする。ただし、確認した通常の呼び出し箇所では `extra` を渡していない。Harness では別の `agentEnvironment()` が許可リストを適用した後に `extra` を追加する（`app/host/server/external-env.mjs:64-71`; `app/host/server/agent/harness-runtime.mjs:26-36,80-83`）。

## ログと測定値

このフィルターは値を変更・削除しても、それ自体ではログや警告を出さず、終了もしない。外部プログラムの起動結果は各呼び出し元が処理する。たとえば Linux のフォルダ選択では、選択ツールと portal が使えなかった場合に unavailable と理由を返すが、`QML2_IMPORT_PATH` に結び付いた失敗判定ではない（`app/host/server/external-env.mjs:43-57`; `app/host/server/folder-dialog.mjs:123-145`）。該当する測定値はない。

## 根拠

- `app/host/server/external-env.mjs:15-26` — 元環境記録の変数名、AppImage 専用名、パス一覧。
- `app/host/server/external-env.mjs:28-40` — 元環境のデコードと未設定・空値を含む値の復元。
- `app/host/server/external-env.mjs:43-61` — `APPDIR` 配下のパス除去と AppImage 判定。
- `app/host/server/external-env.mjs:64-71` — 通常起動・記録環境・fallback の選択と `extra` の優先順位。
- `app/host/server/agent/harness-runtime.mjs:20-36,67-83` — Harness 子プロセスへ渡す環境の絞り込み。
- `app/host/server/folder-dialog.mjs:117-126,153-154`; `app/host/server/chat-files.mjs:89-94`; `app/host/server/app-ui.mjs:39-59`; `app/host/server/artifacts.mjs:5-6`; `app/host/server/open-text-file.mjs:26-29` — 外部プログラム起動時の環境利用。
