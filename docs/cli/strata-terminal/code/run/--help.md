# `strata code run --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code run` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。`argparse` が `code run` parser に標準追加するヘルプ action。 |

## 役割

`strata code run` の usage と、このサブコマンド parser が受け付けるオプションを表示して終了します。`--prompt-file` と `--policy` は通常の実行では必須ですが、`--help` を指定すると必須値を渡さずにヘルプを確認できます。

## 使い方

```sh
strata code run --help
strata code run -h
```

この revision のソース checkout では `python strata.py code run --help` でも同じ parser を確認できます。

## 値と既定値

値は不要です。`--help` と `-h` は同じ標準 help action です。parser に明示的な `add_help=False` の指定はなく、`code_sp.add_parser("run", ...)` で作成された `argparse` parser の標準動作により追加されます（`strata_cli/cli.py:498-504`）。

## 実行時の動作

このオプションは `run` parser のヘルプを表示し、通常のコマンド処理へ進まずに終了します。同 revision の CLI で確認した表示は `usage: strata code run [-h] --prompt-file PROMPT_FILE --policy POLICY [--output {jsonl}] [--quiet]` と `-h, --help` を含む options 一覧です。

表示対象は `run` parser に属する `--prompt-file`、`--policy`、`--output`、`--quiet` と help action です。親の `strata code` parser に定義された `--workspace`、`--resume`、`--quiet` は別スコープであり、`strata code run --help` の一覧には含まれません（`strata_cli/cli.py:494-504`）。

help action が通常終了するため、`_run()` の `code` 分岐には到達しません。同分岐は実行時に共有 Desktop harness component が未導入ならエラーコード `5` を返す実装ですが、`--help` 表示自体はこの利用可否を検査しません（`strata_cli/cli.py:2162-2164`）。

## 適用条件と副作用

Python CLI の通常の起動経路では、引数解析より前に `private_files.adopt_user_defaults()` が呼ばれます。POSIX ではこの関数は何も変更しません。Windows では、可能な場合にプロセス token の既定 owner と DACL を現在ユーザー向けに設定します。従って、`--help` は `code run` の作業処理を実行しませんが、Windows でのこの共通初期化は先行します（`strata_cli/cli.py:2217-2223`、`strata_control/private_files.py:349-389`）。

ソース checkout の entry point は、起動時に更新済み Control への handover を試みてから CLI を読み込みます。配布済み環境での handover 先やプラットフォーム固有の挙動は、この checkout の parser だけからは確定できません（`strata.py:30-43`）。

## 出力とエラー

確認した同 revision の checkout では、ヘルプ本文を標準出力に表示します。`--help` を指定しない通常実行では `--prompt-file` と `--policy` が必須です。未知の引数は `argparse` の parser error 経路になります（`strata_cli/cli.py:499-504`、`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:494-504` — 親 `code` と子 `run` parser の登録、必須引数、出力形式、子 parser 固有の `--quiet`。
- `strata_cli/cli.py:2217-2231` — 共通初期化の後に parser を作成して引数を解析する順序。
- `strata_cli/cli.py:2162-2164` — 通常の `code` 実行が共有 Desktop harness 未導入をエラーにする分岐。
- `strata_control/private_files.py:349-389` — Windows での process token の既定 owner / DACL 初期化と、POSIX では無効であること。
- `strata.py:30-43` — checkout entry point の handover と CLI 呼び出し順。
- 同 revision の補助確認: `python strata.py code run --help`。上記 parser 定義と `-h`、usage、表示オプションが一致することを確認。
