# `--help`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`install-file` parser が受け付ける位置引数とオプションを表示して、処理を終了します。ヘルプはこのサブコマンドに固有で、トップレベルや別の `components` サブコマンドの一覧とは異なります。

## 使い方

```sh
strata components install-file --help
```

`file` 位置引数を省略していてもヘルプを表示できます。`file` は通常実行では必須ですが、help action が解析を終了するため、その必須引数の検証やインストール処理には進みません。

## 値と既定値

値を取りません。`strata_cli/update_cmd.py` は `components install-file` parser を `components_sp.add_parser(...)` で作成し、`argparse.ArgumentParser` の標準 help を無効化していません。そのため標準の `-h` / `--help` が利用できます。

表示内容には、位置引数 `file`、`_common()` が加える `--feed`、`--components-dir`、`--backend`、`--wait`、`--force`、`--model-config`、`--output`、および後から one-shot parser 群へ加えられる `--json` と `--quiet` が含まれます。引数の説明と順序は parser 定義に従います。

## 実行時の動作

`main()` は引数を解析し、通常なら `_run()` から `update_cmd.run()` へ `install-file` を dispatch します。しかし `--help` は `argparse` の解析中にヘルプを出して parser を終了させるため、この dispatch と `install_engine_file()` の呼び出しには到達しません。したがって package の検証・導入やネットワーク取得はこのオプション自体では行いません。

## 適用条件と副作用

`components install-file` の後に指定します。`file` を含む位置引数の並びや、同じ parser に登録された共通 option と併用しても、help action が選ばれれば説明を表示して終了します。

コマンドの `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows では後続作成ファイル向けにプロセス token の既定所有者／DACL 設定を試み、Windows 以外では何もしません。help の経路は install-file のファイル導入処理には進みません。

## 出力とエラー

標準 `argparse` の help 表示として usage、コマンド説明、位置引数およびオプションの説明を標準出力へ出し、終了コード `0` で解析を終了します。ヘルプ表示後に通常の必須引数チェックや command dispatch は行われません。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` によるトップレベル parser の作成。
- `strata_cli/cli.py:114-115` — `components` parser とサブコマンド parser の登録。
- `strata_cli/cli.py:139-140` — update 系 parser を登録し、その一覧を one-shot option 追加に渡す。
- `strata_cli/update_cmd.py:30-40` — install-file と共有する `_common()` option の定義。
- `strata_cli/update_cmd.py:57-62` — `install-file` parser、必須位置引数 `file`、共通 option の登録。
- `strata_cli/cli.py:508-515` — `update_parsers` を含む one-shot parser へ `--json` と `--quiet` を追加。
- `strata_cli/cli.py:2217-2237` — `main()` の起動時処理、引数解析と通常 dispatch への分岐。
- `strata_control/private_files.py:349-357, 359-385` — `adopt_user_defaults()` の Windows 条件と process token 設定。
- `strata_cli/cli.py:2135-2137`、`strata_cli/update_cmd.py:208-217` — 通常解析時の dispatch と install-file 実行経路。help は解析中に終了するためこの経路には進みません。
