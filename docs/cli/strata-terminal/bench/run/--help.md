# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata bench run` 専用の使用方法と、この parser に登録された引数の説明を表示して終了します。Terminal CLI の他の階層にある `--help` とは別スコープです。

## 使い方

```sh
strata bench run --help
```

短縮形は `strata bench run -h` です。どちらも同じ help action です。

## 値と既定値

値は不要です。`strata_cli.cli` は各 `argparse.ArgumentParser` の既定 `add_help=True` を変更しておらず、`bench run` parser も `add_parser("run", ...)` で作られるため、Python `argparse` が `-h` と `--help` を同じヘルプ表示 action として自動追加します。`bench run` の parser には通常引数の既定値や validation とは別に、help action が用意されています（`strata_cli/cli.py:40-45, 291-315`）。

## 実行時の動作

トップレベル parser は `strata` を表示名とし、`bench` の必須サブコマンドとして `run` を登録します。`run` parser の help には、排他的な `--profile` / `--url`、suite、serving-suite 向け引数、標準 suite 向け引数、one-shot 共通の `--json` / `--quiet` などが含まれます（`strata_cli/cli.py:291-334, 508-516`）。コマンド説明は標準ベンチマーク文書と serving suite の両方を示します（`strata_cli/cli.py:293-300`）。

Help action は引数解析中に表示して終了するので、通常の `_run()` から `_bench()` へ進みません。したがって、このオプション自体はベンチマーク要求を送らず、エンジンを起動せず、結果ディレクトリを作りません（`strata_cli/cli.py:2217-2237, 2119-2148`）。`--help` だけを指定した場合は通常実行時の必須 `--profile` / `--url` が未指定でも表示できます。ただし、help action より前に不正な引数がある場合は argparse の解析エラーになり得ます。

## 適用条件と副作用

`strata.py` から実行する場合、CLI parser より前に旧 updater の拒否確認、新しい Control への handover、`bench` に必要な Python package の存在確認が行われます。依存 package が不足していると、help parser に到達する前に不足名を stderr に出して status 5 で終了します。この preflight は package をインストールしません（`strata.py:30-42, 14-27`）。したがって、help の表示には通常の `bench` 起動前提が影響します。

parser に到達した後、`main()` は Windows では後続のファイルをユーザー所有で作成するためのプロセストークン既定値を設定しようとします。非 Windows では何もせず、失敗も例外にしません（`strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-389`）。これは `--help` 固有の処理ではありません。

## 出力とエラー

argparse の既定 help action が parser 用のヘルプを stdout に表示して status 0 で終了します。`--help` 自体に値の validation はなく、ベンチマーク処理にも入りません。上記 preflight が依存 package 不足を検出した場合は stderr の診断と status 5 で help 表示前に終了します（`strata.py:14-27, 39-42`）。この checkout の CLI を実行して出力を採取することはしていないため、整形後の全文・端末幅による折り返しは記録していません。

## 根拠

- Parser の既定設定とトップレベル command tree: `strata_cli/cli.py:40-45`
- `bench run` parser と表示対象引数: `strata_cli/cli.py:291-334`
- one-shot 共通引数の追加: `strata_cli/cli.py:508-516`
- parse と通常 command dispatch: `strata_cli/cli.py:2119-2155, 2217-2237`
- Python entry point の preflight: `strata.py:14-42`
- Windows の user defaults 処理: `strata_control/private_files.py:349-389`
- 標準ベンチマークの protocol 文書: [`docs/BENCHMARK_PROTOCOL.md`](../../../../../docs/BENCHMARK_PROTOCOL.md)
