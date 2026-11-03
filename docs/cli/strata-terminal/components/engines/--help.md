# `--help`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプ表示用のフラグ。 |

## 役割

`strata components engines` の使用法と、その parser に登録されたオプションを表示します。`--help` は `engines` サブコマンドのスコープであり、トップレベルの `strata --help` や `strata components --help` とは表示対象が異なります。

## 使い方

```sh
strata components engines --help
```

短縮別名も使えます。

```sh
strata components engines -h
```

## 値と既定値

値は不要です。`strata_cli.cli.parser()` は `argparse.ArgumentParser` を `add_help` の指定なしで作成し、サブパーサーを標準の `add_parser()` で登録しています。このため Python `argparse` の既定ヘルプ action（`-h` / `--help`）が有効です。`engines` 固有の値変換や入力 validation はありません。

表示される `engines` parser の option には、`strata_cli.update_cmd._common()` が登録する `--feed`、`--components-dir`、`--backend`、`--wait`、`--force`、`--model-config`、`--output` と、CLI が後から追加する `--json`、`--quiet` が含まれます。

## 実行時の動作

help action が usage と説明・option 一覧を標準出力へ表示し、終了コード 0 で parser を終了します。`main()` では引数 parsing の後に余剰引数の処理、出力形式調整、`_run()` の dispatch を行います。そのためヘルプ表示では `update_cmd.run()` やエンジン一覧の取得処理に進みません。

## 適用条件と副作用

この option は `engines` parser が選ばれたときに有効です。`main()` は引数を解析する前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows では現在の process token の既定 owner と DACL を設定しようとし、Windows 以外では `False` を返して変更しません。したがってヘルプ表示の前にもこの処理が試みられます。エンジンの切替・削除・取得は help action からは実行されません。

## 出力とエラー

- `--help` / `-h` はヘルプを出して終了します（`argparse` の標準 help action）。
- `--help` に値は付けません。help action は parser 内で終了するため、この実行では `main()` の後続 validation やコマンド処理へ進みません。help を指定しない呼び出しで余剰引数が parser から返れば、`main()` は `ap.error()` を呼びます（usage とエラー、終了コード 2）。

## 根拠

- Strata `strata_cli/cli.py:40-45` — root parser の `ArgumentParser` 作成と必須 subparser 登録。
- Strata `strata_cli/cli.py:114-140` — `components` 階層と `components engine`、`update_cmd.add_parsers()` の登録。
- Strata `strata_cli/update_cmd.py:47-57,82-84` — `engines` parser と共通 option の登録。
- Strata `strata_cli/cli.py:508-516` — `update_parsers` を含む parser 群への `--json` / `--quiet` の後付け。
- Strata `strata_cli/cli.py:2233-2248,2249-2254` — parsing とエラー処理が `_run()` dispatch より前にあること。
- Strata `strata_cli/cli.py:2233-2241`、`strata_control/private_files.py:349-388` — parsing 前の user defaults 処理と、Windows で process token defaults を設定する実装。

調査範囲: 同一 revision のソースで parser 登録と dispatch 順序を確認しました。CLI を実行した場合の実際の端末幅・折返しを含む出力見本は採取していません。ヘルプの基本動作は `argparse` の標準 action に基づきます。
