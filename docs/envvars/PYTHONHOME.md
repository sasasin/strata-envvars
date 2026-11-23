# `PYTHONHOME`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `PYTHONHOME` を設定値として読み取って分岐したり、値を解析したりしない。確認できる用途は、Strata 同梱 Python や Control の子プロセスにユーザー環境の値を渡さないことと、AppImage から起動された外部プログラムの環境を組み立てるときに元の環境値を復元または AppImage 内のパスだけ除くこと。したがって値によって Strata のモデル、backend、CLI の選択が変わる設定ではない（例: `terminal/bin/strata:142-145`、`app/host/server/control-runtime.mjs:88-107`、`app/host/server/external-env.mjs:26,43-57,64-71`）。

## 値と判定

値の文字列を比較・変換する読み取り箇所はない。削除処理は値の内容にかかわらずキー名で行う。従って空文字、`0`、`1`、`true`、任意のパスなどに Strata 固有の有効・無効判定はない。

| 処理経路 | unset / 空文字 | 任意の非空値 | 条件・結果 |
|---|---|---|---|
| 同梱 Python を使う Terminal ランチャー | unset のまま / `set "PYTHONHOME="` または `unset` で子プロセス環境から除去 | 同じく値を除去 | Unix shell、Windows `cmd.exe`、PowerShell で bundled runtime を選んだ分岐のみ（`terminal/bin/strata:142-145`、`terminal/bin/strata.cmd:34-40`、`terminal/bin/strata-direct.ps1:36-41`） |
| Desktop の Control 起動・診断 | `Command` の子環境からキーを除去 | 値を見ず除去 | `control_runs` と `control_engine_notice` が同梱 interpreter を起動する際（`app/desktop/src-tauri/src/main.rs:688-716`） |
| Host の Control 子プロセス | コピーした環境からキーを除去 | 値を見ず除去 | `controlEnvironment` の利用者が Control を起動する際（`app/host/server/control-runtime.mjs:88-107,140-146`） |
| AppImage の外部プログラム環境 | 元の記録があれば元の値を復元し得る。古い AppImage の fallback では空要素を除去 | 記録があれば記録中の値を採用。fallback では `APPDIR` 内を指す path 要素だけ除去し、残りがなければキーごと除去 | AppImage 起動時または `STRATA_ORIGINAL_ENV` がある場合（`app/host/server/external-env.mjs:28-40,43-57,60-71`） |
| App の agent 子環境 | 出力環境には含めない | 出力環境には含めない | `agentEnvironment` の許可名 `KEEP` に `PYTHONHOME` が含まれないため（`app/host/server/agent/harness-runtime.mjs:20-36`） |

他の環境変数や CLI 引数との優先順位はない。AppImage の外部環境経路だけは `APPIMAGE` / `APPDIR` と `STRATA_ORIGINAL_ENV` によって元環境の選び方が変わり、`extra` は最後にマージされる。通常の非 AppImage 起動では `externalEnvironment` は入力環境をコピーし、`PYTHONHOME` を変更しない（`app/host/server/external-env.mjs:60-71`）。

## 有効になる条件

- Terminal の Unix / Windows ランチャーでは、同梱 runtime を選んだ場合に限り `PYTHONHOME` を消してから `strata.py` / `setup.py` を起動する。明示した `STRATA_PYTHON`、venv、PATH 上の Python を選ぶ分岐では、この箇所による除去は行わない（`terminal/bin/strata:45-63,142-147`、`terminal/bin/strata.cmd:16-43`、`terminal/bin/strata-direct.ps1:27-58`）。
- Desktop の Control 確認コマンドおよび Host の Control 起動は同梱 interpreter 用の環境を作るため、元の値が設定されていても除去する（`app/desktop/src-tauri/src/main.rs:688-716`、`app/host/server/control-runtime.mjs:88-107,140-146`）。
- Control の handover 先を起動する場合も、`_child_env` が環境を複製して `PYTHONHOME` を削除する。handover 自体が行われない場合、この子環境処理は適用されない（`terminal/strata_cli/handover.py:117-145`）。
- インストール/準備用の子プロセスでも Control モードでは除去される。MCP installer は `spec.get("control")` の場合に削除し（`terminal/tools/strata_mcp.py:3151-3162`）、launch runner は準備コマンドの環境から削除して `PYTHONPATH` のみソースディレクトリに設定する（`terminal/strata_cli/launch/runner.py:1650-1661,1798-1805`）。
- AppImage の外部プログラム向けには、`APPIMAGE` / `APPDIR` の存在または元環境レコードの有無で分岐する。レコードがあればその復元環境を使い、なければ `APPDIR` に含まれる path list 要素を除く。path list は `:` 区切りであり、他の残存要素があれば結合して保持する（`app/host/server/external-env.mjs:26,28-40,43-57,60-71`）。
- AppImage 外部環境を使う folder chooser、opener、通知、ファイル関連コマンド、agent harness の呼び出し元は `app/host/server/` 内の `externalEnvironment()` 呼び出しを使う。外部プログラムが `PYTHONHOME` をどう解釈するかは本書の対象外（例: `folder-dialog.mjs:118,153`、`app-ui.mjs:39,57`、`agent/harness-runtime.mjs:26-36`）。

