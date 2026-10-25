# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata install` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata install` の利用方法を表示して終了します。`argparse` のサブコマンド parser が持つ標準ヘルプで、`--update` と、`setup.py` に渡される位置引数 `setup_args` を含むこのコマンドの usage を表示します。トップレベルの `strata --help` とは対象スコープが異なります。

## 使い方

```sh
python strata.py install --help
```

インストール済みの `strata` では次の形式です。

```sh
strata install --help
```

## 値と既定値

値は不要です。省略時にヘルプは表示されません。`-h` は同じ parser action の短縮別名です。`strata_cli.cli.parser()` は `argparse.ArgumentParser` と `add_subparsers()` を通常の設定で作り、`install` をそのサブコマンドとして登録しています。`argparse` の標準設定により、コマンド parser は `-h` / `--help` を自動で受理します。

## 実行時の動作

ヘルプ action は引数解析中に usage/help を標準出力へ書き、終了コード `0` で parser を終了します。そのため通常は `_run()` や `_install()` に到達せず、`setup.py` の起動、インストーラー引数の転送、ダウンロードは行われません。`--update` は別の `strata install` オプションであり、ヘルプ表示のために指定する必要はありません。

CLI 起動時には引数解析より前に hand-over 判定が行われます。ソース checkout では hand-over を行わない分岐があります。インストール済み Terminal でより新しい Control が登録されている場合は、その Control が同じ引数で起動してヘルプを表示することがあります。Windows では `main()` が引数解析前にプロセス token の既定 owner/DACL を設定しようとしますが、これはファイルのインストールや変更ではありません。

## 適用条件と副作用

このヘルプは `strata install` 専用です。インストール済み環境では起動前の hand-over 条件により、現在の実行ファイルではなく登録された新しい Control が表示を担当する場合があります。ソース checkout では `strata.py` が hand-over を抑止します。

通常の parser 経路での副作用は usage/help の出力と正常終了です。`_install()` が行う installer の有無の確認や `setup.py` の子プロセス起動には進みません。ヘルプ表示前の import、hand-over 判定、および Windows の token 設定試行は CLI 共通の起動処理です。

## 出力とエラー

usage とオプション説明を標準出力へ表示し、終了コード `0` で終了します。parser の import や起動前の hand-over 自体が失敗する場合の診断は、このオプション固有の失敗経路ではありません。ソース上で `install --help` 固有の検証エラーやファイル出力は確認できません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser とサブコマンド parser の登録。
- `strata_cli/cli.py:190-196` — `install` parser、`--update`、委譲先向け `setup_args` の定義。
- `strata_cli/cli.py:2064-2082` — `_install()` の installer 解決と `setup.py` 子プロセス起動。
- `strata_cli/cli.py:2119-2124` — `_run()` から `_install()` への dispatch。
- `strata_cli/cli.py:2217-2237` — parser 生成、引数解析、解析後の dispatch。
- `strata.py:30-43` — 起動前処理と CLI `main()` の呼び出し。
- `strata_cli/handover.py:27-29,126-153` — checkout 判定と新しい Control への hand-over。
- `strata_control/private_files.py:349-385` — Windows での process token 既定 owner/DACL 設定。
- `docs/cli/README.md:375-380` — 索引上のコマンド階層と `--help` / `-h` のリンク。
