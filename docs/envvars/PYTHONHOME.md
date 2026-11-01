# `PYTHONHOME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部 Python 実行環境が `PYTHONHOME` をどう解釈するかは対象外。

## 役割

この commit の Strata 所有コードには、`PYTHONHOME` の値を設定項目として読み取り、値に応じて Strata のモデル処理や engine/backend を切り替える実装は見つからない。Strata は主に同梱 Python runtime や Control などの子プロセスを起動する前に、継承環境からこの名前を削除する。一方、AppImage 内からファイル選択・通知・外部ツール等を起動する共通経路では、起動元の環境を復元して渡す場合がある。

## 値と判定

Strata が値を boolean / 数値 / パス設定として parse する処理はない。したがって Strata 内部での unset・空文字・任意文字列の値判定、境界値、無効値 fallback は該当しない。

| 実行経路 | `PYTHONHOME` の扱い |
|---|---|
| Linux `bin/strata` から同梱 Python を使う | `unset PYTHONHOME` で継承値を削除する。空文字か否かを判定しない（`bin/strata:128-131`）。 |
| Windows PowerShell / cmd の同梱 Python 分岐 | 環境変数を削除または空にする（`bin/strata.ps1:34-39`, `bin/strata.cmd:34-39`）。 |
| setup / package 検査・handover・Control 起動 | 子プロセス用の env map からキーを削除する（`setup.sh:9-12`, `strata_cli/handover.py:117-123`, `apps/host/server/control-runtime.mjs:88-104`, `packaging/package_terminal.py:202-207,432-437`）。 |
| Terminal のモデル準備 | 継承キーを削除後、`PYTHONPATH` は Strata source path に設定される。`PYTHONHOME` 自体は設定しない（`strata_cli/launch/runner.py:1142-1153`）。 |
| AppImage から起動する外部プログラム | `externalEnvironment()` は記録された起動元環境があればそれを復元する。記録がなければ AppImage 専用値を削除し、`APPDIR` 内を指す path-list 要素を除く（`apps/host/server/external-env.mjs:15-26,28-57,63-70`）。 |

`external-env.mjs` の `PYTHONHOME` は、コメント上の値一覧と `PATH_LISTS` に現れ、独立した parse はしない。起動元環境の復元時には元の値を外部プロセスへ引き継ぎ、記録がない場合には `APPDIR` 内の要素だけを `:` 区切りで落とす。`APPDIR` がない場合、`withoutAppImage()` はその path-list 値に手を加えない。これは Strata の環境引き渡し処理の説明であり、受け取った Python 等での意味を示すものではない。

## 有効になる条件

- ランチャーが同梱 Python を選んだ場合に限り、シェルラッパーが `PYTHONHOME` を明示的に除去する。外部指定 Python (`STRATA_PYTHON`) や既存 venv を選ぶ分岐では、これらの箇所による削除は同梱 runtime 分岐と異なる。PowerShell の分岐条件は `bin/strata.ps1:28-44`、POSIX ランチャーは `bin/strata:128-131` にある。
- setup の `setup.sh` は `python/bin/python3` が存在する場合だけ削除して `setup.py` を exec する（`setup.sh:7-13`）。
- Desktop が同梱 Python を用いる version / engine 検査 subprocess では `.env_remove("PYTHONHOME")` を設定する（`apps/desktop/src-tauri/src/main.rs:627-632,649-654`）。
- Control の環境生成は呼び出し元の env を複製してから `PYTHONHOME` を削除する。Terminal のモデル準備と Control handover もそれぞれ専用 env を作る際に削除する。CLI 引数や別環境変数による `PYTHONHOME` の優先順位はない。
- AppImage の外部プログラム経路は `externalEnvironment()` の呼び出し元（例: `apps/host/server/folder-dialog.mjs:111,146`, `apps/host/server/app-ui.mjs:38,56`, `apps/host/server/chat-files.mjs:92`）に適用される。AppImage 外で `APPIMAGE` / `APPDIR` と記録がなければ、関数は env を複製して `extra` を上書き追加するだけであり、`PYTHONHOME` を削除しない（`external-env.mjs:60-70`）。

## 実行時の詳細

削除は子プロセス用環境を組み立てる際、または同梱 runtime を exec する直前に行われる。シェルの `unset`, PowerShell の `Remove-Item`, Rust `Command::env_remove`, Python の `dict.pop`, JavaScript の `delete` であり、値を読み込んで cache する処理はない。後から同じプロセスの環境を変更したときの再評価機構もない。子プロセスに対しては、削除後の環境 map が渡される。

外部プログラム用環境では AppImage 起動元環境を復元するのが優先され、復元記録がない旧式経路だけ `APPDIR` に属する値・path-list 要素を掃除する。`PYTHONHOME` に関する Strata 固有の警告、エラー、終了コードは見つからなかった。`bin/strata.ps1` 等の別のエラー表示は Python 選択の失敗に関するもので、この変数の値検査ではない。

## 根拠

- 同梱 runtime 起動前の環境除去: `bin/strata:128-133`, `bin/strata.ps1:28-44`, `bin/strata.cmd:34-43`, `setup.sh:7-13`。
- Control / handover / installer 子プロセスの env 構築: `strata_cli/handover.py:117-123`, `strata_cli/launch/runner.py:1142-1153`, `apps/host/server/control-runtime.mjs:88-104`, `tools/strata_mcp.py:2843-2848`。
- Desktop / package helper subprocess の除去: `apps/desktop/src-tauri/src/main.rs:627-654`, `packaging/package_terminal.py:202-208,432-438`, `tools/minimal_cli_smoke.py:25-31`。
- AppImage 外部プログラム向け環境の変換と適用箇所: `apps/host/server/external-env.mjs:15-26,28-70`, `apps/host/server/folder-dialog.mjs:111,146`, `apps/host/server/app-ui.mjs:38,56`, `apps/host/server/chat-files.mjs:92`, `apps/host/server/artifacts.mjs:6`, `apps/host/server/open-text-file.mjs:28`, `apps/host/server/agent/harness-runtime.mjs:30`。
- テスト・文書の記載は候補や意図の補助情報に留め、本番挙動の根拠にはしていない。
