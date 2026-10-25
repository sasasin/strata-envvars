# `strata presets off --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets off` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。コマンドの使用法と help を表示する |

## 役割

`strata presets off` の引数と共通オプションを表示する。`--help` と `-h` はこのサブコマンド parser の help action であり、トップレベルや別の `presets` サブコマンドの help とは別スコープである。

## 使い方

```sh
strata presets off --help
strata presets off -h
```

## 値と既定値

値は不要で、`--help` と `-h` は同じ help action の長短表記である。`strata presets off` parser は `argparse` の `add_parser()` で作られ、help を無効化する指定や独自の help action はないため、Python `argparse` の既定 help option が使われる（`strata_cli/tune_commands.py:80`）。

## 実行時の動作

`presets` の下に必須のサブコマンド群が登録され、その一つとして `off` parser が作られる。各 preset サブコマンドには共通 helper が `--output {human,json}`（既定 `human`）を追加し、`off` にはさらに必須位置引数 `target` がある（`strata_cli/tune_commands.py:51-55`, `strata_cli/tune_commands.py:80-81`）。したがって通常の help には `target` と `--output` が引数として現れる。

トップレベル parser は `strata presets` parser 群を登録した後、`parse_known_args()` で引数を解析する（`strata_cli/cli.py:486-489`, `strata_cli/cli.py:2223-2225`）。help action は解析中に表示して正常終了するため、`_run()` によるコマンド dispatch や preset の変更処理には進まない（`strata_cli/cli.py:2236-2237`, `strata_cli/cli.py:2151-2153`）。このため `--output json` を付けても help action の表示形式を JSON に切り替えるものではない。

## 適用条件と副作用

引数解析時に利用できる。help の表示自体は preset を読み書きしない。CLI の `main()` は parser を作る前に `private_files.adopt_user_defaults()` を呼ぶが、この関数は Windows 以外では `False` を返して何もしない。Windows では現在プロセスの既定 owner / DACL を設定しようとする（`strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-358`, `strata_control/private_files.py:372-390`）。

## 出力とエラー

標準 `argparse` の help action により、parser が生成する使用法・説明・引数一覧を標準出力へ表示し、終了コード 0 で解析を終了する。表示幅などによる具体的な整形結果は実行環境に依存し、この調査では CLI を起動して出力を採取していない。

`--help` 自体に値は不要。未知の引数が残る通常の解析経路では `main()` が `ap.error()` を呼ぶため、標準 `argparse` の parser error（usage とエラーを表示して終了コード 2）になる（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/tune_commands.py:49-55`, `strata_cli/tune_commands.py:80-81` — `presets` の parser 階層、共通 `--output`、`off` と必須 `target` の定義。
- `strata_cli/cli.py:486-489`, `strata_cli/cli.py:2217-2225` — parser 登録、起動時処理と引数解析。
- `strata_cli/cli.py:2226-2237`, `strata_cli/cli.py:2151-2153` — 余分な引数の処理と通常時のコマンド dispatch。
- `strata_control/private_files.py:349-390` — `adopt_user_defaults()` の Windows 条件と token owner / DACL 処理。

調査対象 checkout は `git status --short --branch` で `## main...origin/main` と確認し、表示された未コミット変更はなかった。CLI help の実出力は取得せず、parser 定義と `argparse` の標準動作から記述した。
