# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。引数 parser が自動で追加するヘルプ action。 |

## 役割

`strata tune plan` の usage と、このサブコマンドで受理するオプションを表示して終了します。`strata tune` やトップレベルの `strata` に対する `--help` とは別の parser scope です。

## 使い方

```sh
strata tune plan --help
```

`--engine`、`--backend`、`--model` などの必須引数を指定せずにヘルプを表示できます。

## 値と既定値

値を取りません。`argparse.ArgumentParser` を標準設定で生成しており、`add_help=False` は指定されていません。したがって `-h` と `--help` は同じヘルプ action の表記です。別の既定値はありません。

## 実行時の動作

ヘルプには `strata tune plan` の usage と、`--engine ENGINE`、`--backend {metal,cuda,hip,sycl,cpu}`、`--model MODEL`、`--objective`、`--trials`、`--time`、`--repeats`、繰り返し指定できる `--hold`、`--output {human,json}` が表示されます。`--engine`、`--backend`、`--model` は parser 上必須ですが、help action はそれらの値を要求する処理に進まずに終了します。

ヘルプ表示のために engine の問い合わせや tuning plan の生成は行いません。plan の実行処理は parser から戻った後に `_run` から `_tune` へディスパッチされた場合に行われます。

## 適用条件と副作用

この action は `strata tune plan` の parser に属します。`strata tune --help` は親コマンドのヘルプを表示します。

`main()` は parser の構築と引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows 以外では `False` を返して何もせず、Windows ではプロセスの既定 owner / DACL を設定しようとします。従って help action 自体は plan の実行やファイル生成をしませんが、Windows では CLI 起動時のこの前処理が先に走ります。

## 出力とエラー

同一 revision の CLI で `python strata.py tune plan --help` を実行すると、usage とオプション一覧が標準出力に表示され、終了コード 0 で終了しました。必要な `--engine` などを省略しても help が優先されます。

Strata 側は `parse_known_args()` の後に未知の引数が残った場合 `ArgumentParser.error()` を呼びます。これは help 表示ではなく入力エラー経路です。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser の生成。`argparse.ArgumentParser` に標準の help 設定を使用。
- `strata_cli/cli.py:395-412` — `tune` / `plan` の parser 階層と、この scope の引数定義。`plan` parser 自体に `--help` を無効化する指定はない。
- `strata_cli/cli.py:1632-1641,1715-1723` — `tune` の dispatch と plan 生成経路。通常の plan は `tuning.plan_tuning()` を呼ぶ。
- `strata_cli/cli.py:2217-2231` — CLI 起動時の前処理、引数解析、未知引数時の `ap.error()`。
- `strata_control/private_files.py:349-357` — `adopt_user_defaults()` が Windows 以外では効果を持たないこと。
- 補助確認: 同一 checkout の `python strata.py tune plan --help` 出力。ソース上の parser scope と一致。
