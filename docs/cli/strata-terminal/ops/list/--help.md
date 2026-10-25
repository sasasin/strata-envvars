# `strata ops list --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops list` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata ops list` の引数構文と利用可能なオプションを標準出力に表示します。`ops` の各サブコマンドは `argparse` の `add_parser()` で作られ、`add_help=False` の指定がないため、Python `argparse` の標準 `-h` / `--help` が使えます（`strata_cli/cli.py:255-267`）。

## 使い方

```sh
strata ops list --help
```

ソース checkout から実行する場合はリポジトリのルートで `python strata.py ops list --help` とします（`strata.py:3`, `strata.py:30-43`）。

## 値と既定値

値を指定しないフラグです。ヘルプ表示は `--profile` が必須の通常実行条件より先に処理されるため、`--profile` を付けなくても使えます。通常の `list` 実行では `--profile PROFILE` が必要で、出力形式 `--output` の既定値は `human`、選択肢は `human` と `json` です（`strata_cli/cli.py:260-267`）。

この parser には共通オプションとして `--json`（`--output json` の alias）と `--quiet` も登録されています（`strata_cli/cli.py:508-515`）。これらはヘルプを表示するために必要ありません。

## 実行時の動作

引数解析中に help action がヘルプを出力して終了するため、`ops list` の処理本体には進みません。通常実行時の一覧取得は `_ops()` から `recipes.list_recipes(profile)` を呼びますが（`strata_cli/cli.py:1391-1403`）、`--help` ではこの呼び出しや一覧データの読み込みは行われません。`--help` 自体が一覧を作成・変更する効果はありません。

## 適用条件と副作用

`strata.py` から CLI を起動すると、引数 parser の構築前に `main()` が `private_files.adopt_user_defaults()` を呼びます（`strata.py:42-43`, `strata_cli/cli.py:2217-2224`）。この関数は Windows では現在プロセスの既定 owner / DACL を設定しようとし、その他の OS では何もしません（`strata_control/private_files.py:349-357`, `strata_control/private_files.py:372-376`）。したがってヘルプ action より前にこの起動時処理が行われます。ヘルプ表示そのものは `ops` の recipe や profile を変更しません。

## 出力とエラー

ヘルプ本文は標準出力に表示され、通常の argparse help action は終了コード `0` で parser を終了します。表示内容には使用法、必須の `--profile`、`--output {human,json}`、`--json`、`--quiet` が含まれます。調査では CLI の実行は行っておらず、表示内容は parser の定義と argparse の標準動作から確認しています。

## 根拠

- `strata_cli/cli.py:255-267` — `ops` / `list` parser の登録、`--profile` の必須指定、`--output` の値と既定値。
- `strata_cli/cli.py:508-515` — 各 ops parser への `--json` と `--quiet` の追加。
- `strata_cli/cli.py:2217-2224` — 引数解析前の起動処理と parser 呼び出し。
- `strata_cli/cli.py:1391-1403`, `strata_cli/cli.py:2158-2161` — 通常の ops 処理と list の実処理経路。
- `strata_control/private_files.py:349-376` — Windows での起動時 owner / DACL 処理と非 Windows での no-op。
- `strata.py:3`, `strata.py:30-43` — source checkout での CLI 入口。
