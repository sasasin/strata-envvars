# `strata components plan --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components plan` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし（フラグ） |

## 役割

`components plan` の構文と引数を表示します。これは Python `argparse` が各 parser に自動追加するヘルプアクションです。対象 parser は `components plan` で、トップレベルや他の `components` サブコマンドのヘルプとは別です（`strata_cli/cli.py:41-45,114-128`）。

## 使い方

```sh
strata components plan --help
```

短縮形も使えます。

```sh
strata components plan -h
```

## 値と既定値

値を取りません。`-h` は `--help` の短縮別名です。コマンド parser の生成には標準の `argparse.ArgumentParser` と `add_parser` を使い、独自の `add_help=False` 指定はありません。そのため標準のヘルプアクションが有効です（`strata_cli/cli.py:41,114-121`）。

ヘルプには位置引数 `manifest` と、`--backend`、`--target`、`--output {human,json}` が示されます。通常実行時は `manifest` が必要で、`--backend` と `--target` の既定値は `None`、`--output` は `human` です（`strata_cli/cli.py:122-128`）。ヘルプ表示では manifest の指定・読み込みは必要ありません。

## 実行時の動作

トップレベル parser が引数を解析します。`argparse` のヘルプアクションはヘルプを標準出力へ表示して正常終了するため、`main()` の後続 `_run()` には進まず、manifest の存在確認・互換性判定も実行しません（parser 定義: `strata_cli/cli.py:40-45,114-128`、解析箇所: `strata_cli/cli.py:2217-2225`、通常の `components plan` 処理: `strata_cli/cli.py:1966-1983,2129-2130`）。値の指定や他オプションとの組み合わせによる挙動の変更はありません。

## 適用条件と副作用

`components plan` の parser が構築できる環境で利用できます。ヘルプ表示だけではコンポーネント manifest を開かず、ダウンロード、展開、Strata 設定の変更を行いません。これらの作業をしない旨は通常実行の出力にも明示されています（`strata_cli/cli.py:2010`）。ただし `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows では以後このプロセスが作るファイルの所有者・既定 ACL を現在ユーザー向けに設定し、Windows 以外では何もしません（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389`）。既存ファイルを変更する処理ではありません。

## 出力とエラー

ヘルプ本文は標準出力に表示され、`argparse` の標準動作で終了コード `0` となります。`--help` 自体に値を付けた場合など、通常の parser エラーとなる入力の詳細な表示文面は Python の `argparse` によります。Strata 独自の `--help` 出力処理や独自終了コードは確認できません（`strata_cli/cli.py:41,2217-2225`）。

## 根拠

- parser の生成とサブコマンド階層: `strata_cli/cli.py:40-45,114-128`
- 引数解析からコマンド処理への経路: `strata_cli/cli.py:2217-2237`
- 通常の `components plan` 処理と読取専用出力: `strata_cli/cli.py:1966-2011,2129-2130`
- 起動前のユーザー既定値設定（Windows のみ）: `strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-389`
- 調査対象 checkout: `git rev-parse HEAD` は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main`（変更なし）。

同一 revision の CLI help は実行せず、parser 定義と `argparse` の標準ヘルプ機能に基づいて記述しました。ソース checkout 以外の配布バイナリ・Release artifact は調査していません。
