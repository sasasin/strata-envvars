# `PYTHONUNBUFFERED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前は Strata の設定値として読み取られていません。Strata が子プロセス用の環境を組み立てる複数の経路で、既存環境にかかわらず `PYTHONUNBUFFERED=1` を設定して転送します。Dockerfile でもイメージ環境の値として `1` を指定しています。Strata のコードはこの値を分岐やログ出力制御に使わず、値を解釈する処理もありません。

## 値と判定

Strata 内に `PYTHONUNBUFFERED` の読み取り、文字列比較、数値変換はありません。そのため Strata 側の「未設定」「空文字」「無効値」の判定や fallback はありません。

| 経路 | 既存値との関係 | 子プロセスへ渡す値 |
|---|---|---|
| Host が source checkout の server、native 操作、auto-tune を起動 | `process.env` を複製して上書き | 常に `1` |
| Host が Strata Control / installer を起動 | `controlEnvironment()` が入力環境を複製して上書き。installer も同 helper を使う | 常に `1` |
| CLI launch runner が子プロセスを起動 | `os.environ` を複製して上書き | 通常は `1`。一部の起動環境組み立てでは `self.s.extra` の同名項目が後から上書き可能 |
| MCP ツールが install job、server、setup を起動 | `os.environ` を複製して上書き | 常に `1` |
| tune worker が server を起動 | `os.environ` と `extra_env`、要求環境を組み立てた後に上書き | 常に `1` |
| Docker イメージ | Dockerfile の `ENV` 指定 | `1` |

Strata 内で起動時に一度だけ読む値や static cache はありません。上記の環境辞書は各子プロセス起動時に作られます。

## 有効になる条件

環境値の付与は、該当する Host、CLI、MCP、tune worker の起動経路が使われる場合に行われます。GPU backend、OS、build macro、モデル状態による `PYTHONUNBUFFERED` の判定は見つかりません。Control 起動時も `controlEnvironment()` が `1` を設定します。

CLI launch runner の `_env()` は親の `os.environ` を複製し、`PYTHONUNBUFFERED="1"` を指定します。engine test 用の環境を作る経路では、その後 `self.s.extra` の通常環境項目を適用するため、同名項目がある場合は `off`、`unset`、`none` 以外の文字列で上書きされます。model setup 用の経路は同じ `_env()` から作り、追加で `PYTHONPATH` などを設定します（`strata_cli/launch/runner.py:674-679,744-748,1142-1153`）。

## 実行時の詳細

- Host の source checkout server は `sourceServerEnvironment()` で親環境を複製し、この変数を `1` に上書きしてから `serve/server.py` を起動します（`apps/host/server/control-runtime.mjs:82-86`, `apps/host/server/native-control.mjs:387-390`）。Host の native auto-tune、native install/update/calibrate も子プロセス環境に `1` を設定します。packaged 経路では `controlEnvironment()` または `installerEnvironment()` を通り、同じ値が設定されます（`apps/host/server/native-control.mjs:55,106,414`, `apps/host/server/control-runtime.mjs:89-103,110-112`）。
- CLI launch runner は `_env()` で値を設定し、`_spawn()` の `subprocess.Popen(..., env=...)` に渡します（`strata_cli/launch/runner.py:674-685`）。この runner の engine update と model setup の起動元はそれぞれ `744-748`, `1142-1153` にあります。
- MCP ツールは install job、server、setup の各起動で親環境を複製して値を設定します。`spawn_detached()` は受け取った環境をそのまま `subprocess.Popen` に渡し、setup job も同様に `Popen` へ渡します（`tools/strata_mcp.py:329-342,2431-2434,2494-2500,2841-2853`）。
- tune worker は親環境等から `spawn_env` を作った後に値を `1` にし、`serve.server` 起動へ渡します（`strata_control/tune_session.py:469-484`）。
- Docker イメージは build stage と runtime image の `ENV` に `PYTHONUNBUFFERED=1` を含めます（`Dockerfile:25,103-105`, `docker/Dockerfile:104-112`）。

起動後の値を Strata が再評価したり、実行中に変更した値を読み直す箇所はありません。Host は起動した server/native job の stdout/stderr を読み、ログや job 状態に反映します（`apps/host/server/native-control.mjs:387-390,414`）。MCP の detached child はログファイルに stdout/stderr を記録し、server/install の開始・終了状態も管理します（`tools/strata_mcp.py:329-342,2421-2451,2489-2506,2852-2859`）。これらは出力収集の Strata 側処理であり、`PYTHONUNBUFFERED` が各子プロセス内でどう作用するかはこの調査の対象外です。

## 根拠

候補名の全参照を Strata リポジトリ全体で検索しました。アプリ・CLI・Control・MCP・Docker の本番参照は上記の環境設定・転送です。残る参照はテスト、ベンチマーク結果ディレクトリ内の記録・測定スクリプトであり、製品動作の根拠にはしていません。`docs` にこの変数の説明は見つかりませんでした。

Strata 本体が環境から値を読んで意味を判定する変数ではなく、起動経路が子プロセスに固定値を渡す変数として記録します。
