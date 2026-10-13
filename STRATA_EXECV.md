# `STRATA_EXECV`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux など Windows 以外の環境で `setup.py` からサーバーを起動するとき、Python の `setup.py` プロセスをサーバーのプロセスに置き換えるかを決めます。有効にすると `subprocess.call()` で子プロセスを作る代わりに `os.execv()` を呼びます。Dockerfile はこの変数を `1` に設定し、サーバーがコンテナの PID 1 になるようにしています。

## 値と判定

`setup.py` は `os.environ.get("STRATA_EXECV")` の返り値を truth value として判定します。値の数値変換や文字列比較はありません。

| OS 条件 | 未設定 | 空文字 | 空でない値 |
|---|---|---|---|
| `os.name != "nt"` | 無効 | 無効 | 有効（`1`、`0`、`false` を含む） |
| Windows（`os.name == "nt"`） | 無効 | 無効 | 無効（分岐に入らない） |

したがって `STRATA_EXECV=0` や `STRATA_EXECV=false` も、Windows 以外では有効です。設定有無ではなく、Python 文字列の空・非空で分かれます。

## 有効になる条件

- `setup.py` の `start()` が呼ばれ、サーバー起動直前の分岐に到達すること。
- OS が Windows 以外であること。
- 環境変数が未設定または空文字でないこと。

CLI 引数や設定ファイルからこの環境変数を上書きする処理は見当たりません。`start()` に到達しない場合（たとえばサーバーを起動しない操作）には、この判定も実行されません。

## 実行時の詳細

`start()` は先に設定を読み、実行ファイルの存在を確認し、設定済みのエンジン引数などを反映してから、サーバー起動コマンドを `[sys.executable, <Strata>/serve/server.py, "--engine", "strata", "--config", <設定ファイル>, "--port", <port>]` として組み立てます。必要な起動前処理と表示の後に変数を読みます。

変数が有効なら `os.execv(cmd[0], cmd)` を実行します。これは同じプロセスを Python サーバーへ置き換え、`setup.py` 側の後続処理や `subprocess.call()` への復帰はありません。`execv` 呼び出しには環境辞書を渡さないため、Python の `os.execv` が現在のプロセス環境を引き継ぎます。無効なら `subprocess.call(cmd)` でサーバーを子プロセスとして実行し、終了コードを `start()` の戻り値にします。

標準の Dockerfile は `STRATA_EXECV=1` を設定します。Docker entrypoint は通常起動時に `exec .venv/bin/python setup.py ...` で setup.py を PID 1 にしており、この変数が有効な Linux コンテナでは、その同じプロセスがさらにサーバーへ置き換わります。Windows では変数を設定しても `os.execv` 分岐には入りません。

この分岐自体が追加のログやエラー文を出す処理はありません。`os.execv` が成功すればプロセス置換が起き、呼び出しが失敗した場合は `setup.py` 内で捕捉する処理がないため、その例外が通常どおり伝播します。

## 根拠

- `setup.py:62` — Windows 判定 `WIN = os.name == "nt"`。
- `setup.py:4276-4304` — `start()` とサーバー起動コマンドの組み立て。
- `setup.py:4397-4405` — truth-value 判定、`os.execv` と `subprocess.call` の分岐。
- `Dockerfile:44-47` — Docker イメージでの `STRATA_EXECV=1` 設定と意図。
- `docker-entrypoint.sh:96-106` — 通常起動時に setup.py を `exec` で起動。
- `docs/DETAILS.md` — `STRATA_EXECV` の個別記載は確認できませんでした。
