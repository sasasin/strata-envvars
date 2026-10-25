# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。Python `argparse` の既定 help action。 |

## 役割

`strata components rollback` の使い方と、そのコマンドで受理される引数を表示して終了します。rollback を実行するオプションではありません。コマンド固有の説明は「最後の update が保持した以前の engine version に戻す」です（`strata_cli/update_cmd.py:57`）。

## 使い方

```sh
strata components rollback --help
strata components rollback -h
```

## 値と既定値

値は不要です。`-h` は同じ help action の短縮別名です。`ArgumentParser` と subparser は `add_help=False` を指定せず生成されており、Strata 独自の help parser や値 validation はありません（`strata_cli/cli.py:40-45,114-116`、`strata_cli/update_cmd.py:42-59`）。

## 実行時の動作

rollback subparser は共通引数を登録した後、通常は `update_cmd.run()` の rollback 分岐から `updater.rollback_engine()` を呼びます（`strata_cli/update_cmd.py:30-39,57-59,185-196`、`strata_cli/cli.py:2135-2137`）。ただし `--help` が指定されると、argparse がその parser の help を表示して正常終了するため、この rollback 分岐には進みません。help のための feed 読み込み、rollback、ダウンロードは行われません。

表示対象の parser には `_common()` 由来の `--feed`、`--components-dir`、`--backend`、`--wait SECONDS`、`--force`、`--model-config RUN_CONFIG.json`、`--output {human,json,jsonl}` が登録されています（`strata_cli/update_cmd.py:30-39,57-59`）。これは同じ rollback parser の引数一覧であり、各引数の実行時効果はそれぞれのオプション文書を参照してください。

## 適用条件と副作用

通常の Python `argparse` help action は表示後に終了コード 0 で終了します。rollback の handler は実行されません。CLI の `main()` は parser 作成・引数解析の前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows では現在のプロセストークンの既定 owner と DACL の変更を試み、Windows 以外では `False` を返して何もしません（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-388`）。したがって、help 表示でもこの起動時初期化は先に実行されます。

## 出力とエラー

help 本文を標準出力に表示し、終了コード 0 で終了します（`argparse.ArgumentParser` の既定 help action。Strata 側で独自の出力処理は定義していません）。help を付けずに不正な引数を渡した場合は通常 parser の引数エラーとなり、`main()` は未知の余剰引数を `ap.error()` に渡します（`strata_cli/cli.py:2223-2231`）。この文書では、実行時のロケール・端末幅に依存する help 全文は固定していません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル `ArgumentParser` と `add_subparsers` の生成。
- `strata_cli/cli.py:114-116,139-140` — `components` 階層と update/rollback parser 登録。
- `strata_cli/update_cmd.py:30-39,57-59` — rollback parser と共通引数。help を独自登録していないこと。
- `strata_cli/cli.py:2217-2231` — parser より前の起動時処理と解析経路。
- `strata_cli/cli.py:2135-2137`、`strata_cli/update_cmd.py:163-196` — 通常実行時の dispatch と rollback handler。
- `strata_control/private_files.py:349-388` — Windows での既定 owner/DACL 調整。
