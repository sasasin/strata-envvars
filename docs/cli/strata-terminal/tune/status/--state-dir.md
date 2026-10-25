# `--state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune status` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | ディレクトリパスを表す文字列（必須） |

## 役割

指定したディレクトリを tuning job の状態ファイルを探すルートとして使います。対象 job の状態ファイルは `<state-dir>/<job_id>/job.json` です。status はその JSON を読み、job の状態と記録済みの計画・測定レポートを表示します。

## 使い方

```sh
strata tune status 0123456789abcdef --state-dir ./tuning-state
```

JSON 出力も必要な場合は、別オプション `--output json` を指定できます。

## 値と既定値

- parser は `--state-dir` に値を要求しますが、値の型変換、形式検査、存在確認は行いません。相対パスはプロセスの現在の作業ディレクトリ基準で扱われ、`~` のホームディレクトリ展開もありません。
- 省略時は環境変数 `STRATA_TUNE_DIR` が設定されていればその値を使います。環境変数もなければ `state_base() / "tuning"` が使われます。Unix 系では `state_base()` は `$XDG_STATE_HOME/strata`（未設定時は `~/.local/state/strata`）、Windows では `%LOCALAPPDATA%/Strata`（未設定時は `~/AppData/Local/Strata`）です。
- 明示した空文字列は `state_root()` の真偽値判定で未指定扱いとなり、環境変数または既定値へフォールバックします。

## 実行時の動作

`--state-dir` の値を `Path` に変換してルートとし、位置引数 `job_id` をその下のディレクトリ名として連結して `job.json` を読みます。`--output` の既定値 `human` では job ID、state、backend、objective を表示し、report があれば metric、試行数、baseline、recommendation または理由、失敗した試行を表示します。`--output json` では `{"job": <job JSON>}` を成功応答として出力します。

このコマンドは状態ファイルを読む経路で、`--state-dir` によるディレクトリ作成や job ファイルの書き込みはありません。`--output` は同じ `tune status` parser の別オプションです。

## 適用条件と副作用

このオプションは `strata tune status` の parser にだけ定義されています。同じ `--state-dir` は `tune run`、`tune apply`、`tune rollback`、`tune list` にもありますが、それぞれのサブコマンドで別々に parser 登録されています。

パスの存在・ディレクトリ種別はオプション値の検証時には確認されず、実行時に `<root>/<job_id>/job.json` がファイルでなければ job 不在として扱います。`job_id` 自体もこの parser では形式検証されず、指定した文字列をパス連結に使います。

## 出力とエラー

- 指定先に対象の `job.json` がない場合、人向け出力では標準エラーに `strata: no tuning job <job_id>`、終了コード `2` を返します。JSON 出力時は `schema_version: 1`、`ok: false`、error code `2` の JSON を標準出力に出します。
- JSON の読み込みで `JSONDecodeError`（`ValueError`）が発生した場合は共通例外処理を通り、終了コード `2` のエラーになります。
- 読み込み時に `OSError` が発生した場合、共通例外処理はファイル操作エラーとして扱い、終了コード `6` を返します。通常表示では標準エラー、JSON 表示ではエラー JSON が出力されます。
- 正常時は人向け表示または JSON を標準出力に出し、終了コード `0` を返します。

## 根拠

- parser 定義と値の既定値: `strata_cli/cli.py:477-480`。
- `--state-dir`、`STRATA_TUNE_DIR`、標準 state path の優先順位: `strata_cli/cli.py:1643-1650`。
- status が選択した root から `job.json` を読み、欠落時に code 2、human/JSON 成功出力を組み立てる処理: `strata_cli/cli.py:1678-1706`。
- チューニングの状態 root を使うコマンド dispatch: `strata_cli/cli.py:1708-1713`、`strata_cli/cli.py:2156-2158`。
- 共通エラー出力（human は stderr、JSON は stdout）: `strata_cli/cli.py:527-532`。
- `ValueError` / `OSError` の共通処理と終了コード: `strata_cli/cli.py:2166-2183`。
- ユーザー state base の OS 別既定位置: `strata_control/paths.py:13-21`。
- 調査日と commit は調査開始時に確認した `git rev-parse HEAD`、`git status --short --branch` に基づきます。checkout は `## main...origin/main` で、表示上の未コミット変更はありません。
