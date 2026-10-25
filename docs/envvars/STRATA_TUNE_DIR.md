# `STRATA_TUNE_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリ、テスト、ベンチマーク記録は対象外。

## 役割

Strata Control の `strata tune` が、チューニングジョブの状態・レポートを保存して参照するディレクトリを指定します。Strata の推論エンジンが読む環境変数ではありません。CLI と Desktop App Host のチューニング管理経路で使われます。

## 値と判定

| 呼び出し経路 | 優先順位と値の扱い |
|---|---|
| `strata tune` CLI | サブコマンドの `--state-dir` が truthy なら最優先。次に `STRATA_TUNE_DIR` が空でなければその値を `Path` として使う。どちらも指定されない（または空文字）場合は platform ごとの既定ディレクトリを使う。 |
| Desktop App Host | Host が保持する環境オブジェクトの `STRATA_TUNE_DIR` が truthy ならその値を使い、空文字・未設定なら platform ごとの既定ディレクトリを使う。Host は解決したパスを子 `strata.py` プロセスの `STRATA_TUNE_DIR` に設定する。 |

値は文字列パスとして扱われ、数値変換、真偽文字列の解析、存在確認による fallback はありません。空文字は指定なしと同じです。空白だけの文字列は truthy なのでパスとして採用されます。CLI の `--state-dir` と環境変数の値はいずれもコード上で展開・正規化されません。

既定値は Windows では `%LOCALAPPDATA%\Strata\tuning`（`LOCALAPPDATA` がなければユーザー home の `AppData\Local\Strata\tuning`）、POSIX では `$XDG_STATE_HOME/strata/tuning`（未設定なら `~/.local/state/strata/tuning`）です。

## 有効になる条件

CLI では `strata tune` の状態を扱う `run`、`apply`、`rollback`、`status`、`list` 経路で `--state-dir` と環境変数が参照されます。`plan` は状態ストアを使わず、このディレクトリを参照しません。Desktop App Host では `/api/tune/jobs` と `/api/tune/job` のジョブ参照、および子 CLI 実行時に同じ解決先が使われます。

## 実行時の詳細

CLI は `_tune()` の呼び出し時に `--state-dir` と `os.environ.get("STRATA_TUNE_DIR")` を評価します。環境値はプロセス起動時に読み取って固定するキャッシュではなく、その CLI 呼び出し中に選択される保存先です。`run` は選択した root の下にジョブ ID のディレクトリを作り、`job.json` を状態ファイルとして保存します。`list` と `status` は同じ root からそれらを読みます。

Host は `tuningDir(env)` で環境値または既定値を解決します。子 CLI の起動時には Host が解決した値を `STRATA_TUNE_DIR` として環境に上書きして渡します。ジョブ一覧・詳細の API も同じ root を直接参照します。環境値で保存場所を変えた場合、別のディレクトリにある既存ジョブは自動では検索されません。

Strata リポジトリ内の製品コード文書に、この環境変数の追加の仕様説明は見つかりませんでした。動作の記述は調査対象 commit の実装に基づきます。

## 根拠

- `strata_cli/cli.py:1619-1637` — CLI の `--state-dir`、環境変数、既定値の優先順位。
- `strata_cli/cli.py:1695-1700` — 選択した root を run/apply/rollback に渡す箇所。
- `strata_cli/cli.py:456-482` — run/apply/rollback/status/list の `--state-dir` 定義。
- `strata_control/paths.py:13-21` — Windows と POSIX の状態 root の既定値。
- `strata_control/tuning.py:317-341` — root 配下の job ID ディレクトリと `job.json`。
- `apps/host/server/platform-paths.mjs:16-29` — Host の既定 root と `STRATA_TUNE_DIR` の解決。
- `apps/host/server/index.mjs:804-812,838-868,1077-1083` — 子 CLI への環境値の設定とジョブ読み取り。
