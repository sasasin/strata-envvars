# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile validate` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。検証対象の profile 名は位置引数 `name` で指定する。 |

## 役割

`strata profile validate` の使い方と、そのサブコマンドで受理される引数・オプションを表示して終了します。ヘルプ表示だけを行い、profile や参照先 run config の検証は実行しません。

## 使い方

```sh
strata profile validate --help
strata profile validate -h
```

`name` は通常の検証実行では必須ですが、help 表示では省略できます。help はサブコマンド固有の parser で処理されます。

## 値と既定値

`--help` と `-h` は値を取りません。Strata はこの parser に help action を独自定義しておらず、`argparse` の標準 help action を使用します。validate parser には位置引数 `name` と `--output {human,json}`（既定値 `human`）があり、共通 one-shot オプションとして `--json` と `--quiet` も追加されます。これらの引数は help の説明に列挙されますが、help action が終了するため、その値を用いた検証処理には進みません。

## 実行時の動作

`profile` 配下で `validate` parser を作成し、`name` と `--output` を定義しています。全ての one-shot profile parser には後から `--json` と `--quiet` が追加されます。各 `argparse` parser の標準 help action が `--help` / `-h` を受けて usage と help 文を stdout に表示し、正常終了します。`main()` は引数解析後に `_run()` を呼びますが、help action は解析中に終了するため、profile の読み込み、参照先 config の検査、検証結果の出力には到達しません。

## 適用条件と副作用

このオプションは `strata profile validate` の parser に対するもので、トップレベルや他のサブコマンドの help とは別スコープです。`main()` は parser の作成・解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows では現在のプロセスの既定ファイル所有者と ACL を現在ユーザー向けに設定しようとし、POSIX では何もしません。したがって Windows では help 表示前にこのプロセス内の token 既定値へ作用する場合があります。help による profile ファイルの読み書き、run config 検証、サーバー起動は行われません。

## 出力とエラー

正常時は `argparse` が生成するコマンド usage と説明を stdout に表示して終了コード 0 で終了します。help 出力の文言・レイアウトは Python `argparse` の生成結果です。help 以外の不正な引数は CLI の検証処理に渡らず、`argparse` の usage/error 表示と終了コード 2 の経路になります。help 表示そのものは `strata profile validate` の成功・失敗結果を出しません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser の生成と `argparse` の使用。
- `strata_cli/cli.py:69-83` — `profile` / `validate` の階層、位置引数 `name`、`--output` の choices と既定値。`add_parser()` に独自 help action や `add_help=False` の指定はありません。
- `strata_cli/cli.py:508-515` — profile validate parser を one-shot 共通設定に含め、`--json` と `--quiet` を追加。
- `strata_cli/cli.py:958-968,1015-1020` — 通常の profile 処理では最初に profile をロードし、validate の場合は `_launch_plan()` を実行してから成功結果を出力。
- `strata_cli/cli.py:2119-2129,2217-2237` — `_run()` から profile 処理への dispatch と、起動時の権限既定値処理・引数解析の順序。help action による終了は解析中のため dispatch より前。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` は Windows で token の既定 owner / DACL を設定しようとし、失敗時も例外を外へ送らず、Windows 以外では何もしない。

この checkout では `strata profile validate --help` を実行していません。`main()` が引数解析前に上記の Windows token 処理を呼ぶためです。表示文言そのものではなく、同一 revision の parser 定義と標準 `argparse` の動作を根拠にしています。
