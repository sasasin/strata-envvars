# `strata ops set --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops set` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 値を取らないフラグ |

## 役割

`strata ops set` の使用法と、その parser に登録された位置引数・オプションを表示して終了します。`argparse.ArgumentParser` の標準 help action で、Strata の recipe 操作 handler には進みません。

## 使い方

```sh
python strata.py ops set --help
```

インストール済み CLI では `strata ops set --help`、短縮形では `strata ops set -h` と実行します。

## 値と既定値

`--help` は値を取りません。Python の `argparse.ArgumentParser` は `add_help=False` を指定しない限り `-h` と `--help` を自動登録します。このリポジトリのトップレベル、`ops`、`set` の parser はいずれも `add_help=False` を指定せず作成されているため、この位置では `--help` と `-h` が有効です（`strata_cli/cli.py:40-46,255-260`）。

## 実行時の動作

```text
strata ops set --help
```

`ops` は必須のサブコマンドを持ち、`set` parser は `name`、`--profile`、`--output {human,json}`、`KEY=VALUE`、`--plan` を登録します（`strata_cli/cli.py:255-277`）。その後、全 `ops` action に `--json` と `--quiet` も追加されます。したがって `set --help` に表示される対象には、これらの共通オプションも含まれます（`strata_cli/cli.py:508-515`）。

`main()` は引数解析後に `_run()` へ進む設計で、`_ops()` の `set` 分岐では recipe の提案値を作成し、`--plan` がなければ保存します（`strata_cli/cli.py:2217-2237,1391-1430`）。一方、標準 help action は help を出力して parser を終了するため、この呼び出しではその分岐・recipe 読み込み・保存は行われません。

## 適用条件と副作用

- この help の範囲は `strata ops set` の parser です。トップレベル `strata --help` や `strata ops --help` とは別の help です。
- help action による出力先は stdout、正常終了コードは 0 です。これは使用している Python `argparse` の標準動作で、Strata が独自の help 出力処理を追加している箇所はありません。
- CLI の `main()` は parser を作る前に `private_files.adopt_user_defaults()` を呼びます。POSIX では同関数は何も変更せず `False` を返し、Windows では現在のプロセストークンの owner / default DACL を設定しようとします。これは当該プロセス内の設定であり、`ops set --help` による recipe のファイル変更ではありません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-389`）。
- ソース checkout の `strata.py` は、通常は checkout 検出によりインストール済み Control への hand-over を行わず、この checkout の CLI を使います（`strata.py:30-43`; `strata_cli/handover.py:126-134`）。配布済み CLI の別 revision の表示内容はここでは調査していません。

## 出力とエラー

- 有効な `--help` / `-h` は parser の usage と説明を stdout に表示し、終了コード 0 で終了します。`--json` を同時に書いても help action が先に終了するため、JSON result にはなりません。
- 必須位置引数や `--profile` は通常実行では必要ですが、help action はそれらが不足していても help を表示して終了します（parser 定義: `strata_cli/cli.py:264-275`）。
- 不明なオプションなど parse error の場合は、`argparse` が usage とエラーを stderr に出し、終了コード 2 で終了します。`main()` は `parse_known_args()` の余分な引数を `ap.error()` に渡します（`strata_cli/cli.py:2223-2231`）。この場合も `_run()` や recipe handler には進みません。

## 根拠

- parser の生成と `ops set` の登録、必須引数・専用オプション: `strata_cli/cli.py:40-46,255-277`
- `ops` parser 群への `--json` / `--quiet` の追加: `strata_cli/cli.py:508-515`
- 引数解析から実行 handler へ進む条件: `strata_cli/cli.py:2217-2237`
- `ops set` の値提案、plan 時の非保存、通常時の保存: `strata_cli/cli.py:1391-1430`
- 起動時の user default 調整: `strata_control/private_files.py:349-389`
- source checkout の hand-over 条件: `strata.py:30-43`; `strata_cli/handover.py:126-134`
