# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。Python `argparse` の標準ヘルプ action。 |

## 役割

`strata connection` の使い方と、直下で利用できるサブコマンドを表示する。親コマンドの parser に付くヘルプなので、`create`、`show`、`list`、`set` の選択に迷ったときに使う。各サブコマンド固有のオプションを確認する場合は、そのサブコマンドに `--help` を付ける。

## 使い方

```sh
strata connection --help
strata connection -h
```

この revision の parser から表示される usage は `strata connection [-h] {create,show,list,set} ...`。説明には `create`（名前付き接続の保存）、`show`（資格情報を表示せず保存済み接続を表示）、`list`、`set`（URL、prefix、資格情報参照の編集）が列挙される。確認には対象 revision の `strata_cli.cli.parser()` を使って `connection --help` を渡した。これは help 出力の確認であり、サブコマンドの処理は実行しない。

## 値と既定値

値は不要。`-h` は `--help` の短縮別名で、どちらも `connection` 親 parser の標準 help action を呼び出す。help 表示用の追加設定や独自 validation はこの parser にない。親 parser のサブコマンドは `required=True` だが、help action はサブコマンドが選ばれていなくても usage を表示して終了する。

## 実行時の動作

ヘルプには上記の4サブコマンドと、共通の `-h, --help` が表示される。help action が parser を終了するため、通常の `connection` 実行処理へは進まず、接続情報の読込・保存やネットワーク通信は行わない。`connection` の親 parser は `monitor_commands.add_connections()` で登録され、サブコマンド一覧はその直下の subparser から作られる。

## 適用条件と副作用

ヘルプ自体にファイルや接続先への副作用はない。ただし通常の `strata` エントリポイントでは、parser の解析前に `private_files.adopt_user_defaults()` が呼ばれる。この関数は Windows でプロセスの既定 owner と DACL を設定しようとし、Windows 以外では `False` を返して何もしない。これは `--help` 固有の動作ではなく、CLI 起動時の前処理である。対象 revision の parser を直接呼び出して確認した help 出力は、この CLI 前処理を通していない。

## 出力とエラー

確認した出力先は標準出力で、終了は成功（`argparse` の標準 help action は status 0 で終了）となる。help action がない通常の `strata connection` 呼び出しでは、必須サブコマンドがないため parser の usage/error 経路に入る。標準的な未知引数・構文エラーも `argparse` によるエラー表示と status 2 の経路であり、サブコマンド処理には入らない。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection` parser、必須サブコマンド、直下の `create` / `show` / `list` / `set` の定義。明示的な `-h` / `--help` 定義がないため、標準 help action が適用される。
- `strata_cli/cli.py:40-45` — トップレベル parser を `argparse.ArgumentParser(prog="strata", ...)` で構築。
- `strata_cli/cli.py:488-493` — `add_connections()` を `strata` のトップレベル subparser に登録。
- `strata_cli/cli.py:2217-2224` — CLI の `main()` が parse 前に Windows 向け user defaults 処理を呼び、続いて parser を解析。
- `strata_control/private_files.py:349-385` — `adopt_user_defaults()` の OS 条件と Windows token owner / default DACL 設定。
- `strata.py:30-42` — ソース checkout の実行入口で handover 判定、preflight 後に `strata_cli.cli.main()` へ委譲。
- `docs/cli/README.md:1033-1037` — 索引上の `strata connection` と、この `--help` 文書の配置。
