# `strata profile list --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の Strata checkout は `main`（`origin/main` 追跡）で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile list` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 値を取らない。使用法とこのコマンドの説明を表示する |

## 役割

`strata profile list` の使用法と、そのコマンドで受理されるオプションを表示して終了します。`profile list` の実行や保存 profile の読み込みは行いません。

## 使い方

```sh
strata profile list --help
strata profile list -h
```

## 値と既定値

`--help` と `-h` は `argparse` が各 `ArgumentParser` に自動追加する、値なしの help action です。Strata の parser では `argparse.ArgumentParser` に `add_help=False` を指定しておらず、`profile list` の parser も通常の `add_parser` で生成されています。そのため、このコマンドにも両表記が適用されます（`strata_cli/cli.py:40-41,69-76`）。

この parser に明示定義された通常オプションは `--output {human,json}`（既定値 `human`）です。さらに one-shot command 共通設定として `--json` と `--quiet` が後から追加されます（`strata_cli/cli.py:75-76,508-515`）。ただし `--help` を指定すると help action が解析中に表示・終了するため、これらの通常実行時の出力設定は処理されません。

## 実行時の動作

help action は使用法と parser の説明・引数ヘルプを標準出力へ表示し、終了コード `0` で parser を終了します。`main()` は `parse_known_args()` の後で通常コマンドを `_run()` に渡しますが、help action が先に終了するため、`profile list` の dispatch、`profiles.list_profiles()` 呼び出し、一覧整形は行われません（`strata_cli/cli.py:2223-2237,958-967`）。

## 適用条件と副作用

コマンドのサブパーサーを選んでから指定します。`strata profile --help` は `profile` 階層、`strata profile list --help` は `list` 階層のヘルプです。索引上もこの文書は `profile/list` の `--help` に対応します（[CLI 索引](../../../README.md)）。

help の解析より前に `main()` は `private_files.adopt_user_defaults()` を呼びます。これは Windows でプロセスの既定 owner と DACL をユーザー向けに設定する処理で、Windows 以外では `False` を返して何もしません。したがって Windows では、ヘルプ表示だけでもプロセスのトークン既定値に作用する場合があります。関数は失敗時に例外を送出せず `False` を返します（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-390`）。

## 出力とエラー

通常は使用法・ヘルプ本文を標準出力へ出して終了コード `0` です。help action は `main()` の後続処理より前に終了するため、`--quiet` や `--json` による通常コマンド出力への変換は適用されません。明示した位置引数や値は不要です。

## 根拠

- `strata_cli/cli.py:40-41` — 最上位 parser。`argparse.ArgumentParser` を既定設定で生成。
- `strata_cli/cli.py:69-76` — `profile` と `list` の parser、list の `--output` 定義。
- `strata_cli/cli.py:508-515` — `profile list` を含む one-shot parser に `--json` と `--quiet` を追加。
- `strata_cli/cli.py:2217-2237` — parser 構築前の Windows 用初期化、引数解析、および通常 dispatch への経路。
- `strata_cli/cli.py:958-967` — 通常の `profile list` 処理と一覧出力。help action ではここへ到達しない。
- `strata_control/private_files.py:349-390` — `adopt_user_defaults()` の Windows 条件とプロセストークン設定。

Strata の CLI help 自体は実行せず、同一 revision の parser 定義と起動経路を確認しました。`-h/--help` の標準出力・終了コードの説明は Python `argparse` の標準 help action に基づきます。
