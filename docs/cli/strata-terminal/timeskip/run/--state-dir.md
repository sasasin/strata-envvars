# `strata timeskip run --state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip run` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | ディレクトリパス（文字列）。既定値は `None` |

## 役割

Time-skip 実行の永続状態を置くディレクトリを指定します。実行記録、基準チェックポイント、候補 revision などはこの保存先の下に作られます。作業対象の workspace は `--workspace` で別に指定します。

## 使い方

```sh
strata timeskip run --workspace ./project --prompt 'Improve the parser' --state-dir ./state/time-skip
```

相対パスは CLI プロセスの作業ディレクトリから解決されます。パーサーは `--state-dir` の引数を `default=None` で受け取り、値の型変換や選択肢制限は定義していません（`strata_cli/cli.py:352-369`）。

## 値と既定値

- 指定値が空でない場合、その値を `Path` に変換して保存先にします。
- 省略時は `STRATA_TIMESKIP_DIR` が設定されていればそのパスを使います。
- オプション省略時に環境変数も未設定なら、POSIX では `$XDG_STATE_HOME/strata/time-skip`（`XDG_STATE_HOME` 未設定時は `~/.local/state/strata/time-skip`）、Windows では `%LOCALAPPDATA%\\Strata\\time-skip`（`LOCALAPPDATA` 未設定時はユーザーの `AppData/Local/Strata/time-skip`）です。
- 明示した空文字列は truthy 判定を通らないため、未指定と同じく環境変数または OS 別既定値へ進みます。ディレクトリの存在、書き込み可否、絶対パスかどうかを CLI 独自に検証する処理は見当たりません。実際のディレクトリ作成時に OS のパス・権限エラーが発生すれば、共通エラー経路になります。

## 実行時の動作

`--state-dir` が指定されると、`_timeskip` の保存先決定関数が最優先でその値を返します。値がなければ `STRATA_TIMESKIP_DIR`、さらに `state_base()/time-skip` の順です（`strata_cli/cli.py:1476-1485`）。`state_base()` は POSIX の `XDG_STATE_HOME`（既定 `~/.local/state`）または Windows の `LOCALAPPDATA`（既定 `~/AppData/Local`）を使います（`strata_control/paths.py:13-21`）。

`strata timeskip run` は保存先ディレクトリを作成した後、実行 ID のサブディレクトリを作成します。実行状態は `run.json` に保存され、チェックポイントや revision 候補も同じ実行ディレクトリの下に置かれます（`strata_control/time_skip.py:321-347,369-372,408-419,422-448`）。このオプションは workspace の場所を変更せず、実行成果物の保存場所を切り替えます。

このオプションは `timeskip status`、`list`、`apply` にも別々の parser 定義がありますが、それらは各コマンドのスコープです。この文書の対象は `timeskip run` のみです（`strata_cli/cli.py:371-393`）。

## 適用条件と副作用

保存先ルートが存在しない場合、`TimeSkipStore` が `mkdir(parents=True, exist_ok=True)` で作成します。`run` はさらに実行 ID 用のディレクトリを作り、workspace のスナップショットや候補ファイル、実行状態をそこへ書き込みます（`strata_control/time_skip.py:698-700,321-347,408-419`）。既存の保存先を指定した場合、そこにある実行記録を使うため `status` / `list` / `apply` で参照する保存先とも一致させる必要があります。

保存先の作成・書き込みに伴う `OSError` は `_run` の共通処理で捕捉され、`strata:` 付きエラーとして報告されて終了コード 6 になります。通常の出力では標準エラー、`--output json` では JSON エラー出力になります（`strata_cli/cli.py:2166-2183`）。

## 根拠

- `strata_cli/cli.py:348-369` — `timeskip run` parser、`--state-dir` の `default=None`、help の既定パス表記。
- `strata_cli/cli.py:1476-1485` — 明示値、`STRATA_TIMESKIP_DIR`、OS 別既定値の優先順位と store 初期化。
- `strata_control/paths.py:13-21` — POSIX / Windows の共通 state base。
- `strata_control/time_skip.py:321-347,369-372,408-419,422-448` — run ID ディレクトリ、状態 JSON、チェックポイント・候補の保存。
- `strata_cli/cli.py:2166-2183` — `OSError` の共通出力・終了コード。

調査時点では checkout の parser と実装を根拠にしました。別途配布された Release artifact の挙動は照合していません。CLI `--help` は補助実行していません。
