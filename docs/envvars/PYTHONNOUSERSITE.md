# `PYTHONNOUSERSITE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査時の Strata checkout は `main` で、`git status --short --branch` は `## main...origin/main`。

## 役割

Strata はこの名前を設定値として読み込んで動作を切り替えるのではなく、同梱 Python や Control を起動する一部の経路で、子プロセス環境に文字列 `1` を設定する。既存の値が未設定・空文字・別の文字列のいずれでも、これらの経路では `1` に上書きする。主な箇所は Control 用環境を組み立てる `controlEnvironment` と、バンドル Python を選んだ CLI ラッパーである（`app/host/server/control-runtime.mjs:88-107`, `setup.sh:12-17`, `terminal/bin/strata:142-145`）。

Strata ソース内に `PYTHONNOUSERSITE` の値を読み取って分岐する実装は見つからなかった。この調査で確認できるのは Strata が環境値を設定して子プロセスへ渡すことまでであり、その値を受け取った Python や pip の挙動は対象外。

## 値と判定

Strata による値の parse や真偽判定はない。設定箇所はいずれもリテラル `1` を代入するため、親環境の unset、空文字、`0`、`true`、その他の値を判定する規則・無効値時の fallback・境界値はない。外部から与えた値がそのまま優先される規則もない。

| Strata の経路 | 親環境の `PYTHONNOUSERSITE` | 子プロセスへ渡す値 | 適用条件 |
|---|---|---|---|
| Linux セットアップ | 何であっても | `1` | `python/bin/python3` が実行可能なとき（`setup.sh:12-17`） |
| Terminal CLI ラッパー | 何であっても | `1` | bundled Python を選んだとき。Windows の PowerShell / cmd も同条件（`terminal/bin/strata:142-145`, `terminal/bin/strata-direct.ps1:27-41`, `terminal/bin/strata.cmd:34-40`） |
| Control / installer | 何であっても | `1` | Host が Control 環境を組み立てるとき（`app/host/server/control-runtime.mjs:88-107,140-146`） |
| Control の引き継ぎ・更新確認 | 何であっても | `1` | 新しい Control に引き継ぐとき、または staged Control の `--version` を試すとき（`terminal/strata_cli/handover.py:117-123,148-158`, `terminal/strata_control/updater.py:1883-1900`） |
| モデル準備・MCP セットアップ | 何であっても | `1` | 子 `setup.py` を起動する該当処理（`terminal/strata_cli/launch/runner.py:1650-1661,1797-1805`, `terminal/tools/strata_mcp.py:3151-3163`） |

## 有効になる条件

- bundled Python の条件分岐にある CLI ラッパーでは、その private runtime が選ばれた場合にだけ設定する。システム Python、venv、`STRATA_PYTHON` など別の interpreter を選ぶ枝では、この変数を設定するコードは該当箇所にない（`terminal/bin/strata:142-145`, `terminal/bin/strata-direct.ps1:30-44`, `terminal/bin/strata.cmd:29-40`）。
- `controlEnvironment` はアプリの Control を起動するとき、もとの環境を複製した後で `PYTHONNOUSERSITE: '1'` を加えるため、Control 起動では親環境の値によらず上書きされる（`app/host/server/control-runtime.mjs:88-107,140-146`）。
- 同じ Host でも、ソース checkout の API server 向け `sourceServerEnvironment` は環境を複製して UTF-8 等の設定を足すだけで、この変数を設定・削除しない。したがってその経路は親環境の値をそのまま引き継ぐ（`app/host/server/control-runtime.mjs:77-86`; 呼び出し `app/host/server/native-control.mjs:688-690`）。
- セットアップ・更新・モデル準備の該当子プロセスでも、環境を複製または組み立てた後に `1` を設定する（上表の各根拠箇所）。
- OS / backend / build macro / サーバー引数 / モデル状態による値の解釈分岐は Strata にない。CLI 引数や他の環境変数との値の優先順位もない。

## 実行時の詳細

各箇所はプロセス起動用の環境辞書またはコマンド環境を組み立てる際に設定する。たとえば `controlEnvironment` は呼び出しごとに `env` を複製して固定値を追加し、`runCli` や Control 起動に渡す（`app/host/server/control-runtime.mjs:88-107,140-146`）。handover は `environ` を辞書化してから固定値を設定し、更新版 Control の起動環境に渡す（`terminal/strata_cli/handover.py:117-123,148-158`）。これらのコードには `PYTHONNOUSERSITE` 専用の static cache や、実行中に環境値を再読込する処理はない。起動後にプロセス環境を変えた場合の反映は実装されていない。

`tools/packaging/package_terminal.py` は依存関係 probe と pip の install/check/list 用に作る subprocess 環境でも `1` を指定する（`tools/packaging/package_terminal.py:146-156,218-232`）。macOS の署名後 smoke test もスクリプト環境へ設定する（`tools/packaging/mac/sign-and-notarize.sh:392-400,471-478`）。Docker イメージでは build/runtime の `ENV` に固定値を定義している（`tools/docker/Dockerfile:113`, `tools/docker/Dockerfile.src:148`）。これらは配布物作成やコンテナ設定の経路である。

## ログと測定値

この変数を設定したこと自体を通知する Strata のログ、警告、終了コード変更は確認できなかった。子プロセスの起動失敗などは各起動処理の別のエラー経路であり、この変数の値による分岐ではない。対象変数について Strata 資料の測定値は確認できなかった。

## 根拠

- Linux セットアップの bundled Python 分岐: `setup.sh:12-17`
- Terminal launcher の bundled Python 分岐: `terminal/bin/strata:142-145`, `terminal/bin/strata-direct.ps1:27-41`, `terminal/bin/strata.cmd:34-40`
- Host の Control subprocess 環境: `app/host/server/control-runtime.mjs:88-107,140-146`
- Host の source checkout API server 環境（対象変数には触れない）: `app/host/server/control-runtime.mjs:77-86`, `app/host/server/native-control.mjs:688-690`
- Control handover: `terminal/strata_cli/handover.py:117-123,148-158`
- Control update version check: `terminal/strata_control/updater.py:1883-1900`
- モデル準備と MCP セットアップ: `terminal/strata_cli/launch/runner.py:1650-1661,1797-1805`, `terminal/tools/strata_mcp.py:3151-3163`
- 配布物 probe / pip と署名後 smoke test: `tools/packaging/package_terminal.py:146-156,218-232`, `tools/packaging/mac/sign-and-notarize.sh:392-400,471-478`
- Docker 環境: `tools/docker/Dockerfile:113`, `tools/docker/Dockerfile.src:148`
