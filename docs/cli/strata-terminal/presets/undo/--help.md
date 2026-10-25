# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets undo` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし（フラグ） |

## 役割

`strata presets undo` の使い方と、このサブコマンドが受け取る引数・オプションを表示します。Strata CLI の各 parser は標準の `argparse.ArgumentParser` と `add_parser()` で構築され、独自の help action は追加されていません。そのため `--help` と `-h` は `argparse` の標準 action です（`strata_cli/cli.py:40-45`、`strata_cli/tune_commands.py:49-55,70-72`）。

## 使い方

```sh
python strata.py presets undo --help
```

インストール済み CLI では `strata presets undo --help` または `strata presets undo -h` を使います。

## 値と既定値

値は取りません。`-h` は同じ help action の短縮別名です。`undo` parser 固有の位置引数は `preset`（preset、または `--config` と併用する設定対象）で、固有オプションは `--config` です。`--output` は `presets` の各サブコマンドに共通し、選択肢は `human` / `json`、既定値は `human` です。これらは help の対象内容であり、`--help` 自体の値ではありません（`strata_cli/tune_commands.py:53-55,70-72`）。

## 実行時の動作

`argparse` が `strata presets undo` の parser から usage と説明、`preset`、`--config`、共通の `--output`、および help action を表示して終了します。help action は引数解析中に終了するため、`main()` の後続にある `_run()` と `presets_command()` には到達せず、preset の検索・undo・index 更新は行いません（`strata_cli/cli.py:2223-2237`、`strata_cli/cli.py:2151-2153`、`strata_cli/tune_commands.py:289-294,321-330`）。

ただし `main()` は parser の作成・解析より先に `private_files.adopt_user_defaults()` を呼びます。これは Windows ではプロセス token の既定 owner と DACL を設定しようとし、設定失敗を例外として伝えず `False` を返します。非 Windows では何も変更しません（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389`）。

## 適用条件と副作用

オプションは `strata presets undo` parser のみに適用されます。通常の help 表示は preset store のデータを読み書きせず、エンジン起動やチューニングも呼び出しません。上記の Windows token default 設定は parser より前に行われるため、help 表示にも適用されます（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389`）。

## 出力とエラー

標準 `argparse` の help action は usage/help を標準出力へ表示して終了コード `0` で終了します。通常の help 表示時に undo handler が返す成功・失敗メッセージは出力されません（parser の生成位置: `strata_cli/tune_commands.py:70-72`、handler の位置: `strata_cli/tune_commands.py:321-330`）。無効な引数など help 以外の parse error は `argparse` の parser error 経路になりますが、個別の Strata 独自処理は確認できません。

## 根拠

- `strata_cli/cli.py:40-45,487-489` — ルート parser と `presets` parser の登録。
- `strata_cli/tune_commands.py:49-55,70-72` — `presets undo` の parser、共有 `--output`、位置引数と `--config`。`add_parser()` は標準 help action を有効にしたまま使用。
- `strata_cli/cli.py:2217-2237` — parser 解析前の処理と、解析後の command dispatch。
- `strata_cli/cli.py:2151-2153`、`strata_cli/tune_commands.py:289-294,321-330` — undo handler の dispatch と実処理。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の OS 条件と Windows token 設定。

確認範囲は上記 revision の checkout 内の Python CLI 実装です。実行しての help 出力確認は行わず、標準 `argparse` の挙動と parser 定義を照合しました。個別の配布バイナリや異なる revision の挙動は調査対象外です。
