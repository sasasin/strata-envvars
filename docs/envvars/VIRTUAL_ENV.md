# `VIRTUAL_ENV`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata は `VIRTUAL_ENV` の値を設定として解析しない。用途は子プロセス環境の整理または継承である。Control 用 Python を起動する経路やモデル準備用 `setup.py` の起動ではキーを除去する。一方、通常の serve では親環境を engine の子環境へコピーし、`VIRTUAL_ENV` を特別扱いせず渡す。したがってこの変数自体がモデル、backend、CLI の選択を変える処理は確認できない（`app/host/server/control-runtime.mjs:88-107,141-146`; `terminal/strata_cli/launch/runner.py:1719-1730,1869-1876`; `terminal/serve/server.py:4007-4028`）。

## 値と判定

値を数値・真偽値・パスとして parse する Strata の読み取り箇所はない。経路ごとの扱いは次のとおり。

| 経路 | 未設定 | 設定あり（空文字を含む） | 判定・上書き |
|---|---|---|---|
| Packaged Control の環境（`controlEnvironment`） | コピー後もキーなし | コピーしたキーを削除 | 値を見ずに削除。`runCli` と `installerEnvironment` がこの環境を使う（`app/host/server/control-runtime.mjs:89-107,114-119,141-146`）。 |
| Terminal のモデル準備・pack 準備 | `env.pop` は何もしない | `env.pop` で削除 | その後 `PYTHONPATH` を Strata のソースディレクトリに設定する（`terminal/strata_cli/launch/runner.py:1719-1730,1869-1876`）。 |
| MCP の Control install job | キーなしのまま | `spec.control` が真なら削除、偽なら継承 | Control install job の条件分岐内だけ削除する（`terminal/tools/strata_mcp.py:3151-3162`）。 |
| serve の engine 子環境 | 親環境にないため通常はキーなし | 親環境からコピー | `cfg.env` に `VIRTUAL_ENV` があれば文字列化してコピー値を上書きする（`terminal/serve/server.py:4007-4028`）。 |
| Control への CLI handover | 引き継がれない | 値をそのまま引き継ぐ | `_child_env` は `PYTHONHOME` と `PYTHONPATH` を削除するが、このキーは変更しない（`terminal/strata_cli/handover.py:117-123,126-158`）。 |

これらの除去経路では空文字、`0`、`false`、通常のパスなどに差はなく、キーが存在すれば削除する。継承経路では値の内容による Strata 独自の分岐はなく、空文字もコピー対象になる。

## 有効になる条件

- 有効化する値、OS、backend、build macro、CLI 引数、モデル状態はない。どの挙動になるかは起動経路で決まる。
- Packaged app の Control 実行環境は `controlEnvironment` が作り、`VIRTUAL_ENV` を常に除去する。`runCli` に加え、Control の installer 環境もこの関数を基にする（`app/host/server/control-runtime.mjs:88-107,114-119,141-146`; `app/host/server/native-control.mjs:200-205`）。
- Terminal がモデルの `setup.py` または `--prepare-pack` を起動するときは除去する。それ以外の `_env()` コピー自体はこのキーを除かない（`terminal/strata_cli/launch/runner.py:1033-1043,1719-1730,1869-1876`）。
- serve は全 backend 共通の `child_env` で親環境をコピーする。`cfg.env` の同名キーがあればその値が優先され、engine 起動時に渡る（`terminal/serve/server.py:4007-4028,9391-9394`）。
- MCP の Control install job は `spec.control` が真のときだけ削除する。MCP の `strata_start` は環境をコピーして起動し、このキーを削除しない（`terminal/tools/strata_mcp.py:3151-3162,2792-2810`）。
- デスクトップの Control バージョン確認 `control_runs` は明示的に削除する。隣接する `control_engine_notice` は `PYTHONHOME` と `PYTHONPATH` だけを削除するため、こちらでは親に設定されていれば引き継がれる（`app/desktop/src-tauri/src/main.rs:688-704,708-716`）。

## 実行時の詳細

除去経路は、子プロセスの環境辞書を作る際にキーを削除する。Python の Terminal runner と MCP は `os.environ` のコピーを作ってから `pop` し、Control host は `process.env` をコピーしてから `delete` する。Rust の Control 確認は `Command` に `.env_remove("VIRTUAL_ENV")` を指定する。値を cache したり、プロセス内で後から再評価したりする処理ではなく、子プロセスを起動する時点でその起動に使う環境へ反映される（`terminal/strata_cli/launch/runner.py:1720-1730,1871-1876`; `terminal/tools/strata_mcp.py:3153-3163`; `app/host/server/control-runtime.mjs:89-107`; `app/desktop/src-tauri/src/main.rs:688-696`）。

継承経路では `serve.child_env` が `os.environ` をコピーして engine 環境を作り、設定の `cfg.env` を後から反映する。CLI handover も引数で受けた環境をコピーして Control の Python に渡す。これらの経路で `VIRTUAL_ENV` を Strata が解釈・変更する処理はない（`terminal/serve/server.py:4007-4028`; `terminal/strata_cli/handover.py:117-158`）。

## ログと測定値

`VIRTUAL_ENV` の除去・継承を知らせる専用ログや警告はない。デスクトップの自己診断は Control の起動成否と出力を `control-runs-on-bundled-python` の記録に使うが、変数の値や除去結果を個別に報告しない（`app/desktop/src-tauri/src/main.rs:696-703,838-845`）。該当する測定値はない。

## 根拠

- `app/host/server/control-runtime.mjs:82-107,114-119,141-146`
- `app/host/server/native-control.mjs:200-205`
- `app/desktop/src-tauri/src/main.rs:688-704,708-716,838-845`
- `terminal/strata_cli/handover.py:117-158`
- `terminal/strata_cli/launch/runner.py:1033-1043,1719-1730,1869-1892`
- `terminal/serve/server.py:4007-4028,9391-9394`
- `terminal/tools/strata_mcp.py:2792-2810,3151-3169`
