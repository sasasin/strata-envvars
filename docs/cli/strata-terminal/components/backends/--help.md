# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components backends` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。help を表示して終了する |

## 役割

このコマンド専用の使い方と利用可能なオプションを表示します。`--help` は各 parser に明示的に登録されているのではなく、`argparse.ArgumentParser` の既定 help action から提供されます。対象 parser には `--output {human,json}` が登録されています（`strata_cli/cli.py:40-45,129-131`）。

## 使い方

```sh
strata components backends --help
```

短縮形も同じです。

```sh
strata components backends -h
```

## 値と既定値

値は不要で、既定値や値の validation はありません。`--help` と `-h` は同じ parser action の別名です。コマンドに通常の引数として渡す位置引数は定義されていません（`strata_cli/cli.py:129-131`）。

## 実行時の動作

`main()` は parser を作り、`parse_known_args()` を呼びます。help action は parser の引数解析中に usage/help を stdout に出して終了するため、通常の `_run()` や `_components_backends()` には進みません（`strata_cli/cli.py:2217-2237,2131-2132`）。したがって、backend matrix の読み出しや現在の platform の判定は `--help` では行われません。通常実行時の matrix 読み出しは `_components_backends()` にあります（`strata_cli/cli.py:2044-2061`）。

## 適用条件と副作用

ヘルプ表示は `strata components backends` の parser に適用されます。`--output` の値や host platform は help の生成に影響しません。

エントリーポイントの `strata.py` は `components backends` について server package preflight を行わず、その後 `strata_cli.cli.main()` に渡します（`strata.py:14-27,30-43`）。`main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows でプロセスの既定 owner/DACL を現在ユーザー向けに設定しようとする処理で、他 OS では何もしません。失敗は握りつぶされます。help 自体は matrix の照会、ダウンロード、ファイル変更をしません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-390`）。

## 出力とエラー

help action は対象 parser の usage と利用可能な引数の説明を標準出力へ出し、終了コード `0` で終了します。独自の `--help` 出力実装はありません。`--help` を使わず未知の引数を渡した場合は、`parse_known_args()` の余剰引数を `ap.error()` に渡し、argparse の parser error（終了コード `2`）になります（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser とトップレベルの `argparse.ArgumentParser`、必須 subcommand 定義: `strata_cli/cli.py:40-45`
- `components backends` parser と同スコープの `--output`: `strata_cli/cli.py:129-131`
- 引数解析・余剰引数のエラー経路: `strata_cli/cli.py:2217-2231`
- help 後に呼ばれる通常の dispatch と backend 表示処理: `strata_cli/cli.py:2131-2132,2044-2061`
- エントリーポイントの preflight と CLI 委譲: `strata.py:14-27,30-43`
- 引数解析前の Windows user-default 処理: `strata_control/private_files.py:349-390`
