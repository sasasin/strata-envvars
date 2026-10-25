# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models inspect` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata models inspect` の使い方と、その parser に登録された引数・オプションを表示します。`argparse` の標準ヘルプ action によるもので、`models_inspect` の定義では独自の help action を置いたり、標準ヘルプを無効にしたりしていません（`strata_cli/cli.py:41,153-156`）。

## 使い方

```sh
strata models inspect --help
```

`-h` も同じヘルプ表示を行います。

## 値と既定値

値は不要です。`argparse.ArgumentParser` は既定で `-h` と `--help` を登録します。通常の引数解析でこの action が実行されると、ヘルプを標準出力へ書き、終了コード `0` で parser を終了します。

表示対象には位置引数 `model_id`、`--install-dir`、`--output {human,json}` が含まれます。加えて `--json` と `--quiet` は `models_inspect` を含む共通登録ループが後から追加します（`strata_cli/cli.py:153-156,508-515`）。`--json` は `--output json` の別表記として説明され、`--quiet` は人向け情報出力を抑制するフラグです。

## 実行時の動作

CLI の `main()` は parser を作成し、`parse_known_args()` を呼びます。ヘルプ action が実行されると parser がその場で終了するため、通常の引数処理や `_run()` のコマンド dispatch には進まず、モデル設定の検査処理 `models.inspect()` も呼びません（`strata_cli/cli.py:2217-2237,2140-2142,550-603`）。位置引数 `model_id` を指定せずに `--help` だけを渡しても、ヘルプ action が終了するので通常の必須位置引数エラーにはなりません。

## 適用条件と副作用

このオプションは `strata models inspect` の parser に適用されます。ヘルプ表示より前に `main()` は `private_files.adopt_user_defaults()` を呼びます。この関数は POSIX では何もせず、Windows では可能な場合にプロセス token の既定 owner と既定 DACL を設定します。したがって Windows 上ではヘルプ表示前にプロセスの権限既定値へ作用し得ますが、`adopt_user_defaults()` 自体はファイルの作成・検査を行いません（`strata_cli/cli.py:2217-2223`; `strata_control/private_files.py:349-389`）。

## 出力とエラー

標準ヘルプ action は parser のヘルプ文を標準出力に表示して終了コード `0` で終了します。`-h` は同じ動作です。ヘルプ action が実行されない通常の解析では、必須引数の欠落や不正な引数は `argparse` の parser error になります。`main()` も未認識引数が残った場合 `ap.error()` を呼びます（`strata_cli/cli.py:2217-2231`）。

## 根拠

- `strata_cli/cli.py:40-45` — root parser と標準 `argparse.ArgumentParser` の生成。
- `strata_cli/cli.py:141-156` — `models inspect` の parser、位置引数、個別オプション。
- `strata_cli/cli.py:508-515` — `models_inspect` に共通 `--json` / `--quiet` を追加。
- `strata_cli/cli.py:550-603` — `models inspect` の通常処理と `models.inspect()` の呼び出し。
- `strata_cli/cli.py:2217-2237` — 起動時処理、引数解析、通常 dispatch への移行。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の OS 条件と token 既定値処理。
