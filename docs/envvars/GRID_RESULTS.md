# `GRID_RESULTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Strata 同梱のリリース検証グリッド用コーディネータ `tools/release_grid/grid.py` で、`--work` の既定ディレクトリを指定します。ここには `run` のジョブ記録・計画ファイル、`planfile` の計画ファイル、`collect` が集める結果、`summary` が読む結果と出力する Markdown/JSON が置かれます。Strata エンジンの実行時設定ではありません。`grid.py` は `grid_lib.default_results_dir()` の戻り値を parser の `--work` の default に設定し、その各コマンドは `a.work` をパスとして使います（`tools/release_grid/grid.py:345-355`, `214-241`, `248-253`, `306-338`）。

## 値と判定

`tools/release_grid/grid_lib.py:357-358` で `os.environ.get("GRID_RESULTS") or (...)` を評価し、結果を `Path` に渡します。環境変数が未設定 (`None`) または空文字なら、既定値 `HERE.parents[1] / "grid-results"` です。`HERE` は `grid_lib.py` のある `tools/release_grid` なので、既定場所は Strata リポジトリ直下の `grid-results` です。空白だけの値を含む非空文字列は真として採用され、文字列全体がパスになります。真偽値以外の文字列検査、数値変換、大小文字比較、範囲制限、存在確認、正規化はこの関数では行いません。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `grid.py` の `--work` default を評価 | Strata リポジトリ直下の `grid-results` | `GRID_RESULTS=/tmp/release-grid` は `/tmp/release-grid` | 空文字 `GRID_RESULTS=""` は無効値として既定場所に戻る。値の形式による無効判定はなく、`0`、`false`、空白文字列もパスとして採用 |

ただし CLI で `--work DIR` を指定すると、argparse が default をその値で置き換えます。したがって、そのコマンドの保存・読込先は `GRID_RESULTS` の値ではなく `DIR` です（`tools/release_grid/grid.py:345-356`）。

## 有効になる条件

- `tools/release_grid/grid.py` を実行する場合に使われます。リポジトリ内の名前参照は `grid_lib.py` の読み取りと `grid.py` の default 指定だけで、候補名を参照する別の実装箇所はありません。
- `--work` を受け取るコマンドでは、`--work` が `GRID_RESULTS` に優先します。`run` はこの場所に `jobs.json` と plan JSON を作成し、`planfile` は plan JSON を書き、`collect` は `results/<label>` に収集し、`summary` は同階層の結果を読み、`summary-<candidate>.md/.json` を出力します（`tools/release_grid/grid.py:214-241`, `248-253`, `306-338`）。
- `--work` を使わない `boxes`、`plan`、`stage`、`fetch` では、値は parser の default として評価されますが、その値を使ったファイル操作はありません（`tools/release_grid/grid.py:345-375`）。
- OS、GPU backend、build macro、サーバーモード、モデル状態による条件分岐はありません。この参照は Python のリリース検証ツール内にあります。

## 実行時の詳細

値は `main()` が argparse parser を構築するとき、`add_argument("--work", default=str(gl.default_results_dir()))` の引数評価として読み取られます。各 `grid.py` 起動につき parser 構築時に一度評価され、関数内 static cache やリクエストごとの再読込はありません。環境変数を起動後に変更しても、すでに起動したプロセスの `a.work` には反映されません。新しいプロセスではそのプロセスの環境から読み直します（`tools/release_grid/grid.py:345-370`, `tools/release_grid/grid_lib.py:357-358`）。

`--work` を省略したとき、選ばれたパス文字列は `Path` に包まれます。相対パスならコマンドの作業ディレクトリ基準です。`run` は `mkdir(parents=True, exist_ok=True)` して `jobs.json` と計画ファイルを作成し、`collect` は結果ディレクトリを作成して scp の宛先にし、`summary` はそこから結果を読み Markdown と JSON を書きます。ディレクトリ作成・読み書き・scp 等で失敗した場合の例外や終了は各処理に委ねられ、この環境変数用の警告・fallback はありません（`tools/release_grid/grid.py:214-241`, `306-338`, `tools/release_grid/grid_lib.py:345-350`）。

## 根拠

- `tools/release_grid/grid_lib.py:357-358` — 環境値の読み取り、空値時の fallback、`Path` 化。
- `tools/release_grid/grid.py:345-370` — `--work` の default 登録と引数 parse。
- `tools/release_grid/grid.py:214-241`, `248-253`, `306-338` — work ディレクトリを使う各コマンドとファイル出力。
