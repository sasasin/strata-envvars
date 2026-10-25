# `strata timeskip list`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip list` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/time_skip.py` |

## 役割

保存されている Time-skip run を読み取り、ID、状態、判定、prompt の一部を一覧にします。個別 run の記録やチェックポイントの詳細は `strata timeskip status RUN_ID` で確認します。run の内容を workspace に適用する操作は行いません。

## 使い方

```sh
# 既定の状態ディレクトリにある run を一覧表示
strata timeskip list

# 保存場所を指定して一覧表示
strata timeskip list --state-dir ./timeskip-state

# 機械処理向け JSON
strata timeskip list --output json
```

このサブコマンドは `strata timeskip` の下に登録され、親コマンドだけではなく `list` の指定が必要です。受け付ける個別オプションは `--state-dir`、`--output`、`--help`（alias: `-h`）です（`strata_cli/cli.py:348-350,376-378`）。オプションの詳細は [CLI 索引の timeskip list 節](../../../README.md) を参照してください。

## 表示と実行時の動作

- `--output` の既定値は `human`、指定可能な値は `human` と `json` です（`strata_cli/cli.py:376-378`）。
- human 出力では run がないと `no Time-skip runs recorded` を表示します。run がある場合は各行に ID の先頭12文字、state、decision の outcome（未設定なら `-`）、prompt の先頭48文字を表示します。状態のないレコードは `?` と表示されます（`strata_cli/cli.py:1491-1498`）。
- JSON 出力は `{ "schema_version": 1, "ok": true, "runs": [...] }` の形です。各要素には `id`、`state`、`workspace`、`prompt`、`started_at`、`finished_at`、`decision` のフィールドが含まれます。個々の `run.json` にフィールドが欠けている場合、その値は `null` になります（`strata_cli/cli.py:1487-1490,535-542`、`strata_control/time_skip.py:702-713`）。
- run の保存先は `--state-dir`、環境変数 `STRATA_TIMESKIP_DIR`、OS のユーザー状態領域配下の `strata/time-skip` の順で決まります。POSIX では `$XDG_STATE_HOME/strata/time-skip`（`XDG_STATE_HOME` 未設定時は `~/.local/state/strata/time-skip`）、Windows では `%LOCALAPPDATA%\Strata\time-skip`（未設定時はユーザープロファイル下の `AppData\Local\Strata\time-skip`）です（`strata_cli/cli.py:1476-1485`、`strata_control/paths.py:13-21`）。
- 保存ディレクトリ直下の項目を名前順に調べ、`run.json` がある項目だけを列挙します。表示順は開始時刻ではなくディレクトリ名の辞書順です（`strata_control/time_skip.py:702-713`）。

## 副作用と失敗経路

一覧自体は run や workspace の内容を書き換えません。ただし、対象 store の初期化時に状態ディレクトリが存在しなければ作成します。そのため、まだ run がない状態でも初回実行でディレクトリが作られます（`strata_cli/cli.py:1476-1485`、`strata_control/time_skip.py:698-700`）。

`run.json` の読み込み時にファイル操作エラーまたは JSON 構文エラーが起きた項目は、エラー表示せず一覧からスキップします（`strata_control/time_skip.py:704-713`）。一方、状態ディレクトリの列挙・作成などで `OSError` が起きると、CLI 共通処理がエラーを標準エラーへ表示し、終了コード `6` を返します。`--output json` の場合は共通エラー JSON になります（`strata_cli/cli.py:2176-2183`）。引数の値が選択肢外の場合などは argparse の usage/error 経路です。

## 関連文書

- [`strata timeskip` 概要](../README.md)
- [`strata timeskip apply` 概要](../apply/README.md)
- [CLI 文書索引](../../../README.md)

## 根拠

- Strata `strata_cli/cli.py:348-350,376-378` — timeskip/list の parser、必須サブコマンド、オプション、既定値。
- Strata `strata_cli/cli.py:1476-1498,2147-2150` — state directory の選択、出力分岐、コマンド dispatch。
- Strata `strata_control/time_skip.py:695-713` — 状態ディレクトリ作成、run.json 列挙、破損・読取失敗項目のスキップ、返却フィールド。
- Strata `strata_cli/cli.py:527-542,2176-2183` — 共通の JSON 成功・エラー形式と OSError のエラー処理。
- Strata `strata_control/paths.py:13-21` — OS ごとのユーザー状態領域。
- `docs/cli/README.md:700-706` — 対象リンクと timeskip/list のオプション scope。

調査は上記 commit の checkout 内ソースに基づきます。同一 revision の `--help` 出力と Release 配布物は確認していないため、配布版との相違は調査範囲外です。
