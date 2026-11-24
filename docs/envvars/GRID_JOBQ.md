# `GRID_JOBQ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`GRID_JOBQ` は Strata の release-grid 補助スクリプト `tools/release_grid/grid.py` が `jobq.py` の実行ファイルパスを指定するための変数である。エンジンや通常の CLI / サーバー動作は制御しない。値はモジュール読み込み時に `JOBQ` へ代入され、`run` / `fetch` が job を submit するときに `sys.executable` の引数として使われる（`tools/release_grid/grid.py:32-37,137-150,187-241,282-303`）。

## 値と判定

Python の `os.environ.get("GRID_JOBQ") or <既定パス>` で読み取る。環境変数が未設定、または空文字なら `C:\Users\AI-Server\Desktop\Strata\phaseA-tests\jobq\jobq.py` にフォールバックする。空白だけの文字列を含む非空値はそのまま採用され、strip、パス存在確認、形式検証、大小文字変換はない。値は文字列のまま `subprocess.run` の argv に入るため、実行可能な Python スクリプトのパスとして解釈されるのはその呼び出し時である（`tools/release_grid/grid.py:37,137-139`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|
| 全実行環境 | Windows 固定の既定パスを使う | 空でないパス文字列（例: `C:\\tools\\jobq.py`、`/opt/jobq/jobq.py`） | 空文字は「無効値」ではなく未設定と同じ既定値。`0`、`false`、`true` も特別扱いされず、文字列のパスとして渡される。存在しないパス等も読み取り時には拒否されない。 |

この変数に対応する CLI 引数や別変数との優先順位はない。`--work`、`--timeout` などの CLI 引数は jobq の実行パスを変更しない（`tools/release_grid/grid.py:345-370`）。

## 有効になる条件

- 対象は Strata 同梱の release-grid 管理スクリプトに限られる。エンジンの build macro、GPU backend、モデル状態、サーバーモードによる条件分岐はない（`tools/release_grid/grid.py:32-37,345-379`）。
- `run` コマンドでは、`cells.json` の box に `jobq` があり、skip されない cell がある場合に job submission へ進む。`jobq` がない box は `no jobq box (...)` を表示して飛ばし、実行対象がないときも submit しない（`tools/release_grid/grid.py:219-240`）。
- `fetch` コマンドでは、対象 box に fetch する key がある場合に submit する。key がなければ `nothing to fetch` を表示して jobq を呼ばない（`tools/release_grid/grid.py:282-303`）。
- `boxes`、`plan`、`planfile`、`stage`、`collect`、`summary` は `jobq()` / `submit()` を呼ばない（コマンド分岐は `tools/release_grid/grid.py:345-375`）。

## 実行時の詳細

スクリプトの import 時に環境から一度読み、モジュール定数 `JOBQ` に保持する。したがって同じプロセス中に `os.environ` を変更しても再読込されない。`run` / `fetch` の submit 時には、`jobq()` が `[sys.executable, JOBQ, ...]` を起動する。呼び出し側の環境を引き継いだ上で `MSYS_NO_PATHCONV="1"` を設定し、stdout / stderr を捕捉してテキストとして読み、600 秒の timeout を指定する（`tools/release_grid/grid.py:32-37,137-150`）。

戻り値が非ゼロで `check=True`（通常の submit 呼び出し）なら `SystemExit` となり、`jobq <subcommand> failed: ` に stdout と stderr の末尾最大 500 文字を付けて終了する。成功時は stdout の前後空白を除いた文字列を返し、`submit()` はそこから job ID 形式を検索する。指定パスが起動できない場合や 600 秒を超える場合の `subprocess` 例外はこの関数内で捕捉されず、呼び出し元へ伝播する（`tools/release_grid/grid.py:137-152`）。

## ログと測定値

jobq が非ゼロ終了した場合の Strata 側エラー形式は `jobq %s failed: %s`（実際の subcommand と出力末尾を埋め込む）である。jobq が成功した場合、`run` / `fetch` は取得した job ID を標準出力へ表示し、`run` は `WORK/jobs.json` にも記録する（`tools/release_grid/grid.py:140-152,216-241,297-303`）。変数自体を設定したことを示すログや測定値はない。

## 根拠

- `tools/release_grid/grid.py:32-37` — スクリプトの場所と `GRID_JOBQ` の読み取り、既定パス。
- `tools/release_grid/grid.py:137-152` — 環境の転送、jobq 起動引数、timeout、エラー処理、job ID 抽出。
- `tools/release_grid/grid.py:187-241,282-303` — `run` / `fetch` の submit 条件と結果表示。
- `tools/release_grid/grid.py:345-379` — CLI コマンド一覧と dispatch。
