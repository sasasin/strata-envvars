# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops history` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし（フラグ） |

## 役割

`strata ops history` の usage と、このサブコマンド parser に属する引数の説明を表示して終了します。トップレベルの `strata --help` や `strata ops --help` とは別の階層のヘルプです。

## 使い方

```sh
strata ops history --help
strata ops history -h
```

履歴名や `--profile` を指定しなくてもヘルプを表示できます。ヘルプ上の通常実行形式は `strata ops history [引数] --profile PROFILE [--output {human,json}] [--json] [--quiet] name` です。

## 値と既定値

値は取りません。`strata_cli/cli.py` は `argparse.ArgumentParser` とサブパーサを使い、`add_help` を無効化せず `--help` を個別登録していません。そのため Python `argparse` の標準ヘルプ action が `-h` を別名として提供します。`history` parser には位置引数 `name`、必須の `--profile`、既定値 `human` の `--output` が定義されます。さらに one-shot コマンド共通の `--json` と `--quiet` が追加されます。

## 実行時の動作

Parser は `history` action に対して `name`, `--profile`, `--output` を設定します。`--help` は parser が構築した当該コマンドの usage とオプション一覧を出して parser 処理を終了するため、通常の実行分岐である `_ops()` や `recipes.history()` には到達せず、profile/recipe の読み込みや履歴ファイルの列挙は行いません。

`strata ops --help` は `ops` のサブコマンド一覧、`strata ops history --help` は `history` の引数一覧を表示します。

## 適用条件と副作用

ヘルプ表示前に `main()` は `private_files.adopt_user_defaults()` を呼びます。この関数は Windows ではプロセス token の既定 owner / DACL の調整を試みます（失敗時は `False` を返す実装です）。POSIX では何もせず `False` を返します。Windows で token default が変更される可能性があるため、ヘルプ表示もこの起動時処理を通ります。ソース上、ヘルプ処理自体による recipe・履歴ファイルの変更、ネットワークアクセス、子プロセス起動はありません。

## 出力とエラー

標準の argparse help action により usage と引数説明が表示され、通常は終了コード 0 で処理が終わります。`--help` 自体に独自の出力形式指定はなく、`--json` / `--output` は history 結果の形式を制御する引数です。未知の引数や必須引数不足でヘルプを要求しない通常実行は、`parse_known_args()` 後の `ap.error()` 経路で usage とエラーを標準エラーへ出し、argparse が終了コード 2 で終了します。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser を `argparse.ArgumentParser` で作成し、通常の subparser を登録。
- `strata_cli/cli.py:255-267` — `ops` / `history` parser、位置引数 `name`、必須 `--profile`、`--output` の定義。
- `strata_cli/cli.py:508-515` — one-shot parser 群に `--json` / `--quiet` を追加。`ops_items` に `history` が含まれる。
- `strata_cli/cli.py:1391-1394,1431-1435` — 通常実行時の `history` 分岐と `recipes.history()` の呼び出し。
- `strata_cli/cli.py:2217-2237` — parser 構築・引数解析・未知引数処理・実行分岐の順序。
- `strata_control/private_files.py:349-358` — 起動時に呼ばれる token default 調整関数の説明と Windows 以外での早期 return。
- `strata_control/recipes.py:240-250` — 通常実行時に現行 revision と履歴ファイルを列挙する処理。
- 対象 checkout は調査開始時 `## main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

Python 標準 `argparse` の具体的な help 表示・終了動作は標準ライブラリの仕様に依存します。調査では同一 revision の CLI help を別途実行せず、Strata 側 parser の構成と呼び出し経路を確認しました。