## 実行時の詳細

設定値を起動時にキャッシュする処理はない。各ランチャーは子プロセス起動直前に自身の環境から値を除去する。Node.js の Control helper は呼び出し時に環境オブジェクトを shallow copy し、キーを削除した環境を `spawn` に渡す。Desktop の Rust helper も `Command` の子プロセス環境からキーを除去する。起動済みプロセスの環境を書き換える処理ではなく、これらの起動後に親側で環境が変わっても、すでに渡した子環境には反映されない（`terminal/bin/strata:142-147`、`app/host/server/control-runtime.mjs:89-107,140-146`、`app/desktop/src-tauri/src/main.rs:688-716`）。

AppImage の外部環境 helper は呼び出しごとに `env`（既定値は `process.env`）を読み、必要に応じて記録環境の復号または `APPDIR` パスの除去を行う。記録環境は `STRATA_ORIGINAL_ENV` の base64 を NUL 区切りの `NAME=value` 項目として読む。`PYTHONHOME` 自体は helper の path-list 名一覧に固定で含まれるため、別の環境変数名で動的に参照されることはない（`app/host/server/external-env.mjs:15,26,28-57,67-71`）。

候補名の全参照には、上記のほか packaging ツールの subprocess 環境を作る際の削除（`tools/packaging/package_terminal.py:146-156,218-229`）と `setup.sh`、Windows の `START-HERE.bat` による bundled Python 起動前の削除（`setup.sh:12-17`、`START-HERE.bat:49-56`）がある。`terminal/tools/minimal_cli_smoke.py:26-32` と `terminal/tools/feed_model_install_gate.py:234-243`、`tools/layout/split/split_server_run.py:65-76` もそれぞれ smoke / gate / layout 作業用 subprocess の環境から削除する。テスト、コメント、README 上の参照は実装根拠として扱っていない。

## ログと測定値

`PYTHONHOME` の値や削除を理由に出す Strata のログ、警告、終了コードは確認できない。ランチャーの失敗メッセージや Control の起動結果は別の条件によるもので、この変数固有の結果ではない。性能測定値の記載もない。

## 根拠

- `terminal/bin/strata:45-63,142-147` — Unix Terminal の Python 選択と bundled runtime 分岐での削除。
- `terminal/bin/strata.cmd:16-43`、`terminal/bin/strata-direct.ps1:27-58` — Windows `cmd.exe` / PowerShell ランチャーの bundled runtime 分岐。
- `setup.sh:12-17`、`START-HERE.bat:49-56` — setup 用 bundled runtime の起動前処理。
- `app/desktop/src-tauri/src/main.rs:688-716`、`app/host/server/control-runtime.mjs:88-107,140-146` — Desktop / Host が Control 子プロセスへ渡す環境。
- `terminal/strata_cli/handover.py:117-145` — 新しい Control への handover 環境。
- `terminal/tools/strata_mcp.py:3151-3162`、`terminal/strata_cli/launch/runner.py:1650-1661,1798-1805` — installer / model preparation の子環境。
- `app/host/server/external-env.mjs:15,26,28-57,60-71`、`app/host/server/agent/harness-runtime.mjs:20-36` — AppImage 外部環境の復元・清掃と agent 環境の許可リスト。
- `tools/packaging/package_terminal.py:146-156,218-229` — package 作成時の interpreter / pip subprocess 環境。
- `terminal/tools/minimal_cli_smoke.py:26-32`、`terminal/tools/feed_model_install_gate.py:234-243`、`tools/layout/split/split_server_run.py:65-76` — smoke / gate / layout 作業用の子プロセス環境。
