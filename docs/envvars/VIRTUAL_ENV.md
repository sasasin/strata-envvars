# `VIRTUAL_ENV`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 本体の計算や設定を切り替える環境変数ではありません。Strata は一部の Control 用子プロセスを作る前に、親プロセスから継承した環境マップから `VIRTUAL_ENV` のキーを取り除きます。値を読み取って使う、別の値へ変換する、または子プロセスへ転送するコードは見つかりませんでした。

## 値と判定

値の parse や値比較はありません。キーが未設定なら除去後も未設定のままです。空文字を含め、値が設定されていれば値の内容に関係なく子プロセス環境からキーごと削除されます。既定値、範囲、無効値時の fallback はありません。

| 経路 | `VIRTUAL_ENV` の処理 |
|---|---|
| `strata launch` が Control モードで `setup.py` を起動 | `_env()` で親環境を複製した後にキーを削除。その後 `PYTHONPATH` は Strata checkout のパスに設定し直す（`strata_cli/launch/runner.py:674-679,1142-1153`）。 |
| Host の Control CLI / Control installer 環境 | `controlEnvironment()` が入力環境を複製し、キーを削除する。CLI 実行と installer 環境生成の双方がこの helper を使う（`apps/host/server/control-runtime.mjs:88-103,106-111,124-130`）。 |
| 同梱 MCP installer の Control 用 install job | `spec.control` が真のときだけ、親環境の複製からキーを削除して `setup.py` を起動する。非 Control job ではこの削除分岐を通らない（`tools/strata_mcp.py:2841-2853`）。 |
| Desktop の bundled Control 自己診断 | `control_runs()` が bundled Python で `strata.py --version` を起動するときキーを削除する。自己診断の呼び出しは `run_self_test()` 内（`apps/desktop/src-tauri/src/main.rs:625-640,775-781`）。 |

## 有効になる条件

削除は上記の子プロセス環境を構成する経路に限られます。`strata launch` ではモデル準備が必要な場合の Control install が対象です。Host では Control 用 CLI と installer の環境を作るときに適用されます。MCP installer では `spec.control` 条件付きです。Desktop では自己診断の `--version` 子プロセスに適用されます。

これらの分岐に OS/backend/build macro/モデル状態による `VIRTUAL_ENV` 値の解釈差はありません。各経路が削除する限り、設定値の内容は問いません。通常の Strata engine 起動、一般の Python 起動、または親プロセス自身に対する一律削除は確認できませんでした。

## 実行時の詳細

各起動経路が子プロセス用の環境を組み立てる時点で処理します。環境マップの複製に含まれていた値を `pop` / `delete` / `env_remove` で捨ててから子プロセスを起動します。Strata は値を cache せず、存在確認に応じた別動作も行いません。したがって設定値が異なることによる Strata 側のログ、警告、終了コード、失敗経路はありません。子プロセス起動やその後の処理結果は別の要因によります。

## 根拠

- `strata_cli/launch/runner.py:674-679,1142-1153` — 親環境の複製、Control 用 setup 環境からの削除、`PYTHONPATH` の再設定、子プロセス起動。
- `apps/host/server/control-runtime.mjs:88-103,106-111,124-130` — Control 環境を複製してキーを除去し、Control CLI / installer に渡す。
- `tools/strata_mcp.py:2841-2853` — Control install job での条件付き除去と `Popen` への環境引き渡し。
- `apps/desktop/src-tauri/src/main.rs:625-640,775-781` — bundled Control の自己診断起動時の除去と呼び出し。
- `apps/host/tests/packaged-control.test.mjs:52-62` と `tests/desktop/test_control_install.py:340-347` にも名前が現れますが、これらはテストコードであり、実装の挙動根拠にはしていません。

候補一覧には名前がありますが、実装上の役割は値を読む設定ではなく、限定された Control 子プロセス環境からの除去です。
