# `strata timeskip list --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip list` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`list` サブコマンドの使い方を表示します。`strata timeskip` は必須のサブコマンドを持ち、その `list` parser は「記録済み run を一覧表示する」コマンドとして登録されています。標準 `argparse` の help が各 parser に自動設定されるため、このオプションは `list` parser に属し、`strata timeskip` 親 parser の help とは別です（`strata_cli/cli.py:40-45,348-350,376-378`）。

## 使い方

```sh
strata timeskip list --help
```

短縮形も使えます。

```sh
strata timeskip list -h
```

## 値と既定値

値を取りません。コマンド parser の生成時に `argparse` の標準 help action が有効になり、`-h` と `--help` が登録されます。独自の型変換、値の validation、既定値の設定はありません（`strata_cli/cli.py:40-45,376-378`）。

## 実行時の動作

help action が parser 処理中にヘルプを標準出力へ表示し、終了コード `0` で終了します。そのため通常の dispatch には進まず、`_timeskip()` が `TimeSkipStore` を作成したり、保存済み run を列挙したりしません。実際の一覧処理は help を指定しない `list` 呼び出しで行われます（parser の実行位置: `strata_cli/cli.py:2217-2231`、list dispatch: `strata_cli/cli.py:1467-1498`、store 初期化と列挙: `strata_control/time_skip.py:695-713`）。

## 適用条件と副作用

`list` の位置で `--help` または `-h` を指定します。ほかの `list` オプション（`--output`、`--state-dir`）の値や state directory の内容を使って一覧を出す処理には進みません（`strata_cli/cli.py:376-378,1485-1498`）。

CLI 起動時には parser 作成より前に `private_files.adopt_user_defaults()` が呼ばれます。この処理は Windows でのみ、以後プロセスが作成するファイルの既定 owner/DACL をユーザー向けに設定し、Windows 以外では何もしません。help 固有の run/state ファイル書き込みは確認できません（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-359`）。

## 出力とエラー

標準出力に `list` parser の usage と help を表示して終了コード `0` になります。`argparse` の parser error は通常 stderr に出て終了コード `2` ですが、これは help 表示そのものではなく、不正な引数を指定した場合の経路です。Strata の `main()` は parser 後に未認識引数を `ap.error(...)` へ渡します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:40-45` — 標準 `argparse.ArgumentParser` の生成とトップレベル parser。
- `strata_cli/cli.py:348-350` — `timeskip` と必須サブコマンド parser の登録。
- `strata_cli/cli.py:376-378` — `list` parser と同スコープの `--state-dir`、`--output`。
- `strata_cli/cli.py:2217-2231` — parser 実行、認識されない引数の処理。
- `strata_cli/cli.py:1467-1498` — 通常実行時の `list` 処理と出力。
- `strata_control/time_skip.py:695-713` — store の初期化時ディレクトリ作成と run の読み取り。
- `strata_control/private_files.py:349-359` — Windows での user default 設定条件。
