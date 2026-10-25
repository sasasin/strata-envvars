# `strata profile show --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の Strata checkout は `main`（`origin/main` 追跡）で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile show` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 値を取らず、コマンドの使用法と引数・オプションを表示する |

## 役割

`strata profile show` の usage と、そのサブコマンドで使える引数・オプションを表示して終了します。`show` の通常処理や保存 profile の読み込みには進みません。この文書のスコープは `profile/show` の help です。`strata --help` と `strata profile --help` はそれぞれ異なる parser のヘルプです（[CLI 索引](../../../README.md)）。

## 使い方

```sh
strata profile show --help
strata profile show -h
```

## 値と既定値

`--help` と `-h` は Python `argparse` が各 `ArgumentParser` に自動追加する値なしの help action です。Strata の root parser は既定の `argparse.ArgumentParser` で作成され、`profile` と `show` も通常の `add_parser()` で構成されており、`add_help=False` は指定されていません（`strata_cli/cli.py:40-41,69-80`）。

表示対象の構文には位置引数 `name`、`--effective`、`--output {human,json}`（既定値 `human`）、one-shot 共通の `--json` と `--quiet` が含まれます。これらは `show` の構文に属する項目で、`--help` 自体が値を受け取るわけではありません（`strata_cli/cli.py:77-80,508-515`）。

## 実行時の動作

help action は引数解析中に `show` parser の usage とヘルプ本文を標準出力へ表示して parser を終了します。そのため通常実行時に必要な `name` を指定しなくてもヘルプを表示でき、profile の読込、検証、effective settings の計算には進みません。通常実行では `_run()` が `_profile_command()` を呼び、`show` は `profiles.load(a.name)` の結果を出力し、`--effective` が指定された場合に限り `_launch_plan()` も呼びます。help action はこの経路より前に終了します（`strata_cli/cli.py:958-968,1015-1020,2119-2128,2223-2237`）。

`--json` や `--quiet` を同じ呼び出しに含めても、help action が先に終了するため通常処理向けの JSON 出力切替や quiet 捕捉は行われません（`strata_cli/cli.py:2223-2248`）。

## 適用条件と副作用

`show` を選択した後に指定します。`strata profile --help` は profile 階層、`strata profile show --help` は show 階層のヘルプを表示します。help action 自体は profile ファイルを読み書きせず、effective launch plan も作りません。

ただし `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows でプロセスの既定 owner と default DACL をユーザー向けに設定しようとし、Windows 以外では何もしません。関数内の失敗は例外にならず `False` を返します（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-390`）。

`strata.py` を入口に使う場合、さらに parser より前に updater handover 判定があります。entrypoint の preflight は `serve` と `bench` だけを対象にするため、`profile show --help` では依存パッケージ検査をしません（`strata.py:14-27,30-43`）。

## 出力とエラー

通常は usage と `show` parser のヘルプ本文を標準出力に表示して終了コード `0` です。help action が parser を終了するため、通常実行で必要な位置引数 `name` は不要です。`--help` の表記誤りや、help action に到達する前に発生する引数解析エラーは argparse のエラー経路になります（終了コード `2`）。

## 調査範囲

指定 commit の parser 定義、通常処理への dispatch、profile show の処理と起動前処理をソースで確認しました。同一 revision の CLI `--help` は実行していません。ヘルプ本文の表示・終了動作は Python `argparse` の標準 action に基づきます。Windows の token owner / default DACL 設定の実際の成否、およびインストール済み bundle や Release artifact の挙動は実機確認していません。

## 根拠

- `strata_cli/cli.py:40-41,69-80` — root、profile、show parser と位置引数、`--effective`、`--output` の定義。
- `strata_cli/cli.py:508-515` — one-shot parser に `--json` と `--quiet` を追加する処理。
- `strata_cli/cli.py:2217-2248` — `main()` の user-defaults 処理、引数解析、通常 dispatch と quiet 処理。
- `strata_cli/cli.py:958-968,1015-1020` — 通常の profile show 処理、profile 読込と `--effective` による計画生成。
- `strata_cli/cli.py:2119-2128` — parse 成功後に `_run()` から profile 処理へ渡す経路。
- `strata_control/private_files.py:349-390` — Windows 限定の `adopt_user_defaults()` と失敗時の挙動。
- `strata.py:14-27,30-43` — entrypoint の handover / preflight と、`serve` / `bench` 以外では依存検査をしない条件。
- `docs/cli/README.md:72-84` — `strata profile show` の階層と `--help`（`-h`）の索引リンク。
