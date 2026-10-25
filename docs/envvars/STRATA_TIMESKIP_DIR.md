# `STRATA_TIMESKIP_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata の CLI、Python 制御コード、App Host を確認。外部ライブラリの環境変数は対象外。

## 役割

`strata timeskip` が作成する実行記録の保存ルートを指定します。CLI の `run`、`list`、`status`、`apply` で同じルートを使います。各 run はこのディレクトリ直下に run ID のサブディレクトリを持ち、状態は `run.json` などに保存されます。GPU エンジンの挙動は変えません。

## 値と判定

環境変数の値は文字列パスとして使われ、数値・真偽値としての parse や値域検査はありません。

| CLI の `--state-dir` | `STRATA_TIMESKIP_DIR` | 保存先 |
|---|---|---|
| 空でない値 | 任意 | `--state-dir` の値 |
| 未指定または空文字 | 空でない値 | 環境変数の値 |
| 未指定または空文字 | 未設定または空文字 | OS ごとの既定値 |

空白だけの値など、空文字でない文字列はそのままパスとして扱われます。相対パスの拒否や絶対パス化はこの選択箇所では行われず、相対パスは各プロセスの作業ディレクトリを基準に解決されます。CLI の `--state-dir` も空文字なら優先値になりません。

## 有効になる条件

`strata timeskip` の実行時に使われます。通常の生成・推論コマンドには参照がありません。App Host では起動時に `process.env` を設定オブジェクトへ取り込み、その値から UI の run 一覧・詳細参照先と子 CLI の保存先を決めます。ホスト稼働中に親プロセスの環境を変更しても、この取り込み済み設定は更新されません。

未設定または空文字の場合の既定値は次のとおりです。

- POSIX: `$XDG_STATE_HOME/strata/time-skip`。`XDG_STATE_HOME` も未設定または空なら `~/.local/state/strata/time-skip`。
- Windows: `%LOCALAPPDATA%\Strata\time-skip`。`LOCALAPPDATA` が空ならユーザープロファイル下の `AppData\Local\Strata\time-skip`。

## 実行時の詳細

Python CLI は `_timeskip()` の中で `--state-dir`、`STRATA_TIMESKIP_DIR`、OS 既定値の順に選び、そのルートで `TimeSkipStore` を作成します。CLI の各起動で読み取るため、同一プロセス内に値の static cache はありません。`run` では同じ選択関数から `TimeSkipRun` にルートを渡します。`--revise-command` を指定した場合は、その子プロセスに元の環境を継承したうえで `STRATA_TIMESKIP_PROMPT` と `STRATA_TIMESKIP_ATTEMPT` を追加します。

App Host は `timeSkipDir()` で環境変数または既定値を選びます。ホストが CLI を起動するときは、選んだルートを子環境の `STRATA_TIMESKIP_DIR` に設定し直します。`startDetached()` では `extraEnv` を合成した後にも同じルートを設定するため、`extraEnv` 内の同名値は採用されません。run の一覧・状態・ファイル操作もホスト側でこのルートを参照します。

## 根拠

- `strata_cli/cli.py:364-376` — `--state-dir` の指定と CLI ヘルプ上の既定値。
- `strata_cli/cli.py:1463-1472,1557,1562-1564` — 優先順位、ストアと run への適用、revision 子プロセスの環境継承。
- `strata_control/paths.py:13-21` — Python CLI の POSIX / Windows 既定 state root。
- `strata_control/time_skip.py:321-347,695-716` — run ID ごとの保存先と `run.json`、ストアの初期化。
- `apps/host/server/platform-paths.mjs:16-22,25-33` — App Host の既定値と `STRATA_TIMESKIP_DIR` の選択。
- `apps/host/server/index.mjs:876-881` — ホスト起動時の環境スナップショット。
- `apps/host/server/timeskip.mjs:25-27,302-309,367-390,449-455` — ホストの読み取り先と子 CLI への環境変数設定。
