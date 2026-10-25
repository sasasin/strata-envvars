# `strata models import --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。

## 概要

`strata models import` サブコマンドの使い方と、その parser に登録された引数を表示する組み込みヘルプオプション。`-h` は同じ動作の短縮別名です。トップレベルの `strata --help` や `strata models --help` とはスコープが異なります。`models import` parser は「既存の GGUF ファイル一式を採用せずにプレビューする」コマンドとして登録されています（`strata_cli/cli.py:141-161`）。

```sh
strata models import --help
strata models import -h
```

## 値・既定値・validation

- 値は取りません。`argparse.ArgumentParser` は既定で `-h` / `--help` を追加するため、個別の `add_argument` 宣言や値の既定値はありません（`strata_cli/cli.py:40-45,157-161`）。
- help action が実行されるとヘルプを表示して parser を終了します。通常のコマンド実行時に必須となる位置引数 `PATH` と `--plan` の検証には進みません。これらは `models import` parser に登録されています（`strata_cli/cli.py:157-161`）。
- 表示内容には、このサブコマンドで定義された `PATH`、必須の `--plan`、`--output {human,json}`（既定値 `human`）、および共通 one-shot option の `--json`、`--quiet` が含まれます（`strata_cli/cli.py:157-161,508-515`）。

## 効果・相互作用

ヘルプ action は usage と option 説明を表示して終了するため、`models.plan_import()` によるファイル調査や import plan の出力は行いません。実処理への dispatch は parse 完了後に `main()` から `_run()`、`_models()` を経て行われます（`strata_cli/cli.py:550-561,2119-2142,2217-2237`）。実処理では、問題があれば human 形式を stderr、JSON 形式を stdout に出して終了コード 5、問題がなければ plan を出力します（`strata_cli/cli.py:552-561`）。

ただし CLI の `main()` は parser を作る前に `private_files.adopt_user_defaults()` を呼びます。これは Windows では現在のプロセスの既定 owner / DACL を設定する処理で、POSIX では何もせず `False` を返します。そのため Windows 上のヘルプ呼び出しでもこのプロセス設定処理は先に試行されます（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-389`）。

## 出力と失敗経路

- 標準の `argparse` help action によりヘルプを標準出力へ表示し、終了コード 0 で終了します。`--help` と `-h` は同じ parser action です（`strata_cli/cli.py:40-45,157-161`）。
- help action が走らない通常の解析では、未知の引数は `main()` が `ArgumentParser.error()` に渡します（`strata_cli/cli.py:2223-2231`）。
- Windows のプロセス既定設定に関する処理は失敗時にも例外を送出しない実装ですが、その成否は help の表示内容に反映されません（`strata_control/private_files.py:349-389`）。

## 適用範囲と調査上の制約

索引上の対象は Terminal CLI の `strata models import` です。索引にはこの階層の `--help`（`-h` alias）が掲載されています（[`docs/cli/README.md`](../../../README.md)）。この文書は parser 定義と dispatch をソースで確認したもので、実行時の表示を別途起動して採取したものではありません。Release archive や Windows 上の実行環境での表示差は確認していません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser と標準 help 設定。
- `strata_cli/cli.py:141-161` — `models import` の parser、位置引数と option。
- `strata_cli/cli.py:508-515` — one-shot parser へ追加する `--json` / `--quiet`。
- `strata_cli/cli.py:550-561,2119-2142,2217-2237` — import 処理への dispatch と parse の順序。
- `strata_control/private_files.py:349-389` — Windows の既定 owner / DACL 設定と POSIX での no-op。
- `docs/cli/README.md:296-304` — コマンド階層と索引上の option scope。
