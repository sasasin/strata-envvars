# `--state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip status` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | ディレクトリのパス（文字列） |

## 役割

Time-skip の run 状態を読む保存先ディレクトリを指定します。指定したディレクトリの下にある `<run_id>/run.json` が status の読み取り対象です。

## 使い方

```sh
strata timeskip status 0123456789abcdef0123456789abcdef --state-dir ./timeskip-state
```

## 値と既定値

- parser は値を文字列として受け取り、型変換やパス形式の検証をしません。短縮別名もありません（`strata_cli/cli.py:371-374`）。
- 値が truthy ならその値を `Path` に変換して使用します。相対パスは実行時のカレントディレクトリ基準です。絶対化や `~` の展開はこの処理では行いません（`strata_cli/cli.py:1476-1484`）。
- 省略時は `STRATA_TIMESKIP_DIR`、次に共通 state base の `time-skip` が使われます。POSIX では `$XDG_STATE_HOME/strata/time-skip`（未設定なら `~/.local/state/strata/time-skip`）、Windows では `%LOCALAPPDATA%\Strata\time-skip`（未設定ならユーザープロファイル下の `AppData\Local\Strata\time-skip`）です（`strata_cli/cli.py:1479-1484`; `strata_control/paths.py:13-21`）。
- 空文字列は parser では拒否されませんが、実行時の truthiness 判定で未指定と同じ扱いになり、環境変数または既定値へフォールバックします（`strata_cli/cli.py:1476-1484`）。重複指定時の扱いは parser の通常の argparse 動作に委ねられ、独自の処理はありません。

## 実行時の動作

`status` 専用 parser が `--state-dir` を登録し、Timeskip のディスパッチでこのパスを使って `TimeSkipStore` を作ります。その後 `run_id` を使って `run.json` を読み、`--output human` では run ID、状態、workspace、prompt、checkpoint、attempt、decision を表示します。`--output json` では `{ "schema_version": 1, "ok": true, "run": ... }` の JSON を stdout に出します（`strata_cli/cli.py:371-374,1474-1485,1500-1522`）。

## 適用条件と副作用

- このオプションは `strata timeskip status` の引数であり、隣接する `timeskip run`、`list`、`apply` の同名オプションとはそれぞれのコマンド parser で独立しています（`strata_cli/cli.py:352-393`）。
- 指定先に関わらず、store の生成時に `mkdir(parents=True, exist_ok=True)` が呼ばれるため、ディレクトリがなければ status 読み取りのために作成します。run データ自体は `status` 経路では書き換えません（`strata_control/time_skip.py:695-700`; `strata_cli/cli.py:1485,1500-1522`）。
- 指定先は `run_id` の保存先を切り替えるだけです。run の中身を検索したり、既定ディレクトリとマージしたりはしません（`strata_control/time_skip.py:375-379,715-716`）。

## 出力とエラー

- `run.json` がない場合、`TimeSkipError` の「no Time-skip run `<run_id>`」を返します。human 出力では `strata: ...` を stderr に出し終了コード 2、JSON 出力では `ok: false` とエラーを stdout に出し終了コード 2 です（`strata_control/time_skip.py:374-379`; `strata_cli/cli.py:1500-1506,527-533`）。
- state directory の作成やファイル読み取りで通常の `OSError` が発生した場合、CLI はファイル操作エラーとして終了コード 6 を返します。`PermissionError` は既知のユーザーデータ領域の修復を試みて一度コマンドを再実行し、再発時は終了コード 5 を返す分岐があります（`strata_control/time_skip.py:698-700,375-379`; `strata_cli/cli.py:2085-2104,2176-2183,519-524`）。不正 JSON は `ValueError` 経路で終了コード 2 になります（`strata_control/time_skip.py:379`; `strata_cli/cli.py:2166-2173`）。

## 根拠

- `strata_cli/cli.py:371-374` — `timeskip status` の parser と `--state-dir` 定義。
- `strata_cli/cli.py:1467-1485` — 明示値、環境変数、既定 state directory の選択と store 初期化。
- `strata_cli/cli.py:1500-1522` — status 読み取り、エラー処理、human/JSON 出力。
- `strata_control/paths.py:13-21` — POSIX/Windows の state base。
- `strata_control/time_skip.py:374-379,695-716` — run JSON の読み込み、保存先 directory の作成、run 検索。
- `strata_cli/cli.py:2085-2104,2166-2183,527-542` — PermissionError の再試行、共通エラー・成功出力と終了コード。
