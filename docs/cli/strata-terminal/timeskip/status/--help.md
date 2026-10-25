# `strata timeskip status --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip status` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。`status` の使い方、位置引数、オプションを表示する。 |

## 役割

`status` サブコマンド用のヘルプを表示します。`status` parser は `argparse` の `add_parser()` で作られ、標準の help action を無効にしていません。そのため `--help` と `-h` は同じ標準 action の別名です（`strata_cli/cli.py:371-374`）。

## 使い方

```sh
strata timeskip status --help
```

このオプションは `strata timeskip --help` や他のサブコマンドのヘルプとは別スコープです。索引では `timeskip/status` の parser に対応する文書として登録されています（[CLI 索引](../../../README.md)）。

## 値と既定値

値は不要です。ヘルプの対象 parser には必須位置引数 `run_id`、`--state-dir`（既定値 `None`）、`--output`（`human` または `json`、既定値 `human`）が登録されています（`strata_cli/cli.py:371-374`）。ヘルプ表示ではこれらの値は読み込まれません。

## 実行時の動作

トップレベルの `parser()` は標準の `argparse.ArgumentParser` を作り、`timeskip` の下に必須のサブコマンド parser 群を登録します。`status` parser に `--help` を追加する個別実装はなく、標準の自動追加に任せています（`strata_cli/cli.py:40-46,348-374`）。

`main()` は parser を生成して `parse_known_args()` を呼びます。標準 help action がヘルプを表示して終了するため、通常の `_run()` と `_timeskip()` の `status` 処理へは進みません。従って run の保存領域を開いたり、run の状態を取得したりはしません（`strata_cli/cli.py:2217-2237,2147-2150,1467-1506`）。

ただし parser の生成・解析より前に `private_files.adopt_user_defaults()` が呼ばれます。これは Windows ではプロセスの既定 owner と DACL の設定を試み、失敗時は `False` を返し、Windows 以外では効果がありません（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389`）。

## 適用条件と副作用

`strata timeskip status` を選択したときのコマンド固有ヘルプです。ヘルプ action 自体は run のデータや workspace に変更を加えません。Windows では前述の共通初期化がプロセスの既定 owner/DACL を変更する場合があります。

## 出力とエラー

標準 `argparse` の help action が usage と `status` parser に登録された引数を標準出力へ表示し、終了コード `0` で終了します。出力の折り返しは端末幅等に依存します。

`--help` を付けず `run_id` を省略すると、必須位置引数の不足として parser がエラーを標準エラーへ出し、終了コード `2` で終了します（位置引数の登録: `strata_cli/cli.py:372`）。実際の同一 revision の CLI help 出力との照合は行っていません。

## 根拠

- `strata_cli/cli.py:40-46` — 標準 `ArgumentParser` とトップレベル subparser の生成。
- `strata_cli/cli.py:348-374` — `timeskip status` parser、必須 `run_id`、`--state-dir`、`--output` の定義。`add_help=False` は指定されていません。
- `strata_cli/cli.py:2217-2237` — 共通初期化、引数解析、通常実行への分岐。
- `strata_cli/cli.py:2147-2150,1467-1506` — `_timeskip()` への dispatch と、ヘルプで呼ばれない `status` 実処理。
- `strata_control/private_files.py:349-389` — help 解析前に実行される Windows 向け owner/DACL 初期化。

調査対象 checkout は `git status --short --branch` で `main...origin/main` と確認し、未コミット変更はありませんでした。調査範囲はこの checkout のソースです。CLI help は実行せず、標準 `argparse` の動作と parser 定義を根拠にしています。
