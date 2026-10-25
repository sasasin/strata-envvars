# `strata bench --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata bench` の利用法と利用可能なサブコマンドを表示して終了します。ベンチマークを実行するオプションではありません。たとえば次のように呼び出します。

```sh
strata bench --help
strata bench -h
```

## 値と既定値

値は不要です。`strata_cli/cli.py` は `bench` parser を `add_parser("bench", ...)` で作成し、`--help` を個別に追加していません。`argparse.ArgumentParser` の標準設定（`add_help=True`）により `--help` と `-h` が生成されます。親 parser に独自の help formatter や help action は設定されていません（`strata_cli/cli.py:40-45,291-292`）。

## 実行時の動作

ヘルプには `bench` の説明と、`run`、`cancel`、`report`、`compare` のサブコマンド名・短い説明が表示されます。各サブコマンドの固有オプションは親のヘルプには展開されません。たとえば `run` の引数を確認するには `strata bench run --help` を使います。親と子は別々の parser であり、`bench` の subparser は `required=True` です（`strata_cli/cli.py:291-296,335-347`）。

ヘルプ action は引数解析中にヘルプを標準出力へ書き、正常終了します。そのため `strata bench --help` はサブコマンド指定を要求する通常の解析をそこで終え、`_run` のベンチマーク処理へ進みません。対して `strata bench` だけでは必須サブコマンドがないため parser error となり、usage/error を標準エラーへ出して終了コード 2 になります。これは `argparse` の標準 `--help` / required subparser 動作であり、Strata 独自のヘルプ処理ではありません（parser の必須指定: `strata_cli/cli.py:292`、解析と実行への分岐: `strata_cli/cli.py:2217-2237`）。

## 適用条件と副作用

このヘルプは `strata bench` のスコープです。`run`、`cancel`、`report`、`compare` の実行時オプションは各サブコマンド側で解析され、親の `--help` では値の検証やベンチマークの実行、レポートの読み書き、サーバーへの接続を行いません（`strata_cli/cli.py:291-347,1129-1189`）。

ソース checkout の `python strata.py bench --help` では、ヘルプ解析より前に `strata.py` の旧 updater 判定・handover 判定と `bench` 用 package preflight が実行されます。preflight は必要 package の存在確認のみで、自動インストールはしません（`strata.py:14-27,30-42`）。さらに CLI の `main` は parser 作成前に `adopt_user_defaults()` を呼びます。この関数は Windows では現在のプロセス token の既定 owner / DACL を調整し、Windows 以外では何もしません。したがってヘルプ action 自体はベンチマーク用のファイルやネットワーク処理を行いませんが、エントリーポイント全体ではこれらの前処理があります（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-385`）。

## 出力とエラー

成功時はヘルプを標準出力に表示して終了コード 0 です。`--help` / `-h` 自体に値は不要で、ヘルプを指定せず未知の引数を渡した場合は `main` が `ap.error(...)` を呼び、argparse の usage とエラーが標準エラーに出ます（終了コード 2）。必須の子コマンドを省略した場合も parser が解析エラーにします（`strata_cli/cli.py:292,2223-2231`）。

`strata.py` 経由で `bench` を指定したときに必要 package が不足していれば、help parser に到達する前に不足 package の案内を標準エラーへ出し、終了コード 5 で終わります。これは help option 固有の validation ではなく、エントリーポイントの事前確認です（`strata.py:14-27,39-41`）。

## 根拠

- `strata_cli/cli.py:40-45,291-292` — 親 parser の生成、`bench` の parser と必須サブコマンド parser。
- `strata_cli/cli.py:293-347` — 子 parser と、親ヘルプに含まれない各サブコマンド固有 option の定義。
- `strata_cli/cli.py:1129-1189` — bench の実行分岐。ヘルプ終了後には到達しない。
- `strata_cli/cli.py:2217-2237` — `main` の前処理、引数解析、エラー処理、実行への分岐。
- `strata.py:14-27,30-42` — checkout の entry point、handover 判定、bench 用 package preflight。
- `strata_control/private_files.py:349-385` — Windows の process token の既定 owner / DACL を設定する処理。
