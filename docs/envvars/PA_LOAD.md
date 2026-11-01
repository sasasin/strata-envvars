# `PA_LOAD`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PA_LOAD` は Strata エンジンやサーバーの設定ではなく、同梱の `tools/par` 実験用ハーネス `tools/par/both.py` が、2 回目のロード計測に使う別の Python ローダースクリプトのパスとして読む環境変数です。通常の Strata 起動だけでは参照されず、`both.py` をロードコマンドとして実行する場合に使われます。

## 値と判定

値は文字列のまま Python 実行ファイルのスクリプト引数に渡されます。存在確認、空文字判定、パス補完、正規化、既定値への fallback はありません。

| 状態 | 動作 |
|---|---|
| 未設定 | `os.environ["PA_LOAD"]` で `KeyError` になります。先行する sustained 計測は呼び出し済みですが、burst ローダーは起動されません。 |
| 空文字 | 空文字をスクリプトパスとして `sys.executable` に渡します。実行先の起動に失敗し得ます。 |
| 値あり | 文字列全体がスクリプトパスとして渡されます。値の形式・存在・実行結果を `both.py` は事前検証しません。 |

## 有効になる条件

- `tools/par/both.py` が `URL OUT.json` の引数で起動され、実行が burst ロード部分まで到達することが必要です。
- 同梱の `tools/par/recon3.py` は `armrun.py` を起動する際、環境辞書に `PA_LOAD=PA + "/par_load.py"` を設定します。この代入は元プロセスの `PA_LOAD` の値を上書きします。`PA` は `box` の分岐に応じた絶対パスです。
- この変数に OS、GPU backend、Strata の build macro、モデル状態による分岐はありません。ソースに記載された利用経路は `tools/par` の実験用ロードハーネスです。

## 実行時の詳細

`both.py` はまず同梱 `par_load.main(...)` を使い、`BOTH_CONC`（未設定なら `8,16,32`）の並列度で sustained workload を実行します。その後 `os.environ["PA_LOAD"]` を参照し、`sys.executable` から指定スクリプトを `URL`、並列度、`--rounds 2`、`--prompt-tokens 1000`、`--max-tokens 128`、burst 出力先とともに起動します。環境変数の読み取りに static cache はなく、`both.py` の burst 部分に達した時点のプロセス環境が参照されます。

`recon3.py` から起動した場合、`subprocess.run(..., env=e2, capture_output=True, text=True)` により、その子プロセスへ `PA_LOAD` を含む環境が渡ります。`both.py` の `subprocess.run` は `check=True` を指定せず、戻り値を検査・報告する処理もありません。起動時の例外やローダーの失敗を `both.py` が捕捉する処理もありません。`recon3.py` 側も `armrun.py` の戻り値を検査せず、後続で結果ファイルが存在すれば内容の一部を表示します。

## 根拠

- `tools/par/both.py:2-3` — `both.py` が sustained と burst のロードを行うハーネスである旨。
- `tools/par/both.py:8-15` — `BOTH_CONC` の既定値、sustained 呼び出し、`PA_LOAD` の直接参照と子プロセス引数。
- `tools/par/recon3.py:47-57` — `both.py` を `--loadcmd` として指定し、子プロセス環境に `PA_LOAD` をセットして起動する箇所。

候補一覧 `000_envvers.md` は環境変数名の直接参照を保証しません。この調査では `PA_LOAD` の実際の読取箇所を `tools/par/both.py:15` に確認しましたが、確認できた用途は実験用ハーネスに限られます。
