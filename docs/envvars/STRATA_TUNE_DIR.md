# `STRATA_TUNE_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata CLI の一部の `strata tune` サブコマンドが、チューニングジョブの保存・参照先にするディレクトリを指定します。対象は `list`、`status`、`run`、`apply`、`rollback` です。これは GPU 計算や推論エンジンの動作を切り替える変数ではありません。

Desktop Host も同名の値を状態ディレクトリとして使い、チューニング用の子 CLI プロセスへ渡します。現在の Host API では plan の作成、記録済みジョブの一覧・詳細取得に使われます。

## 値と判定

| 条件 | 選ばれるディレクトリ |
|---|---|
| CLI の `--state-dir` が空でない | その引数の値（環境変数より優先） |
| `--state-dir` が未指定または空で、`STRATA_TUNE_DIR` が空でない | 環境変数の値 |
| 両方とも未指定または空 | platform state の下の `tuning` |

CLI は引数と環境変数を trim せず、文字列として `Path` に渡します。空文字は false 扱いで次の候補へ進み、空白だけの値は非空としてパスに使われます。非空値の存在確認や正規化はこの選択箇所では行いません。

既定ディレクトリは Windows では `%LOCALAPPDATA%\\Strata\\tuning`（`LOCALAPPDATA` が空なら `~/AppData/Local/Strata/tuning`）、それ以外では `$XDG_STATE_HOME/strata/tuning`（`XDG_STATE_HOME` が空なら `~/.local/state/strata/tuning`）です。既定値のルールは `strata_control/paths.py` にあります。

## 有効になる条件

- CLI の `strata tune list/status/run/apply/rollback` で有効です。各サブコマンドにある `--state-dir` が非空なら環境変数より優先します。
- `strata tune plan` は選択した状態ディレクトリを使わず、`strata tune auto` は共通処理の先頭で別実装へ委譲するため、この環境変数を読む `_tune` 内の状態パス選択を通りません。
- Desktop Host の `tuningDir()` は、Host に渡された環境の非空 `STRATA_TUNE_DIR` を使い、空なら OS と `XDG_STATE_HOME` / `HOME` または `LOCALAPPDATA` から既定値を組み立てます。
- OS は既定パスの組み立てに影響します。backend、GPU、モデル状態による環境変数自体の判定分岐はありません。

## 実行時の詳細

CLI は `_tune()` の呼び出し時に `state_root()` を定義し、対象サブコマンドの処理で必要になった時に `--state-dir`、環境変数、既定値の順に選びます。環境変数はプロセス起動時に static cache されず、この処理で `os.environ.get()` により読み取られます。`list` は選択先のジョブディレクトリを走査し、`status` はその下の `<job-id>/job.json` を読みます。`run` は選択先を `Tuner` に渡し、`Tuner` は `<job-id>` ディレクトリを作成して `job.json` を保存します。`apply` と `rollback` も同じ選択先を使います。

Desktop Host の状態パス関数は Host の環境オブジェクトから要求時に値を参照します。`/api/tune/jobs` はジョブ一覧と選択された `stateDir` を返し、`/api/tune/job` は同じルートのジョブ記録を探します。Host が CLI を起動する際は、継承環境を展開したうえで `STRATA_TUNE_DIR` を `stateDir()` の結果に設定します。したがって Host の既定パスも子 CLI に明示的に渡されます。

観測できる結果として、CLI の human 出力では空の一覧は `no tuning jobs recorded`、見つからない状態照会は `no tuning job <job-id>` で終了コード 2 になります。JSON 出力では `_error()` が `ok: false` のエラー envelope を出します。Host のチューニング用 CLI 起動失敗は収集した stderr/stdout または終了コードをエラー結果にし、plan API は失敗時に HTTP 400 または 502 を返します。変数のパスが無効な場合の個別エラー処理はパス選択箇所にありません。

## 根拠

- `strata_cli/cli.py:1643-1650` — 非空の `--state-dir`、環境変数、既定ディレクトリの優先順。
- `strata_cli/cli.py:1655-1713` — `list/status/run/apply/rollback` が状態ルートを使う箇所。
- `strata_cli/cli.py:1715-1723` — `plan` は状態ルートを使わない。
- `strata_cli/cli.py:395-486,2153-2157` — `--state-dir` を持つサブコマンドと `_tune()` への振り分け。`auto` は `strata_cli/cli.py:1652-1653` で先に委譲される。
- `strata_control/paths.py:13-21` — Windows と POSIX の状態ディレクトリ既定値。
- `strata_control/tuning.py:317-341` — `run` の保存先ディレクトリ作成と `job.json` の場所。
- `apps/host/server/platform-paths.mjs:17-29` — Host の OS 別 state root と空値時の既定 tuning directory。
- `apps/host/server/index.mjs:835-854,870-899` — Host の子 CLI 環境への設定、ジョブ一覧・詳細取得。
- `apps/host/server/index.mjs:1084-1114` — Host の plan、jobs、job API。
- `strata_cli/cli.py:527-535,1678-1683` — CLI のエラー表示・JSON envelope と job 不在時の終了コード。
