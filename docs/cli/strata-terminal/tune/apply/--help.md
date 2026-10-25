# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune apply` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata tune apply` の使い方と、そのサブコマンドに属する引数・オプションを表示して終了します。親コマンド `strata tune` のヘルプとは対象範囲が異なります。

## 使い方

```sh
strata tune apply --help
```

ソース checkout から実行する場合:

```sh
python strata.py tune apply --help
```

## 値と既定値

値は不要です。`--help` と `-h` は `argparse.ArgumentParser` の標準 help action です。適用サブパーサーの作成時に `add_help=False` は指定されていないため、両表記が使えます。独自の既定値や値検証はありません。表示対象の引数には位置引数 `job_id` と `--config`、`--model-path`、`--context`、`--state-dir`、`--output` が含まれます（parser 定義: `strata_cli/cli.py:461-470`）。

## 実行時の動作

CLI の parser は `prog="strata"` の `ArgumentParser` として作られ、`tune` の下に `required=True` のサブパーサー群を持ちます。その群に `apply` parser が登録されています（`strata_cli/cli.py:40-45,395-396,461-470`）。Python 標準の help action が usage と利用可能な引数を標準出力へ表示し、終了コード 0 で解析を終了します。

この終了は通常の引数解析中に起きるため、`main` が解析後に `_run` を呼ぶ処理や、`_run` 内で apply を dispatch する処理には進みません（`strata_cli/cli.py:2217-2237,1710-1712`）。したがって、help 表示のためにジョブを読み込んだり、設定ファイルを検索・変更したり、候補設定を検証したりはしません。

## 適用条件と副作用

ヘルプは apply サブコマンド専用です。`strata tune --help` は親コマンドのヘルプを表示します。

parser に入る前には CLI 共通初期化として `private_files.adopt_user_defaults()` が呼ばれます。POSIX ではこの関数は `False` を返して何もしません。Windows では、可能な場合にプロセスの既定所有者と既定 DACL を現在ユーザーに合わせます。これはプロセスの後続作成物に対する既定値であり、help action 自体が tuning の状態や設定ファイルを変更する処理ではありません（呼び出し: `strata_cli/cli.py:2217-2224`、動作: `strata_control/private_files.py:349-389`）。

## 出力とエラー

help action は標準出力へ apply の usage と parser に登録された引数の説明を表示し、終了コード 0 で終了します。`job_id` など必須引数の指定を省いていても help 表示で終了するため、apply の引数不足エラーや実行時エラーには進みません。実際に apply を実行した場合の失敗経路はこのオプションの動作範囲外です。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser の生成と標準 `argparse.ArgumentParser` の使用。
- `strata_cli/cli.py:395-396,461-470` — `tune` のサブコマンド階層と `apply` parser・表示対象引数。
- `strata_cli/cli.py:1710-1712,2217-2237` — apply dispatch と、引数解析後の実行経路。
- `strata_control/private_files.py:349-389` — 共通初期化から呼ばれる Windows のプロセス既定値設定と POSIX の no-op。
- `strata.py:1-4,30-43` — checkout から `python strata.py` で CLI を起動する入口。
