# `--help`（alias: `-h`）

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata split-engine apply` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`apply` サブコマンドの使い方と、この parser に登録されたオプションを表示します。`--config` が必須であること、`--out` と出力形式 `--output` が使えることを確認できます。

## 使い方

```sh
strata split-engine apply --help
```

短縮形も同じ parser に用意されています。

```sh
strata split-engine apply -h
```

help action は parser の引数処理中に終了するため、必須の `--config FILE` を付けずにヘルプを表示できます。

## 値と既定値

値を取りません。Python `argparse` の `ArgumentParser` は既定で `-h` と `--help` の help action を追加し、ここでは `add_help=False` による無効化はありません。`strata split-engine apply` の parser には `--config FILE`（必須）、`--out FILE`、`--output {human,json}`（既定値 `human`）が宣言されているため、これらがヘルプの対象です。

## 実行時の動作

`strata_cli.cli.main()` は parser を作り、`parse_known_args()` でコマンドラインを解析します。標準 help action が呼ばれると usage と説明を標準出力へ表示して status 0 で終了し、以降の `extras` 処理や `_run()` への dispatch に進みません。そのため `split_cmd.run()`、設定 JSON の読み込み、split-engine の適用判定、`--out` への書き込みは実行されません。

ただし、CLI 全体の `main()` は parser の解析より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows で実行プロセスの token に既定 owner / DACL を設定する処理で、非 Windows では何もしません。これは help 固有の処理ではなく、help action が起きる前の共通初期化です。

## 適用条件と副作用

この help は `strata split-engine apply` parser に属します。`strata split-engine --help` は親コマンドの help、`strata --help` はトップレベルの help であり、別のスコープです。

help 自体は run config や出力ファイルを変更せず、split engine の判定や GPU 検出を実行しません。Windows では前述の共通初期化がプロセス token の既定セキュリティ設定を行います。

## 出力とエラー

標準 help action は usage / オプション説明を標準出力に表示して終了コード 0 で終了します。通常の引数解析で不明な引数が残った場合は、`main()` が `ap.error()` を呼び、argparse の usage とエラーを表示して終了します（終了コード 2）。このエラー経路は help action の出力ではありません。

## 根拠

- `strata_cli/cli.py:40-45` — root parser の生成とサブコマンド parser 群の登録。
- `strata_cli/cli.py:172-175` — `split_cmd.add_parser()` を root parser に登録。
- `strata_cli/split_cmd.py:16-22` — `split-engine apply` parser と `--config`、`--out`、`--output` の宣言。parser 作成時に `add_help=False` は指定されていない。
- `strata_cli/cli.py:2244-2259` — 共通初期化、引数解析、未知引数のエラー処理。
- `strata_cli/cli.py:2156-2158` — 通常実行時に `split_cmd.run()` へ dispatch する箇所。
- `strata_control/private_files.py:349-358` — `adopt_user_defaults()` の目的と Windows 以外での no-op。
